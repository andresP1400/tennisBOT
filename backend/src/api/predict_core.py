"""Shared inference helpers used by the predict / predict-card / track routes.

Pure functions only (no route decorators): model resolution, NaN sanitising,
historical-row feature building, live tracker-state inference, prediction
logging and market-odds autofill.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException

from config import MODELS_DIR
from logging_config import get_logger
from api.schemas import PredictRequest
from pipeline.symmetric_calibration import symmetric_calibration

log = get_logger(__name__)

# Accept pure-stats stacking, pure alias, and market-aware variants
MODEL_NAME_PATTERN = re.compile(r"^(atp|wta)_(stacking_model|model|model_odds)\.pkl$")


def sanitize_nan(obj: Any) -> Any:
    """Convert NaN/inf floats to None so JSON serialization doesn't crash."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_nan(v) for v in obj]
    if isinstance(obj, np.floating) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if isinstance(obj, np.integer):
        return int(obj)
    return obj


def resolve_model_path(model_name: str) -> Path:
    """Resolve a model filename to an absolute path under MODELS_DIR, validated."""
    if not MODEL_NAME_PATTERN.match(model_name):
        raise HTTPException(status_code=400, detail="Invalid model name")
    candidate = (MODELS_DIR / model_name).resolve()
    models_root = MODELS_DIR.resolve()
    # Robust containment check (avoids the string-prefix pitfall where a
    # sibling like ``/models_evil`` would satisfy ``startswith('/models')``).
    try:
        candidate.relative_to(models_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model path")
    return candidate


def predict_proba_from_features(
    bundle: Any, df_fake: pd.DataFrame, calibrated: bool = True
) -> float:
    X_imp = bundle["imputer"].transform(df_fake.values)
    X_scaled = bundle["scaler"].transform(X_imp)
    p_lgbm = bundle["base_models"]["lgbm"].predict_proba(X_scaled)[:, 1]
    p_xgb = bundle["base_models"]["xgb"].predict_proba(X_scaled)[:, 1]
    p_lr = bundle["base_models"]["lr"].predict_proba(X_scaled)[:, 1]
    X_meta = np.column_stack([p_lgbm, p_xgb, p_lr])
    raw_prob = bundle["meta_model"].predict_proba(X_meta)[:, 1][0]
    if calibrated and bundle.get("calibrator") is not None:
        return float(
            symmetric_calibration(np.asarray([raw_prob]), bundle["calibrator"])[0]
        )
    return float(raw_prob)


def predict_with_state(bundle: Any, state: Any, req: PredictRequest) -> dict[str, Any]:
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
        state,
        feature_cols,
        snap1,
        snap2,
        id1,
        id2,
        req.surface,
        best_of=best_of,
        odds_a=req.odds1,
        odds_b=req.odds2,
        now=now,
    )
    row_rev = build_match_features(
        state,
        feature_cols,
        snap2,
        snap1,
        id2,
        id1,
        req.surface,
        best_of=best_of,
        odds_a=req.odds2,
        odds_b=req.odds1,
        now=now,
    )
    prob_fwd = predict_proba_from_features(bundle, row_fwd, calibrated=False)
    prob_rev = predict_proba_from_features(bundle, row_rev, calibrated=False)
    raw = np.asarray([(prob_fwd + 1 - prob_rev) / 2], dtype=float)
    final_prob = float(symmetric_calibration(raw, bundle.get("calibrator"))[0])

    h2h = (
        state["h2h"].get_h2h(id1, id2, req.surface)
        if (id1 is not None and id2 is not None)
        else {"h2h_win_pct": None, "h2h_total_matches": 0}
    )
    h2h_total = h2h.get("h2h_total_matches", 0)
    if not isinstance(h2h_total, int):
        h2h_total = 0
    reliability = assess_reliability(
        snap1,
        snap2,
        h2h_total,
        id1 is not None,
        id2 is not None,
    )
    prob1 = float(np.clip(final_prob, 0, 1))
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
                None
                if h2h_pct is None or (isinstance(h2h_pct, float) and np.isnan(h2h_pct))
                else round(float(h2h_pct), 3)
            ),
            "total_matches": h2h_total,
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


def maybe_log_prediction(req: PredictRequest, result: dict[str, Any]) -> None:
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
        log.warning("track log skipped: %s", exc)


def autofill_odds(req: PredictRequest) -> PredictRequest:
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
        o1 = (
            None
            if o1 is None or (isinstance(o1, float) and math.isnan(o1))
            else float(o1)
        )
        o2 = (
            None
            if o2 is None or (isinstance(o2, float) and math.isnan(o2))
            else float(o2)
        )
        return req.model_copy(
            update={
                "odds1": req.odds1 if req.odds1 is not None else o1,
                "odds2": req.odds2 if req.odds2 is not None else o2,
            }
        )
    except Exception as exc:
        log.debug("odds autofill skipped: %s", exc)
        return req
