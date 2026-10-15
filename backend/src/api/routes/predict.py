"""Single-match prediction route with live-state + historical fallback."""

from __future__ import annotations

from typing import Any

import joblib
import numpy as np
from fastapi import APIRouter, HTTPException

from api.historical_core import (
    build_feature_row,
    get_h2h_stats,
    get_player_latest_stats,
)
from api.predict_core import (
    autofill_odds,
    maybe_log_prediction,
    predict_proba_from_features,
    predict_with_state,
    resolve_model_path,
    sanitize_nan,
)
from api.schemas import PredictRequest
from pipeline.symmetric_calibration import symmetric_calibration
from api.state import load_dataset, load_state

router = APIRouter()


@router.post("/api/predict")
def predict_match(req: PredictRequest) -> dict[str, Any]:
    """Predict with live tracker state; fall back to improved historical rows."""
    try:
        model_path = resolve_model_path(req.model)
        if not model_path.exists():
            return {"error": "Modello non trovato su disco"}

        bundle = joblib.load(model_path)
        tour = "wta" if "wta" in (req.model or "").lower() else "atp"

        # Auto-fill market odds if the client did not provide them.
        req = autofill_odds(req)

        # Primary: live tracker state
        state = load_state(tour)
        if state is not None:
            result = predict_with_state(bundle, state, req)
            maybe_log_prediction(req, result)
            return sanitize_nan(result)  # type: ignore[no-any-return]

        # Fallback: full parquet (both _A and _B), surface-aware + symmetrized
        dataset = load_dataset(tour)
        if dataset is None:
            return {
                "error": "Dataset features non trovato. Esegui `python backend/src/main.py features`."
            }

        feature_cols = bundle["feature_cols"]
        p1_stats = get_player_latest_stats(req.player1, dataset)
        p2_stats = get_player_latest_stats(req.player2, dataset)
        p1_surf = get_player_latest_stats(req.player1, dataset, surface=req.surface)
        p2_surf = get_player_latest_stats(req.player2, dataset, surface=req.surface)
        h2h_12 = get_h2h_stats(req.player1, req.player2, dataset, surface=req.surface)
        h2h_21 = get_h2h_stats(req.player2, req.player1, dataset, surface=req.surface)
        best_of = req.best_of if req.best_of in (3, 5) else 3

        row_fwd = build_feature_row(
            feature_cols,
            p1_stats,
            p2_stats,
            p1_surf,
            p2_surf,
            h2h_12,
            req.surface,
            best_of,
        )
        row_rev = build_feature_row(
            feature_cols,
            p2_stats,
            p1_stats,
            p2_surf,
            p1_surf,
            h2h_21,
            req.surface,
            best_of,
        )
        prob_fwd = predict_proba_from_features(bundle, row_fwd, calibrated=False)
        prob_rev = predict_proba_from_features(bundle, row_rev, calibrated=False)
        raw = np.asarray([(prob_fwd + 1 - prob_rev) / 2], dtype=float)
        final_prob = float(symmetric_calibration(raw, bundle.get("calibrator"))[0])
        prob1 = float(np.clip(final_prob, 0, 1))
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
                []
                if has_history
                else [
                    "cold start: uno o entrambi i giocatori non trovati nello storico"
                ]
            ),
            "h2h": {
                "p1_win_pct": (
                    None
                    if np.isnan(h2h_12["h2h_win_pct"])
                    else round(float(h2h_12["h2h_win_pct"]), 3)
                ),
                "total_matches": int(h2h_12.get("h2h_total_matches", 0)),
            },
            "odds1": req.odds1,
            "odds2": req.odds2,
            "info": (
                "Fallback parquet (simmetrizzato, no bias _A) — "
                "rigenera features per inference state live"
                if has_history
                else "Cold Start - Dati Mediani"
            ),
        }
        maybe_log_prediction(req, result)
        return sanitize_nan(result)  # type: ignore[no-any-return]

    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}
