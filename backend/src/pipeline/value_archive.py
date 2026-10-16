"""Durably archive every qualifying decision against its actual stored evidence."""

from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
from features.value_contracts import ValueSelection, ValueCandidate
from features.market_contracts import MarketQuote
from features.market_comparison import same_fixture
from pipeline.personal_tracking import Prediction
from pipeline.market_store import market_connect, append_record


def append_selection(selection: ValueSelection, path: Path | None = None) -> str:
    """Repeated unchanged decisions retain the first observation rather than inflate results."""
    candidate = selection.candidate
    if datetime.now(timezone.utc) >= candidate.fixture.commence_time:
        raise ValueError("Cannot archive a new selection after match start")
    validate_archived_selection(selection, path)
    identity = json.dumps(
        [
            selection.category,
            candidate.policy_version,
            candidate.prediction_id,
            candidate.side,
            candidate.quote_id,
        ]
    )
    return append_record(
        "value_selections", selection, candidate.fixture.id, path, identity
    )


def validate_archived_selection(
    selection: ValueSelection, path: Path | None = None
) -> None:
    """ROI can use only an existing actual forecast and a saved matching pre-match price."""
    candidate = selection.candidate
    prediction, quote = read_selection_evidence(candidate, path)
    side1 = candidate.side == "player1"
    valid = (
        candidate.qualifies_a if selection.category == "A" else candidate.qualifies_b
    )
    valid = (
        valid
        and same_fixture(prediction.fixture, quote.fixture)
        and same_fixture(candidate.fixture, prediction.fixture)
    )
    valid = (
        valid
        and candidate.model_version == prediction.model_version
        and quote.provenance == "theoddsapi"
    )
    valid = valid and candidate.probability == (
        prediction.prob1 if side1 else prediction.prob2
    )
    valid = valid and candidate.decimal_odds == (quote.odds1 if side1 else quote.odds2)
    valid = (
        valid
        and prediction.predicted_at
        <= candidate.evaluated_at
        <= selection.observed_at
        < quote.fixture.commence_time
    )
    valid = (
        valid
        and quote.observed_at <= candidate.evaluated_at
        and quote.kind != "closing"
    )
    if not valid:
        raise ValueError("Selection does not match its archived pre-match evidence")


def read_selection_evidence(
    candidate: ValueCandidate, path: Path | None
) -> tuple[Prediction, MarketQuote]:
    """A missing archived forecast or quote is a hard error, never an assumed price."""
    database = market_connect(path)
    try:
        forecast = database.execute(
            "SELECT payload FROM prediction_events WHERE id=?",
            (candidate.prediction_id,),
        ).fetchone()
        price = database.execute(
            "SELECT payload FROM market_quotes WHERE id=?", (candidate.quote_id,)
        ).fetchone()
    finally:
        database.close()
    if forecast is None or price is None:
        raise ValueError(
            "Selections require durably archived forecast and quote evidence"
        )
    prediction, quote = Prediction.model_validate_json(
        forecast[0]
    ), MarketQuote.model_validate_json(price[0])
    return prediction, quote
