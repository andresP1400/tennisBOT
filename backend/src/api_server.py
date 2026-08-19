"""TennisBot FastAPI server.

Serves training status, live inference (tracker state), history, weather,
live odds, value bets, and certified prediction tracking.
"""
from __future__ import annotations

import math
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from config import MODELS_DIR, REPORTS_DIR

# backend/src/api_server.py: sources live in backend/src, project data and
# .env files stay at the repository root (three levels up).
SRC_DIR = Path(__file__).resolve().parent
BASE_DIR = SRC_DIR.parent.parent
# .env first, then local.env (personal secrets override)
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "local.env", override=True)

# API port (9090: outside Windows reserved/Hyper-V port ranges that block
# binds on 8000-8050 etc. with WSAEACCES)
API_PORT = int(os.environ.get("TENNISBOT_API_PORT", "9090"))

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    f"http://localhost:{API_PORT}",
    f"http://127.0.0.1:{API_PORT}",
]

# Accept pure-stats stacking, pure alias, and market-aware variants
MODEL_NAME_PATTERN = re.compile(
    r"^(atp|wta)_(stacking_model|model|model_odds)\.pkl$"
)

# Column-name bases where parquet/snapshot keys differ from *_diff prefix
_BASE_COL_MAP = {"ranking": "rank", "ranking_points": "rank_points"}
_FATIGUE_BASES = {"days_rest", "minutes_on_court_last_10_days", "matches_last_7_days"}
_SURFACE_BASES = {"elo_surface", "win_pct_surface", "elo_blend"}


def _sanitize_nan(obj: Any) -> Any:
    """Convert NaN/inf floats to None so JSON serialization doesn't crash."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_nan(v) for v in obj]
    if isinstance(obj, np.floating) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if isinstance(obj, np.integer):
        return int(obj)
    return obj


def _resolve_model_path(model_name: str) -> Path:
    """Resolve a model filename to an absolute path under MODELS_DIR, validated."""
    if not MODEL_NAME_PATTERN.match(model_name):
        raise HTTPException(status_code=400, detail="Invalid model name")
    candidate = (MODELS_DIR / model_name).resolve()
    models_root = MODELS_DIR.resolve()
    if not str(candidate).startswith(str(models_root)):
        raise HTTPException(status_code=400, detail="Invalid model path")
    return candidate


app = FastAPI(
    title="TennisBot API Engine",
    description=(
        "Backend ML/API per TennisBot. "
        "La UI web e' su http://localhost:3000 — qui trovi /docs e gli endpoint JSON."
    ),
    version="2.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root_landing() -> str:
    """Friendly landing page — browsers hit / and used to see a blank/black 404."""
    return """<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TennisBot API</title>
  <style>
    :root { color-scheme: dark; }
    body {
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
      background: #0b1220; color: #e8eefc;
    }
    .card {
      width: min(520px, 92vw); padding: 2rem; border-radius: 16px;
      background: #121a2b; border: 1px solid #243049; box-shadow: 0 20px 50px #0008;
    }
    h1 { margin: 0 0 .5rem; font-size: 1.6rem; }
    p { margin: 0 0 1.25rem; color: #9fb0d0; line-height: 1.5; }
    a.btn {
      display: inline-block; margin: .35rem .5rem .35rem 0; padding: .7rem 1rem;
      border-radius: 10px; text-decoration: none; font-weight: 600;
    }
    .primary { background: #10b981; color: #042f1f; }
    .secondary { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; }
    code { color: #86efac; }
    ul { margin: 0 0 1rem 1.1rem; color: #9fb0d0; }
  </style>
</head>
<body>
  <div class="card">
    <h1>TennisBot API</h1>
    <p>
      Questa e' l'API backend (JSON). La pagina nera/vuota che vedevi era un 404 sulla root.
      Per usare la piattaforma di predizione apri la dashboard Next.js.
    </p>
    <a class="btn primary" href="http://localhost:3000/dashboard/predict">Apri Predict UI</a>
    <a class="btn secondary" href="http://localhost:3000/dashboard">Dashboard</a>
    <a class="btn secondary" href="/docs">API Docs (Swagger)</a>
    <a class="btn secondary" href="/api/status">/api/status</a>
    <p style="margin-top:1.25rem;font-size:.9rem">
      Endpoint utili: <code>/api/predict</code>, <code>/api/models</code>,
      <code>/api/track</code>, <code>/api/history</code>
    </p>
  </div>
</body>
</html>"""


@app.get("/health", include_in_schema=False)
@app.get("/api/health")
def health() -> dict:
    """Simple liveness probe for monitors and reverse proxies."""
    return {"status": "ok", "service": "tennisbot-api"}


training_status = {
    "is_training": False,
    "current_task": "Idle",
    "progress": 0,
    "logs": [],
    "error": False,
    "success": False,
}


class TrainRequest(BaseModel):
    tour: str = Field(..., pattern="^(atp|wta)$")
    trials: int = Field(..., ge=1, le=1000)
    startYear: int = Field(..., ge=1968, le=2100)
    endYear: int = Field(..., ge=1968, le=2100)


class PredictRequest(BaseModel):
    player1: str = Field(..., min_length=1, max_length=128)
    player2: str = Field(..., min_length=1, max_length=128)
    surface: str = Field(..., min_length=1, max_length=32)
    model: str = Field(..., min_length=1, max_length=128)
    best_of: int = Field(default=3, ge=3, le=5)
    odds1: float | None = Field(default=None, gt=1.0)
    odds2: float | None = Field(default=None, gt=1.0)


def run_training_pipeline(tour: str, trials: int, start_year: int, end_year: int) -> None:
    """Launch main.py train in background and capture logs."""
    global training_status
    training_status["is_training"] = True
    training_status["error"] = False
    training_status["success"] = False
    training_status["current_task"] = (
        f"Training ensemble for tour {tour.upper()} ({start_year}-{end_year})"
    )
    training_status["logs"] = []

    try:
        process = subprocess.Popen(
            [
                sys.executable, "main.py", "train",
                "--tour", tour,
                "--optuna-trials", str(trials),
                "--start-year", str(start_year),
                "--end-year", str(end_year),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(SRC_DIR),
        )

        for line in iter(process.stdout.readline, ""):
            if line:
                training_status["logs"].append(line.strip())
                if len(training_status["logs"]) > 1500:
                    training_status["logs"].pop(0)

        process.stdout.close()
        process.wait()

        if process.returncode == 0:
            training_status["current_task"] = "Training Completato!"
            training_status["success"] = True
            global _global_dataset, _global_dataset_mtime, _global_dataset_tour
            _global_dataset = None
            _global_dataset_mtime = None
            _global_dataset_tour = None
            _inference_states.clear()
        else:
            training_status["current_task"] = f"Errore! (Exit code: {process.returncode})"
            training_status["error"] = True

    except Exception as e:
        training_status["current_task"] = f"Exception: {str(e)}"
        training_status["error"] = True
    finally:
        training_status["is_training"] = False


@app.get("/api/status")
def get_status() -> dict:
    return training_status


@app.post("/api/train/start")
def start_training(req: TrainRequest, background_tasks: BackgroundTasks) -> dict:
    if training_status["is_training"]:
        raise HTTPException(status_code=400, detail="Training already running")
    background_tasks.add_task(
        run_training_pipeline, req.tour, req.trials, req.startYear, req.endYear
    )
    return {
        "message": (
            f"Training started per tour {req.tour} iterazioni {req.trials} "
            f"anni {req.startYear}-{req.endYear}"
        )
    }


@app.get("/api/models")
def list_models() -> dict:
    try:
        models = [
            p.name for p in MODELS_DIR.glob("*.pkl")
            if MODEL_NAME_PATTERN.match(p.name)
        ]
        return {"models": sorted(models)}
    except Exception:
        return {"models": []}


_global_dataset = None
_global_dataset_mtime = None
_global_dataset_tour = None
_inference_states: dict = {}


def _load_dataset(tour: str) -> pd.DataFrame | None:
    """Load full parquet (both _A and _B) with mtime cache invalidation.

    IMPORTANT: do NOT filter to _A only — that would bias player lookups
    toward wins only (each player appears as p1 only when they win in _A).
    """
    global _global_dataset, _global_dataset_mtime, _global_dataset_tour

    if tour not in ("atp", "wta"):
        raise HTTPException(status_code=400, detail="Invalid tour")

    data_path = BASE_DIR / "data" / "processed" / f"{tour}_features.parquet"
    if not data_path.exists():
        return None

    current_mtime = data_path.stat().st_mtime
    if (
        _global_dataset is None
        or _global_dataset_mtime != current_mtime
        or _global_dataset_tour != tour
    ):
        _global_dataset = pd.read_parquet(data_path)
        _global_dataset_mtime = current_mtime
        _global_dataset_tour = tour

    return _global_dataset


def _load_state(tour: str = "atp"):
    """Tracker state serialized by the feature builder (tour-aware cache)."""
    if tour not in _inference_states:
        from pipeline.inference import load_inference_state
        _inference_states[tour] = load_inference_state(tour)
    return _inference_states[tour]


def _fold_player_name(name: str) -> str:
    """Lowercase and strip diacritics for accent-insensitive matching."""
    if not isinstance(name, str):
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", name) if not unicodedata.combining(c)
    ).strip().lower()


def _get_player_latest_stats(
    player_name: str, df: pd.DataFrame, surface: str | None = None
) -> pd.Series | None:
    """Last chronological row where the player appears as p1 (win OR loss)."""
    key = _fold_player_name(player_name)
    mask = df["p1_name"].map(_fold_player_name) == key
    if surface and "surface" in df.columns:
        mask &= df["surface"] == surface
    p_df = df[mask]
    if p_df.empty:
        return None
    sort_col = "match_date_est" if "match_date_est" in p_df.columns else "tourney_date"
    return p_df.sort_values(sort_col, ascending=False).iloc[0]


def _get_h2h_stats(
    player1: str, player2: str, df: pd.DataFrame, surface: str | None = None
) -> dict:
    mask = (
        (df["p1_name"].map(_fold_player_name) == _fold_player_name(player1))
        & (df["p2_name"].map(_fold_player_name) == _fold_player_name(player2))
    )
    h_df = df[mask]
    result = {"h2h_win_pct": np.nan, "h2h_win_pct_surface": np.nan, "h2h_total_matches": 0}
    if h_df.empty:
        return result
    result["h2h_win_pct"] = float(h_df["label"].mean())
    result["h2h_total_matches"] = int(len(h_df))
    if surface and "surface" in h_df.columns:
        s_df = h_df[h_df["surface"] == surface]
        if not s_df.empty:
            result["h2h_win_pct_surface"] = float(s_df["label"].mean())
    return result


def _stat_value(stats_row, base: str) -> float:
    if stats_row is None:
        return np.nan
    col = f"p1_{_BASE_COL_MAP.get(base, base)}"
    if col not in stats_row.index:
        return np.nan
    try:
        return float(stats_row[col])
    except (TypeError, ValueError):
        return np.nan


def _build_feature_row(feature_cols, sA, sB, sA_surf, sB_surf, h2h, surface, best_of=3):
    """Build model input row for fallback historical-row inference."""
    df_fake = pd.DataFrame(np.nan, index=[0], columns=feature_cols)
    for col in feature_cols:
        if col.startswith("surface_"):
            df_fake[col] = 1.0 if col == f"surface_{surface}" else 0.0
        elif col == "tourney_level_encoded":
            df_fake[col] = 2
        elif col == "round_encoded":
            df_fake[col] = 3
        elif col == "best_of":
            df_fake[col] = best_of
        elif col == "month":
            df_fake[col] = datetime.now(timezone.utc).month
        elif col == "indoor_outdoor":
            df_fake[col] = 0
        elif col == "altitude":
            df_fake[col] = 0.0
        elif col == "h2h_win_pct":
            df_fake[col] = h2h["h2h_win_pct"]
        elif col == "h2h_win_pct_surface":
            df_fake[col] = h2h["h2h_win_pct_surface"]
        elif col == "hand_matchup":
            try:
                hand_a = str(sA["p1_hand"]) if sA is not None else "U"
                hand_b = str(sB["p1_hand"]) if sB is not None else "U"
                df_fake[col] = int(hand_a != hand_b) if "U" not in (hand_a, hand_b) else 0
            except Exception:
                df_fake[col] = 0
        elif col == "home_country_flag":
            df_fake[col] = 0
        elif col == "qualifier_flag_diff":
            df_fake[col] = 0
        elif col == "cold_start_flag":
            count_a = _stat_value(sA, "match_count")
            count_b = _stat_value(sB, "match_count")
            cold = (
                np.isnan(count_a) or count_a < 10
                or np.isnan(count_b) or count_b < 10
            )
            df_fake[col] = int(cold)
        elif col == "log_rank_diff":
            rank_a = _stat_value(sA, "rank")
            rank_b = _stat_value(sB, "rank")
            if not np.isnan(rank_a) and not np.isnan(rank_b):
                df_fake[col] = np.log(max(rank_a, 1.0)) - np.log(max(rank_b, 1.0))
        elif col == "elo_diff_x_bo5":
            ea = _stat_value(sA, "elo")
            eb = _stat_value(sB, "elo")
            if not np.isnan(ea) and not np.isnan(eb):
                df_fake[col] = (ea - eb) * (1 if best_of == 5 else 0)
        elif col.endswith("_diff"):
            base = col[: -len("_diff")]
            if base in _FATIGUE_BASES:
                continue  # NaN -> train median (stale fatigue is worse than missing)
            row_a, row_b = (sA_surf, sB_surf) if base in _SURFACE_BASES else (sA, sB)
            val_a = _stat_value(row_a, base)
            val_b = _stat_value(row_b, base)
            if not np.isnan(val_a) and not np.isnan(val_b):
                df_fake[col] = val_a - val_b
    return df_fake


def _predict_proba_from_features(bundle, df_fake) -> float:
    X_imp = bundle["imputer"].transform(df_fake.values)
    X_scaled = bundle["scaler"].transform(X_imp)
    p_lgbm = bundle["base_models"]["lgbm"].predict_proba(X_scaled)[:, 1]
    p_xgb = bundle["base_models"]["xgb"].predict_proba(X_scaled)[:, 1]
    p_lr = bundle["base_models"]["lr"].predict_proba(X_scaled)[:, 1]
    X_meta = np.column_stack([p_lgbm, p_xgb, p_lr])
    raw_prob = bundle["meta_model"].predict_proba(X_meta)[:, 1][0]
    if bundle.get("calibrator") is not None:
        return float(bundle["calibrator"].predict(np.array(raw_prob).reshape(-1, 1))[0])
    return float(raw_prob)


def _predict_with_state(bundle, state, req: PredictRequest) -> dict:
    """Live inference from serialized tracker state."""
    from pipeline.inference import (
        assess_reliability,
        build_match_features,
        player_snapshot,
        resolve_player_id,
    )

    feature_cols = bundle["feature_cols"]
    now = pd.Timestamp.now()
    id1 = resolve_player_id(state, req.player1)
    id2 = resolve_player_id(state, req.player2)
    snap1 = player_snapshot(state, id1, req.surface, now) if id1 is not None else {}
    snap2 = player_snapshot(state, id2, req.surface, now) if id2 is not None else {}
    best_of = req.best_of if req.best_of in (3, 5) else 3

    row_fwd = build_match_features(
        state, feature_cols, snap1, snap2, id1, id2,
        req.surface, best_of=best_of,
        odds_a=req.odds1, odds_b=req.odds2, now=now,
    )
    row_rev = build_match_features(
        state, feature_cols, snap2, snap1, id2, id1,
        req.surface, best_of=best_of,
        odds_a=req.odds2, odds_b=req.odds1, now=now,
    )
    prob_fwd = _predict_proba_from_features(bundle, row_fwd)
    prob_rev = _predict_proba_from_features(bundle, row_rev)
    final_prob = (prob_fwd + (1.0 - prob_rev)) / 2.0

    h2h = (
        state["h2h"].get_h2h(id1, id2, req.surface)
        if (id1 is not None and id2 is not None)
        else {"h2h_win_pct": None, "h2h_total_matches": 0}
    )
    reliability = assess_reliability(
        snap1, snap2, h2h.get("h2h_total_matches", 0),
        id1 is not None, id2 is not None,
    )
    prob1 = max(0.01, min(0.99, final_prob))
    h2h_pct = h2h.get("h2h_win_pct")
    return {
        "match": f"{req.player1} vs {req.player2}",
        "surface": req.surface,
        "best_of": best_of,
        "model_used": req.model,
        "prob1": prob1,
        "prob2": 1.0 - prob1,
        "winner": req.player1 if prob1 >= 0.5 else req.player2,
        "reliability": reliability["level"],
        "reliability_notes": reliability["reasons"],
        "h2h": {
            "p1_win_pct": (
                None if h2h_pct is None
                or (isinstance(h2h_pct, float) and np.isnan(h2h_pct))
                else round(float(h2h_pct), 3)
            ),
            "total_matches": int(h2h.get("h2h_total_matches", 0)),
        },
        "elo": {
            "p1": round(snap1.get("elo", 0), 1) if snap1 else None,
            "p2": round(snap2.get("elo", 0), 1) if snap2 else None,
            "p1_surface_blend": round(snap1.get("elo_blend", 0), 1) if snap1 else None,
            "p2_surface_blend": round(snap2.get("elo_blend", 0), 1) if snap2 else None,
        },
        "data_through": state.get("data_through"),
        "odds1": req.odds1,
        "odds2": req.odds2,
        "info": "Inferenza live da stato tracker (dati aggiornati all'ultimo build)",
    }


def _maybe_log_prediction(req: PredictRequest, result: dict) -> None:
    if not result or result.get("error") or result.get("prob1") is None:
        return
    try:
        from pipeline.track import log_prediction
        tour = "wta" if "wta" in (req.model or "").lower() else "atp"
        log_prediction(
            tour=tour,
            model=req.model,
            player1=req.player1,
            player2=req.player2,
            surface=req.surface,
            best_of=getattr(req, "best_of", 3),
            prob1=result["prob1"],
            predicted_winner=result["winner"],
            reliability=result.get("reliability"),
            odds1=getattr(req, "odds1", None),
            odds2=getattr(req, "odds2", None),
        )
    except Exception as exc:
        print(f"[track] log skipped: {exc}")


def _autofill_odds(req: PredictRequest) -> PredictRequest:
    """Fill any missing market odds (odds1/odds2) from live odds sources.

    Only slots the user left empty; never overrides explicit odds. Uses the
    TheOddsAPI-backed scraper (falls back silently if no key / no match).
    """
    if req.odds1 is not None and req.odds2 is not None:
        return req
    try:
        from features.live_odds import LiveOddsScraper

        odds = LiveOddsScraper().get_match_odds(req.player1, req.player2, req.surface)
        best = odds.get("best_odds", {})
        o1, o2 = best.get("player1"), best.get("player2")
        o1 = None if o1 is None or (isinstance(o1, float) and math.isnan(o1)) else float(o1)
        o2 = None if o2 is None or (isinstance(o2, float) and math.isnan(o2)) else float(o2)
        return req.model_copy(
            update={
                "odds1": req.odds1 if req.odds1 is not None else o1,
                "odds2": req.odds2 if req.odds2 is not None else o2,
            }
        )
    except Exception:
        return req


@app.post("/api/predict")
def predict_match(req: PredictRequest) -> dict:
    """Predict with live tracker state; fall back to improved historical rows."""
    try:
        model_path = _resolve_model_path(req.model)
        if not model_path.exists():
            return {"error": "Modello non trovato su disco"}

        bundle = joblib.load(model_path)
        tour = "wta" if "wta" in (req.model or "").lower() else "atp"

        # Auto-fill market odds if the client did not provide them.
        req = _autofill_odds(req)

        # Primary: live tracker state
        state = _load_state(tour)
        if state is not None:
            result = _predict_with_state(bundle, state, req)
            _maybe_log_prediction(req, result)
            return _sanitize_nan(result)

        # Fallback: full parquet (both _A and _B), surface-aware + symmetrized
        dataset = _load_dataset(tour)
        if dataset is None:
            return {"error": "Dataset features non trovato. Esegui `python backend/src/main.py features`."}

        feature_cols = bundle["feature_cols"]
        p1_stats = _get_player_latest_stats(req.player1, dataset)
        p2_stats = _get_player_latest_stats(req.player2, dataset)
        p1_surf = _get_player_latest_stats(req.player1, dataset, surface=req.surface)
        p2_surf = _get_player_latest_stats(req.player2, dataset, surface=req.surface)
        h2h_12 = _get_h2h_stats(req.player1, req.player2, dataset, surface=req.surface)
        h2h_21 = _get_h2h_stats(req.player2, req.player1, dataset, surface=req.surface)
        best_of = req.best_of if req.best_of in (3, 5) else 3

        row_fwd = _build_feature_row(
            feature_cols, p1_stats, p2_stats, p1_surf, p2_surf, h2h_12, req.surface, best_of
        )
        row_rev = _build_feature_row(
            feature_cols, p2_stats, p1_stats, p2_surf, p1_surf, h2h_21, req.surface, best_of
        )
        prob_fwd = _predict_proba_from_features(bundle, row_fwd)
        prob_rev = _predict_proba_from_features(bundle, row_rev)
        final_prob = (prob_fwd + (1.0 - prob_rev)) / 2.0
        prob1 = max(0.01, min(0.99, final_prob))
        has_history = p1_stats is not None and p2_stats is not None
        result = {
            "match": f"{req.player1} vs {req.player2}",
            "surface": req.surface,
            "best_of": best_of,
            "model_used": req.model,
            "prob1": prob1,
            "prob2": 1.0 - prob1,
            "winner": req.player1 if prob1 >= 0.5 else req.player2,
            "reliability": "media" if has_history else "bassa",
            "reliability_notes": (
                [] if has_history
                else ["cold start: uno o entrambi i giocatori non trovati nello storico"]
            ),
            "h2h": {
                "p1_win_pct": (
                    None if np.isnan(h2h_12["h2h_win_pct"])
                    else round(float(h2h_12["h2h_win_pct"]), 3)
                ),
                "total_matches": int(h2h_12.get("h2h_total_matches", 0)),
            },
            "odds1": req.odds1,
            "odds2": req.odds2,
            "info": (
                "Fallback parquet (simmetrizzato, no bias _A) — "
                "rigenera features per inference state live"
                if has_history else "Cold Start - Dati Mediani"
            ),
        }
        _maybe_log_prediction(req, result)
        return _sanitize_nan(result)

    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/players")
def list_players(q: str = "", limit: int = 100, tour: str = "atp") -> dict:
    if tour not in ("atp", "wta"):
        raise HTTPException(status_code=400, detail="Invalid tour")
    state = _load_state(tour)
    if state is None:
        return {"players": [], "total": 0}
    names = [
        row.get("name")
        for row in state.get("players", {}).values()
        if isinstance(row.get("name"), str)
    ]
    ql = q.strip().lower()
    if ql:
        names = [n for n in names if ql in n.lower()]
    names = sorted(set(names))
    # No hard product cap — return up to what the client asked (min 1)
    cap = max(1, limit) if limit > 0 else len(names)
    return {"players": names[:cap], "total": len(names)}


@app.get("/api/track")
def get_track(tour: str = "atp", limit: int = 500) -> dict:
    try:
        from pipeline.track import read_log, summary
        records = read_log(tour)
        records = sorted(records, key=lambda r: r.get("ts", ""), reverse=True)[:limit]
        return {"summary": summary(tour), "records": records}
    except Exception as e:
        return {"error": str(e), "summary": {}, "records": []}


@app.post("/api/track/settle")
def settle_track(tour: str = "atp") -> dict:
    try:
        from pipeline.track import settle_predictions
        return settle_predictions(tour)
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/track/verify")
def verify_track(tour: str = "atp") -> dict:
    try:
        from pipeline.track import verify_integrity
        return verify_integrity(tour)
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/reload")
def reload_dataset() -> dict:
    global _global_dataset, _global_dataset_mtime, _global_dataset_tour
    _global_dataset = None
    _global_dataset_mtime = None
    _global_dataset_tour = None
    _inference_states.clear()
    return {"message": "Cache dataset e inference state invalidata."}


@app.get("/api/history")
def get_match_history(limit: int = 200) -> dict:
    try:
        for name in ("atp_stacking_model.pkl", "atp_model.pkl"):
            model_path = _resolve_model_path(name)
            if model_path.exists():
                break
        else:
            return {"error": "Modello non trovato in models/"}

        bundle = joblib.load(model_path)
        data_path = BASE_DIR / "data" / "processed" / "atp_features.parquet"
        if not data_path.exists():
            return {"error": "atp_features.parquet non trovato. Addestrare prima il modello!"}

        df = pd.read_parquet(data_path)
        df = df[~df["tourney_name"].str.contains("Next Gen", na=False)]
        try:
            base_ids = df["match_id"].str.split("_").str[0].astype(int)
        except ValueError:
            base_ids = pd.Series(range(len(df)))

        keep_a = (base_ids % 2 == 0) & df["match_id"].str.endswith("_A", na=False)
        keep_b = (base_ids % 2 != 0) & df["match_id"].str.endswith("_B", na=False)
        df_single = df[keep_a | keep_b].copy()
        sort_col = "match_date_est" if "match_date_est" in df_single.columns else "tourney_date"
        # Fetch enough rows for the requested limit (no artificial 100-row ceiling)
        take = max(int(limit), 1)
        df_single = df_single.sort_values(sort_col, ascending=False).head(take)

        feature_cols = bundle["feature_cols"]
        # Only use columns that exist
        available = [c for c in feature_cols if c in df_single.columns]
        X = df_single[available].reindex(columns=feature_cols).values
        X_imp = bundle["imputer"].transform(X)
        X_scaled = bundle["scaler"].transform(X_imp)
        p_lgbm = bundle["base_models"]["lgbm"].predict_proba(X_scaled)[:, 1]
        p_xgb = bundle["base_models"]["xgb"].predict_proba(X_scaled)[:, 1]
        p_lr = bundle["base_models"]["lr"].predict_proba(X_scaled)[:, 1]
        X_meta = np.column_stack([p_lgbm, p_xgb, p_lr])
        raw_probs = bundle["meta_model"].predict_proba(X_meta)[:, 1]
        if bundle.get("calibrator") is not None:
            final_probs = bundle["calibrator"].predict(raw_probs.reshape(-1, 1))
        else:
            final_probs = raw_probs

        results = []
        for i, row in enumerate(df_single.itertuples()):
            prob1 = float(final_probs[i])
            actual_winner = row.p1_name if row.label == 1 else row.p2_name
            d_str = str(getattr(row, "tourney_date", ""))[:10]
            results.append({
                "id": str(row.match_id),
                "date": d_str,
                "tournament": str(row.tourney_name),
                "surface": str(row.surface),
                "player1": str(row.p1_name),
                "player2": str(row.p2_name),
                "prob1": prob1,
                "prob2": 1.0 - prob1,
                "winner": actual_winner,
            })
        return {"matches": results[:limit]}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/weather")
def get_weather(tourney_name: str, date: str | None = None) -> dict:
    from features.weather import get_live_weather
    result = get_live_weather(tourney_name, date)
    if not result:
        return {"error": f"Location unknown for tournament: {tourney_name}"}
    return _sanitize_nan({"tourney_name": tourney_name, "weather": result})


class LiveOddsRequest(BaseModel):
    player1: str
    player2: str
    surface: str | None = None


@app.post("/api/live-odds")
def get_live_odds(req: LiveOddsRequest) -> dict:
    from features.live_odds import LiveOddsScraper
    scraper = LiveOddsScraper()
    result = scraper.get_match_odds(req.player1, req.player2, req.surface)
    return _sanitize_nan(result)


class ValueBetRequest(BaseModel):
    player1: str = Field(..., min_length=1, max_length=128)
    player2: str = Field(..., min_length=1, max_length=128)
    surface: str | None = Field(default=None, max_length=32)
    model_prob1: float | None = Field(default=None, ge=0.0, le=1.0)
    model: str = Field(default="atp_stacking_model.pkl", max_length=128)
    min_edge: float = Field(default=0.05, ge=0.0, le=1.0)


@app.post("/api/value-bets")
def get_value_bets(req: ValueBetRequest) -> dict:
    from features.live_odds import compute_value_bets

    if req.model_prob1 is None:
        try:
            pred_req = PredictRequest(
                player1=req.player1,
                player2=req.player2,
                surface=req.surface or "Hard",
                model=req.model,
            )
            pred = predict_match(pred_req)
            if "error" in pred:
                return {"error": pred["error"]}
            model_prob1 = float(pred["prob1"])
        except HTTPException:
            raise
        except Exception as e:
            return {
                "error": (
                    f"Impossibile calcolare model_prob1: {e}. "
                    "Specifica model_prob1 manualmente."
                )
            }
    else:
        model_prob1 = req.model_prob1

    result = compute_value_bets(
        model_prob1, req.player1, req.player2,
        req.surface, req.min_edge,
    )
    return _sanitize_nan(result)


class PlayerNewsRequest(BaseModel):
    player1: str
    player2: str
    surface: str | None = None


@app.post("/api/player-news")
def get_player_news(req: PlayerNewsRequest) -> dict:
    from features.player_news import PlayerNewsResearcher
    researcher = PlayerNewsResearcher()
    result = researcher.research_matchup(req.player1, req.player2, req.surface)
    return _sanitize_nan(result)


@app.get("/api/todays-matches")
def get_todays_matches(tour: str = "atp") -> dict:
    """Return today's matches, cached with stale-while-revalidate.

    Fetching from SofaScore/TheOddsAPI can take 30-60s, which blows past
    the Next.js proxy timeout (~30s). A background thread re-fetches in
    the background so callers always get a fast cached response.
    """
    from features.live_odds import LiveOddsScraper
    scraper = LiveOddsScraper()
    result = scraper.get_todays_matches_cached(tour)
    return _sanitize_nan({"tour": tour, "count": len(result), "matches": result})


@app.get("/api/metrics")
def get_metrics(tour: str = "atp") -> Response:
    if tour not in ("atp", "wta", "atp_odds", "wta_odds"):
        raise HTTPException(status_code=400, detail="Invalid tour")
    metrics_path = REPORTS_DIR / tour / "metrics_summary.csv"
    if not metrics_path.exists():
        return Response(content="metric,test,val\n", media_type="text/csv")
    return Response(
        content=metrics_path.read_text(encoding="utf-8"),
        media_type="text/csv",
    )


_CHART_FILES = [
    {"name": "ROC Curve", "file": "1_roc_curve.png"},
    {"name": "Calibration Curve", "file": "2_calibration_curve.png"},
    {"name": "Feature Importance", "file": "3_feature_importance.png"},
    {"name": "SHAP Summary", "file": "4_shap_summary.png"},
    {"name": "Brier Monthly", "file": "5_brier_monthly.png"},
]
_CHART_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+\.png$")


@app.get("/api/charts")
def list_charts(tour: str = "atp") -> dict:
    """List evaluation chart PNGs for a tour (used by dashboard / reports)."""
    if tour not in ("atp", "wta", "atp_odds", "wta_odds"):
        raise HTTPException(status_code=400, detail="Invalid tour")
    tour_dir = REPORTS_DIR / tour
    charts = []
    for c in _CHART_FILES:
        path = tour_dir / c["file"]
        charts.append({
            "name": c["name"],
            "file": c["file"],
            "exists": path.is_file(),
        })
    return {"tour": tour, "charts": charts}


@app.get("/api/charts/{name}")
def get_chart(name: str, tour: str = "atp") -> Response:
    """Serve a single evaluation chart PNG from reports/{tour}/."""
    if tour not in ("atp", "wta", "atp_odds", "wta_odds"):
        raise HTTPException(status_code=400, detail="Invalid tour")
    if not _CHART_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="Invalid chart name")
    tour_dir = (REPORTS_DIR / tour).resolve()
    file_path = (tour_dir / name).resolve()
    if not str(file_path).startswith(str(tour_dir)):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Chart not found")
    return Response(
        content=file_path.read_bytes(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=60"},
    )


_SURFACE_HINTS = [
    ("wimbledon", "Grass"), ("queen", "Grass"), ("halle", "Grass"),
    ("eastbourne", "Grass"), ("newport", "Grass"), ("stuttgart", "Grass"),
    ("roland garros", "Clay"), ("french open", "Clay"), ("monte carlo", "Clay"),
    ("madrid", "Clay"), ("rome", "Clay"), ("hamburg", "Clay"),
    ("bastad", "Clay"), ("gstaad", "Clay"), ("umag", "Clay"),
    ("kitzbuhel", "Clay"), ("cordoba", "Clay"), ("buenos aires", "Clay"),
    ("rio", "Clay"), ("santiago", "Clay"), ("marrakech", "Clay"),
    ("geneva", "Clay"), ("lyon", "Clay"), ("munich", "Clay"),
    ("estoril", "Clay"), ("bucharest", "Clay"), ("boerg", "Clay"),
]


def _infer_surface(tournament: str) -> str:
    """Best-effort surface from the tournament name (default Hard)."""
    t = (tournament or "").lower()
    for keyword, surface in _SURFACE_HINTS:
        if keyword in t:
            return surface
    return "Hard"


def _log_card_predictions(tour: str, model_name: str, predictions: list[dict]) -> int:
    """Append card predictions to the Track Record, skipping duplicates.

    A prediction already present with the same player pair, surface,
    probability and odds is not re-logged, so regenerating the same card is
    idempotent while price/probability moves still produce new entries.
    """
    from pipeline.track import log_prediction, read_log

    existing = {
        (
            str(r.get("player1")), str(r.get("player2")),
            str(r.get("surface")), r.get("prob1"),
            r.get("odds1"), r.get("odds2"),
        )
        for r in read_log(tour)
    }
    n_logged = 0
    for p in predictions:
        if p.get("error") or p.get("prob1") is None:
            continue
        key = (
            p["player1"], p["player2"], p["surface"],
            round(float(p["prob1"]), 4), p.get("odds1"), p.get("odds2"),
        )
        if key in existing:
            continue
        try:
            log_prediction(
                tour=tour,
                model=model_name,
                player1=p["player1"],
                player2=p["player2"],
                surface=p["surface"],
                best_of=3,
                prob1=float(p["prob1"]),
                predicted_winner=p["winner"],
                reliability=p.get("reliability"),
                odds1=p.get("odds1"),
                odds2=p.get("odds2"),
            )
            existing.add(key)
            n_logged += 1
        except Exception as exc:
            print(f"[track] card log skipped: {exc}")
    return n_logged


def _enrich_card_predictions(predictions: list[dict]) -> None:
    """Attach weather to every card prediction in place.

    Cheap (open-meteo, free, no key) and silent on failure so the daily card
    stays usable when weather coords are unknown. Network-bound work runs in
    a small thread pool so a 20-match card finishes in ~1s.

    Player-news context (injuries, form, coach change) is NOT included here:
    the GPT Researcher pipeline is multi-second per match and incurs LLM
    cost. Per-match news is still available via the manual Player News
    Research panel on the Live Market page.
    """
    if not predictions:
        return
    from concurrent.futures import ThreadPoolExecutor

    def _weather_for(p: dict) -> dict | None:
        try:
            from features.weather import get_live_weather
            w = get_live_weather(
                p.get("tournament", ""),
                (p.get("commence_time") or "")[:10] or None,
            )
            if not w:
                return None
            return {
                "temperature_c": w.get("temperature_c"),
                "humidity_pct": w.get("humidity_pct"),
                "rain_probability": w.get("rain_probability"),
                "wind_speed_kmh": w.get("wind_speed_kmh"),
            }
        except Exception:
            return None

    valid = [p for p in predictions if not p.get("error")]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for p, w in zip(valid, pool.map(_weather_for, valid)):
            if w:
                p["weather"] = w


@app.get("/api/predict-card")
def get_predict_card(
    tour: str = "atp", min_edge: float = 0.05, limit: int = 100, log: bool = False
) -> dict:
    """Automatically predict EVERY match of the day for a tour (ATP or WTA).

    Uses the cached live feed (TheOddsAPI) so no extra API quota is spent,
    then runs live tracker-state inference per match with the market odds
    already available. Returns model probability, edge vs market implied
    probability, reliability and a value-bet flag per match.

    ``log=True`` also appends every prediction to the certified Track Record
    (deduplicated on player1/player2/surface/prob/odds, so regenerating the
    same card does not create duplicates).
    """
    if tour not in ("atp", "wta"):
        raise HTTPException(status_code=400, detail="Invalid tour")
    try:
        from features.live_odds import LiveOddsScraper
        matches = LiveOddsScraper().get_todays_matches_cached(tour)
        if not matches:
            return {
                "tour": tour, "count": 0, "model_used": None,
                "predictions": [],
                "message": "Nessun match live trovato per oggi (feed TheOddsAPI vuoto).",
            }
        model_name = f"{tour}_model_odds.pkl"
        model_path = _resolve_model_path(model_name)
        if not model_path.exists():
            model_name = f"{tour}_model.pkl"
            model_path = _resolve_model_path(model_name)
        if not model_path.exists():
            return {"tour": tour, "count": 0, "predictions": [],
                    "message": f"Nessun modello trovato per {tour}."}
        bundle = joblib.load(model_path)
        state = _load_state(tour)
        if state is None:
            return {"tour": tour, "count": 0, "predictions": [],
                    "message": "Inference state non trovato. Esegui `python backend/src/main.py features`."}

        predictions: list = []
        for m in matches[:max(1, int(limit))]:
            p1 = str(m.get("player1", "")).strip()
            p2 = str(m.get("player2", "")).strip()
            if not p1 or not p2:
                continue
            surface = _infer_surface(m.get("tournament", ""))
            best = m.get("best_odds", {}) or {}
            o1 = best.get("player1")
            o2 = best.get("player2")
            o1 = float(o1) if o1 and o1 > 1 else None
            o2 = float(o2) if o2 and o2 > 1 else None
            req = PredictRequest(
                player1=p1, player2=p2, surface=surface,
                model=model_name, best_of=3, odds1=o1, odds2=o2,
            )
            try:
                res = _predict_with_state(bundle, state, req)
            except Exception as e:
                res = {"error": str(e)}
            if "error" in res:
                predictions.append({
                    "match": f"{p1} vs {p2}", "tournament": m.get("tournament", ""),
                    "surface": surface, "commence_time": m.get("commence_time", ""),
                    "error": res["error"],
                })
                continue
            prob1 = float(res["prob1"])
            prob2 = float(res["prob2"])
            edge1 = None
            edge2 = None
            value_bet = None
            if o1 and o2 and o1 > 1 and o2 > 1:
                raw1, raw2 = 1.0 / o1, 1.0 / o2
                imp1 = raw1 / (raw1 + raw2)
                imp2 = raw2 / (raw1 + raw2)
                edge1 = prob1 - imp1
                edge2 = prob2 - imp2
                if edge1 >= min_edge:
                    value_bet = {"player": p1, "odds": o1, "edge": round(edge1, 4)}
                elif edge2 >= min_edge:
                    value_bet = {"player": p2, "odds": o2, "edge": round(edge2, 4)}
            predictions.append({
                "match": f"{p1} vs {p2}",
                "player1": p1,
                "player2": p2,
                "tournament": m.get("tournament", ""),
                "surface": surface,
                "commence_time": m.get("commence_time", ""),
                "prob1": prob1,
                "prob2": prob2,
                "winner": res.get("winner"),
                "reliability": res.get("reliability", "bassa"),
                "odds1": o1,
                "odds2": o2,
                "edge1": round(edge1, 4) if edge1 is not None else None,
                "edge2": round(edge2, 4) if edge2 is not None else None,
                "value_bet": value_bet,
            })
        _enrich_card_predictions(predictions)
        n_value = sum(1 for p in predictions if p.get("value_bet"))
        n_logged = 0
        if log:
            n_logged = _log_card_predictions(tour, model_name, predictions)
        return {
            "tour": tour,
            "count": len(predictions),
            "n_value_bets": n_value,
            "n_logged": n_logged,
            "model_used": model_name,
            "min_edge": min_edge,
            "predictions": predictions,
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"tour": tour, "count": 0, "predictions": [], "message": str(e)}


@app.get("/api/odds-api-status")
def check_odds_api_status() -> dict:
    """Check if TheOddsAPI key is configured and working."""
    api_key = os.environ.get("ODDS_API_KEY", "").strip()
    env_path = BASE_DIR / ".env"
    local_path = BASE_DIR / "local.env"
    preferred = str(local_path if local_path.is_file() else env_path)
    if not api_key or api_key == "your_api_key_here":
        return {
            "configured": False,
            "message": (
                "ODDS_API_KEY not set. Edit local.env (or .env) in the project root "
                "with your key from https://the-odds-api.com, then restart the API."
            ),
            "how_to_get": (
                "1) Go to https://the-odds-api.com  2) Sign up free  "
                "3) Copy your API key  4) Paste in local.env as ODDS_API_KEY=your_key  "
                "5) Restart: python api_server.py"
            ),
            "free_tier": "500 requests/month",
            "env_file": preferred,
            "env_candidates": [str(env_path), str(local_path)],
        }
    try:
        import requests
        url = "https://api.the-odds-api.com/v4/sports/"
        resp = requests.get(url, params={"apiKey": api_key}, timeout=10)
        if resp.status_code == 200:
            sports = resp.json()
            tennis = [s for s in sports if s.get("key", "").startswith("tennis_")]
            return {
                "configured": True,
                "status": "OK",
                "remaining_requests": resp.headers.get("x-requests-remaining", "unknown"),
                "tennis_tournaments": len(tennis),
                "tennis_keys": [s["key"] for s in tennis[:10]],
            }
        return {
            "configured": True,
            "status": f"Error {resp.status_code}",
            "message": "API key may be invalid or expired",
        }
    except Exception as e:
        return {"configured": True, "status": "Error", "message": str(e)}


if __name__ == "__main__":
    import threading
    import uvicorn

    def _warmup() -> None:
        """Pre-fetch today's matches in the background so the dashboard
        never hits the 30s Next.js proxy timeout on first load."""
        try:
            from features.live_odds import LiveOddsScraper
            scraper = LiveOddsScraper()
            for tour in ("atp", "wta"):
                try:
                    scraper.get_todays_matches_cached(tour)
                except Exception as e:
                    print(f"Warmup {tour} failed: {e}")
        except Exception as e:
            print(f"Warmup failed: {e}")

    print(f"TennisBot API listening on http://127.0.0.1:{API_PORT}")
    threading.Thread(target=_warmup, name="warmup-matches", daemon=True).start()
    uvicorn.run("api_server:app", host="127.0.0.1", port=API_PORT, reload=False)
