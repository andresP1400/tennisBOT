"""Append outcomes without modifying or deleting any recorded pre-match forecast."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from features.personal_results import MatchOutcome, parse_outcomes
from features.personal_schedule import fetch_scoreboard
from pipeline.personal_state import normalize_name
from pipeline.personal_tracking import TRACKING_DB, Prediction, connect

_last_attempt: dict[tuple[str, str], float] = {}


def initialize_outcomes(path: Path) -> sqlite3.Connection:
    """Use the existing private database with separate immutable settlement events."""
    database = connect(path)
    database.execute(
        """CREATE TABLE IF NOT EXISTS outcome_events (
        fixture_id TEXT PRIMARY KEY, observed_at TEXT NOT NULL, payload TEXT NOT NULL)"""
    )
    for operation in ("UPDATE", "DELETE"):
        database.execute(
            f"""CREATE TRIGGER IF NOT EXISTS prohibit_outcome_{operation.lower()}
            BEFORE {operation} ON outcome_events BEGIN
            SELECT RAISE(ABORT, 'Outcome events are append-only'); END"""
        )
    return database


def append_outcomes(outcomes: list[MatchOutcome], path: Path | None = None) -> int:
    """Ignore unmatched/wrong-player events and retain the first provider outcome."""
    database = initialize_outcomes(path or TRACKING_DB)
    try:
        stored = database.execute(
            "SELECT fixture_id, payload FROM prediction_events"
        ).fetchall()
        forecasts: dict[str, list[Prediction]] = {}
        for fixture_id, payload in stored:
            forecasts.setdefault(fixture_id, []).append(
                Prediction.model_validate_json(payload)
            )
        count = 0
        with database:
            for outcome in outcomes:
                if outcome.observed_at > datetime.now(timezone.utc):
                    continue
                matches = forecasts.get(outcome.fixture_id, [])
                valid = any(matches_outcome(forecast, outcome) for forecast in matches)
                if not valid:
                    continue
                cursor = database.execute(
                    "INSERT OR IGNORE INTO outcome_events VALUES (?, ?, ?)",
                    (
                        outcome.fixture_id,
                        outcome.observed_at.isoformat(),
                        outcome.model_dump_json(),
                    ),
                )
                count += cursor.rowcount
        return count
    finally:
        database.close()


def matches_outcome(forecast: Prediction, outcome: MatchOutcome) -> bool:
    """Match exact fixture ID, tour, player pair, and pre-start observation time."""
    players = {normalize_name(outcome.player1), normalize_name(outcome.player2)}
    expected = {
        normalize_name(forecast.fixture.player1),
        normalize_name(forecast.fixture.player2),
    }
    return (
        forecast.fixture.id == outcome.fixture_id
        and forecast.fixture.tour == outcome.tour
        and players == expected
        and abs(
            (forecast.fixture.commence_time - outcome.scheduled_start).total_seconds()
        )
        <= 7 * 86400
        and forecast.predicted_at < outcome.scheduled_start <= outcome.observed_at
        and (outcome.winner is None or normalize_name(outcome.winner) in players)
    )


def settle_pending(tour: str, path: Path | None = None) -> int:
    """Revisit unresolved start dates so results survive event/day transitions."""
    database = initialize_outcomes(path or TRACKING_DB)
    try:
        rows = database.execute("""SELECT p.payload FROM prediction_events p
            LEFT JOIN outcome_events o ON p.fixture_id = o.fixture_id
            WHERE o.fixture_id IS NULL""").fetchall()
    finally:
        database.close()
    now = datetime.now(timezone.utc)
    pending = [Prediction.model_validate_json(row[0]) for row in rows]
    days = sorted(
        {
            item.fixture.commence_time.strftime("%Y%m%d")
            for item in pending
            if item.fixture.tour == tour and item.fixture.commence_time <= now
        }
    )
    count = 0
    days.sort(key=lambda day: (_last_attempt.get((tour, day), 0), day))
    for day in days[:3]:
        _last_attempt[(tour, day)] = time.monotonic()
        board, observed = fetch_scoreboard(tour, day)
        count += append_outcomes(parse_outcomes(board, tour, observed), path)
    return count


def live_summary(
    tour: str, path: Path | None = None, model_version: str | None = None
) -> dict[str, object]:
    """Score first forecast per fixture/model; repeated price snapshots cannot inflate accuracy."""
    database = initialize_outcomes(path or TRACKING_DB)
    try:
        rows = database.execute(
            """SELECT p.payload, o.payload FROM prediction_events p
            LEFT JOIN outcome_events o ON p.fixture_id = o.fixture_id ORDER BY p.observed_at"""
        ).fetchall()
    finally:
        database.close()
    selected: dict[tuple[str, str], tuple[Prediction, MatchOutcome | None]] = {}
    for payload, result in rows:
        prediction = Prediction.model_validate_json(payload)
        if prediction.fixture.tour == tour and (
            model_version is None or prediction.model_version == model_version
        ):
            selected.setdefault(
                (prediction.fixture.id, prediction.model_version),
                (
                    prediction,
                    MatchOutcome.model_validate_json(result) if result else None,
                ),
            )
    return (
        summarize(selected)
        | {"model_version": model_version}
        | model_breakdown(selected)
    )


def model_breakdown(
    selected: dict[tuple[str, str], tuple[Prediction, MatchOutcome | None]],
) -> dict[str, object]:
    """Preserve first-ever fixture results alongside each immutable model version."""
    first: dict[tuple[str, str], tuple[Prediction, MatchOutcome | None]] = {}
    seen: set[str] = set()
    for key, value in selected.items():
        if key[0] not in seen:
            first[key] = value
            seen.add(key[0])
    versions = {key[1] for key in selected}
    return {
        "first_forecast_per_match": summarize(first)
        | {"scoring_rule": "First recorded forecast per unique fixture"},
        "by_model": {
            version: summarize(
                {key: value for key, value in selected.items() if key[1] == version}
            )
            for version in versions
        },
    }


def summarize(
    selected: dict[tuple[str, str], tuple[Prediction, MatchOutcome | None]],
) -> dict[str, object]:
    """Never mix live results with retrospective historical backtest measurements."""
    completed = [
        (prediction, outcome)
        for prediction, outcome in selected.values()
        if outcome
        and outcome.status == "completed"
        and matches_outcome(prediction, outcome)
    ]
    correct = sum(
        normalize_name(prediction.winner) == normalize_name(str(outcome.winner))
        for prediction, outcome in completed
    )
    brier = sum(squared_error(prediction, outcome) for prediction, outcome in completed)
    return {
        "forecast_model_pairs": len(selected),
        "completed": len(completed),
        "unique_completed_matches": len(
            {prediction.fixture.id for prediction, _ in completed}
        ),
        "correct": correct,
        "accuracy": correct / len(completed) if completed else None,
        "brier": brier / len(completed) if completed else None,
        "void": sum(
            outcome is not None and outcome.status == "void"
            for _, outcome in selected.values()
        ),
        "pending": sum(
            outcome is None or not matches_outcome(prediction, outcome)
            for prediction, outcome in selected.values()
        ),
        "scoring_rule": "First pre-match forecast per fixture and model version",
    }


def squared_error(prediction: Prediction, outcome: MatchOutcome) -> float:
    """Score stored probabilities against the observed winner in the same orientation."""
    label = float(
        normalize_name(prediction.fixture.player1)
        == normalize_name(str(outcome.winner))
    )
    return (prediction.prob1 - label) ** 2
