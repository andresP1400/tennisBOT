"""Private local personal-engine API; no model uploads or remote credentials."""

from __future__ import annotations

from typing import Literal

import requests
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from api.personal_engine import PredictionCard, get_card, load_bundle
from api.personal_status import worker_status
from pipeline.personal_tracking import Prediction, read_predictions
from pipeline.personal_settlement import live_summary

router = APIRouter()


@router.get("/api/personal/status")
def status() -> dict[str, object]:
    """Poller timestamps distinguish API liveness from successful automatic updates."""
    return worker_status()


@router.get("/api/personal/predictions", response_model=PredictionCard)
def predictions(tour: Literal["atp", "wta"] = "atp") -> PredictionCard:
    """Every returned probability has already been committed to local tracking."""
    try:
        return get_card(tour)
    except (requests.RequestException, ValidationError) as error:
        raise HTTPException(
            status_code=503,
            detail="Schedule provider is unavailable; stored predictions are preserved",
        ) from error


@router.get("/api/personal/backtest")
def backtest(tour: Literal["atp", "wta"] = "atp") -> dict[str, object]:
    """Actual held-out results of the deployed model, not marketing statistics."""
    try:
        return load_bundle(tour).report
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=503, detail="Model has not been trained"
        ) from error


@router.get("/api/personal/history", response_model=list[Prediction])
def history(limit: int = 100) -> list[Prediction]:
    """Stored pre-match snapshots survive service restarts and retraining."""
    return read_predictions(limit)


@router.get("/api/personal/live-performance")
def live_performance(
    tour: Literal["atp", "wta"] = "atp", scope: Literal["current", "all"] = "current"
) -> dict[str, object]:
    """Observed post-deployment results; no retrospective accuracy substituted."""
    try:
        if scope == "all":
            return live_summary(tour)
        return live_summary(tour, model_version=load_bundle(tour).version)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=503, detail="Model has not been trained"
        ) from error
