"""Live-data routes: weather, odds, value bets and player news."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from api.predict_core import sanitize_nan
from api.schemas import LiveOddsRequest, PlayerNewsRequest, ValueBetRequest

router = APIRouter()


@router.get("/api/weather")
def get_weather(tourney_name: str, date: str | None = None) -> dict[str, Any]:
    from features.weather import get_live_weather

    result = get_live_weather(tourney_name, date)
    if not result:
        return {"error": f"Location unknown for tournament: {tourney_name}"}
    return sanitize_nan({"tourney_name": tourney_name, "weather": result})  # type: ignore[no-any-return]


@router.post("/api/live-odds")
def get_live_odds(req: LiveOddsRequest) -> dict[str, Any]:
    from features.live_odds import LiveOddsScraper

    scraper = LiveOddsScraper()
    result = scraper.get_match_odds(req.player1, req.player2, req.surface)
    return sanitize_nan(result)  # type: ignore[no-any-return]


@router.post("/api/value-bets")
def get_value_bets(req: ValueBetRequest) -> dict[str, Any]:
    from features.live_odds import compute_value_bets
    from api.routes.predict import predict_match
    from api.schemas import PredictRequest

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
        model_prob1,
        req.player1,
        req.player2,
        req.surface,
        req.min_edge,
    )
    return sanitize_nan(result)  # type: ignore[no-any-return]


@router.post("/api/player-news")
def get_player_news(req: PlayerNewsRequest) -> dict[str, Any]:
    from features.player_news import PlayerNewsResearcher

    researcher = PlayerNewsResearcher()
    result = researcher.research_matchup(req.player1, req.player2, req.surface)
    return sanitize_nan(result)  # type: ignore[no-any-return]
