"""Automatic daily card route: predict every match of the day."""

from __future__ import annotations

import joblib
from typing import Any

from fastapi import APIRouter, HTTPException

from api.card_core import (
    build_card_predictions,
    enrich_card_predictions,
    log_card_predictions,
    resolve_card_model,
)
from api.state import load_state

router = APIRouter()


@router.get("/api/predict-card")
def get_predict_card(
    tour: str = "atp", min_edge: float = 0.05, limit: int = 100, log: bool = False
) -> dict[str, Any]:
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
                "tour": tour,
                "count": 0,
                "model_used": None,
                "predictions": [],
                "message": "Nessun match live trovato per oggi (feed TheOddsAPI vuoto).",
            }
        model_name, model_path = resolve_card_model(tour)
        if model_path is None:
            return {
                "tour": tour,
                "count": 0,
                "predictions": [],
                "message": f"Nessun modello trovato per {tour}.",
            }
        bundle = joblib.load(model_path)
        state = load_state(tour)
        if state is None:
            return {
                "tour": tour,
                "count": 0,
                "predictions": [],
                "message": "Inference state non trovato. Esegui `python backend/src/main.py features`.",
            }

        predictions = build_card_predictions(
            bundle, state, matches, model_name, min_edge, limit
        )
        enrich_card_predictions(predictions, tour)
        n_value = sum(1 for p in predictions if p.get("value_bet"))
        n_logged = 0
        if log:
            n_logged = log_card_predictions(tour, model_name, predictions)
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
    except Exception as e:  # noqa: BLE001
        return {"tour": tour, "count": 0, "predictions": [], "message": str(e)}
