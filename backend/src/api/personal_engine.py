"""Generate and record genuine upcoming predictions from local versioned models."""

from __future__ import annotations

import json
import re
import threading
import time
from datetime import date, datetime, timezone
from functools import lru_cache

import joblib
import numpy as np
from pydantic import BaseModel, Field

from config import MODELS_DIR
from features.personal_schedule import Fixture, fetch_fixtures
from pipeline.personal_model import PersonalBundle, calibrate, elo_raw, raw_probability
from pipeline.personal_state import match_vector, normalize_name
from pipeline.personal_tracking import Prediction, record_prediction
from pipeline.personal_settlement import live_summary


class Unavailable(BaseModel):
    fixture: Fixture
    reason: str


class PredictionCard(BaseModel):
    tour: str
    model_version: str | None = None
    fetched_at: datetime
    predictions: list[Prediction] = Field(default_factory=list)
    unavailable: list[Unavailable] = Field(default_factory=list)
    message: str | None = None
    backtest: dict[str, object] = Field(default_factory=dict)
    live_performance: dict[str, object] = Field(default_factory=dict)
    overall_live_performance: dict[str, object] = Field(default_factory=dict)


_cache: dict[str, tuple[float, PredictionCard]] = {}
_lock = threading.Lock()


@lru_cache(maxsize=4)
def load_version(version: str) -> PersonalBundle:
    """Only generated local filenames can select trusted model artifacts."""
    if not re.fullmatch(r"(atp|wta)-\d{8}T\d{12}Z-[a-f0-9]{12}", version):
        raise ValueError("Invalid model version")
    bundle = joblib.load(MODELS_DIR / "personal" / f"{version}.joblib")
    if not isinstance(bundle, PersonalBundle):
        raise ValueError("Unexpected model artifact")
    return bundle


def load_bundle(tour: str) -> PersonalBundle:
    """A newly trained version automatically replaces the cached active pointer."""
    if tour not in ("atp", "wta"):
        raise ValueError("Expected ATP or WTA")
    pointer = json.loads((MODELS_DIR / "personal" / f"{tour}-latest.json").read_text())
    return load_version(str(pointer["version"]))


def predict_fixture(bundle: PersonalBundle, fixture: Fixture) -> Prediction:
    """Unknown players/surfaces remain unavailable, never substituted with 50%."""
    if fixture.tour != bundle.tour or fixture.surface is None:
        raise ValueError("Surface is unverified for this tournament")
    first_id = bundle.names.get(normalize_name(fixture.player1))
    second_id = bundle.names.get(normalize_name(fixture.player2))
    if first_id is None or second_id is None or first_id == second_id:
        raise ValueError("One or both players lack unambiguous historical coverage")
    first, second = bundle.players[first_id], bundle.players[second_id]
    if min(first.count, second.count) < 10:
        raise ValueError("Insufficient completed historical matches for this matchup")
    features = np.asarray([match_vector(first, second, fixture.surface)], dtype=float)
    prob1 = float(
        calibrate(bundle.calibrator, raw_probability(bundle.estimator, features))[0]
    )
    elo_prob = float(calibrate(bundle.elo_calibrator, elo_raw(features))[0])
    age = (
        datetime.now(timezone.utc).date() - date.fromisoformat(bundle.data_through)
    ).days
    prediction = Prediction(
        fixture=fixture,
        model_version=bundle.version,
        model_family=bundle.family,
        prob1=prob1,
        prob2=1 - prob1,
        elo_prob1=elo_prob,
        winner=fixture.player1 if prob1 >= 0.5 else fixture.player2,
        predicted_at=datetime.now(timezone.utc),
        data_through=bundle.data_through,
        history_age_days=age,
        warning=(
            f"Historical results are {age} days old; recent form/rankings are missing"
            if age > 30
            else None
        ),
    )
    return record_prediction(prediction)


def generate_card(tour: str) -> PredictionCard:
    """Refresh schedules without deleting predictions on outages or model changes."""
    now = datetime.now(timezone.utc)
    try:
        bundle = load_bundle(tour)
    except FileNotFoundError:
        return PredictionCard(
            tour=tour,
            fetched_at=now,
            message="No trained model. Run python -m pipeline.personal_train --tour both.",
        )
    card = PredictionCard(
        tour=tour,
        model_version=bundle.version,
        fetched_at=now,
        backtest=dict(bundle.report),
    )
    for fixture in fetch_fixtures(tour):
        try:
            card.predictions.append(predict_fixture(bundle, fixture))
        except ValueError as error:
            card.unavailable.append(Unavailable(fixture=fixture, reason=str(error)))
    attach_live_performance(card)
    if not card.predictions:
        card.message = "No covered upcoming matches with confirmed surfaces are currently available."
    return card


def attach_live_performance(card: PredictionCard) -> None:
    """Current-version results never erase the recorded performance of earlier versions."""
    card.live_performance = live_summary(card.tour, model_version=card.model_version)
    overall = live_summary(card.tour)["first_forecast_per_match"]
    if not isinstance(overall, dict):
        raise RuntimeError("Invalid live performance summary")
    card.overall_live_performance = {str(key): value for key, value in overall.items()}


def get_card(tour: str, refresh: bool = False) -> PredictionCard:
    """Bound schedule traffic; never serve predictions after their scheduled start."""
    with _lock:
        cached = _cache.get(tour)
        if not refresh and cached and time.monotonic() - cached[0] < 300:
            card = cached[1].model_copy(deep=True)
            now = datetime.now(timezone.utc)
            card.predictions = [
                item for item in card.predictions if item.fixture.commence_time > now
            ]
            attach_live_performance(card)
            return card
        card = generate_card(tour)
        _cache[tour] = (time.monotonic(), card)
        return card
