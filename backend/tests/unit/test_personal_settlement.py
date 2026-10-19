"""Actual outcomes are separate immutable events, never retrospective predictions."""

from datetime import datetime, timedelta, timezone
import sqlite3

import pandas as pd
import pytest

from features.personal_results import MatchOutcome, parse_outcomes
from features.personal_schedule import Fixture, Scoreboard
from pipeline.personal_settlement import (
    append_outcomes,
    initialize_outcomes,
    live_summary,
)
from pipeline.personal_tracking import Prediction, record_prediction
from pipeline.personal_train import chronological_partitions


def make_prediction():
    now = datetime.now(timezone.utc)
    fixture = Fixture(
        id="espn:atp:123",
        tour="atp",
        player1="One",
        player2="Two",
        tournament="Example",
        commence_time=now + timedelta(days=1),
        source="unit-test",
        fetched_at=now,
        surface="Hard",
    )
    return Prediction(
        fixture=fixture,
        model_version="test-v1",
        model_family="test",
        prob1=0.7,
        prob2=0.3,
        elo_prob1=0.6,
        winner="One",
        predicted_at=now,
        data_through="2025-12-01",
        history_age_days=300,
    )


def test_year_boundary_labels_are_embargoed():
    dates = pd.to_datetime(
        [
            "2021-01-01",
            "2021-12-25",
            "2022-01-01",
            "2022-12-25",
            "2023-01-01",
            "2023-12-25",
            "2024-01-01",
            "2025-01-01",
            "2026-01-01",
        ]
    )
    frame = pd.DataFrame(
        {
            "date": dates,
            "year": dates.year,
            "available_at": dates + pd.Timedelta(days=21),
        }
    )
    train, select, calibrate, test = chronological_partitions(frame)
    assert len(train) == len(select) == len(calibrate) == 1
    assert set(test.year) == {2024, 2025}
    assert train.available_at.max() < pd.Timestamp("2022-01-01")
    assert select.available_at.max() < pd.Timestamp("2023-01-01")
    assert calibrate.available_at.max() < pd.Timestamp("2024-01-01")


def test_outcome_settlement_is_durable_idempotent_and_does_not_rewrite_forecasts(
    tmp_path, monkeypatch
):
    path = tmp_path / "private.sqlite3"
    prediction = make_prediction()
    record_prediction(prediction, path)
    repriced = prediction.model_copy(deep=True)
    repriced.fixture.odds1, repriced.fixture.odds2 = 1.7, 2.2
    record_prediction(repriced, path)
    database = initialize_outcomes(path)
    before = database.execute(
        "SELECT payload FROM prediction_events ORDER BY id"
    ).fetchall()
    database.close()
    observed = prediction.fixture.commence_time + timedelta(hours=3)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return observed + timedelta(hours=1)

    monkeypatch.setattr("pipeline.personal_settlement.datetime", Clock)
    outcome = MatchOutcome(
        fixture_id=prediction.fixture.id,
        tour="atp",
        player1="One",
        player2="Two",
        winner="One",
        status="completed",
        scheduled_start=prediction.fixture.commence_time,
        observed_at=observed,
    )
    assert append_outcomes([outcome], path) == 1
    assert append_outcomes([outcome], path) == 0
    summary = live_summary("atp", path, model_version="test-v1")
    assert summary["completed"] == 1
    assert summary["first_forecast_per_match"]["completed"] == 1
    assert summary["accuracy"] == 1.0
    assert summary["brier"] == pytest.approx(0.09)
    assert live_summary("atp", path, model_version="another-model")["accuracy"] is None
    database = initialize_outcomes(path)
    assert (
        database.execute("SELECT payload FROM prediction_events ORDER BY id").fetchall()
        == before
    )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        database.execute("DELETE FROM outcome_events")
    database.close()


def test_future_prediction_timestamps_are_rejected(tmp_path):
    prediction = make_prediction()
    prediction.predicted_at = datetime.now(timezone.utc) + timedelta(hours=1)
    with pytest.raises(ValueError, match="future prediction timestamp"):
        record_prediction(prediction, tmp_path / "private.sqlite3")


def test_wrong_players_or_future_outcome_cannot_settle_prediction(tmp_path):
    path = tmp_path / "private.sqlite3"
    prediction = make_prediction()
    record_prediction(prediction, path)
    outcome = MatchOutcome(
        fixture_id=prediction.fixture.id,
        tour="atp",
        player1="Unrelated",
        player2="Two",
        winner="Unrelated",
        status="completed",
        scheduled_start=prediction.fixture.commence_time,
        observed_at=prediction.fixture.commence_time + timedelta(hours=3),
    )
    assert append_outcomes([outcome], path) == 0
    assert live_summary("atp", path)["accuracy"] is None


@pytest.mark.parametrize(
    "state,name,completed,winners,expected",
    [
        ("post", "STATUS_FINAL", True, [True, False], "completed"),
        ("post", "STATUS_RETIRED", True, [True, False], "void"),
        ("in", "STATUS_IN_PROGRESS", False, [False, False], None),
        ("post", "STATUS_FINAL", True, [False, False], None),
    ],
)
def test_only_confirmed_completed_singles_are_settled(
    state, name, completed, winners, expected
):
    now = datetime.now(timezone.utc)
    board = Scoreboard.model_validate(
        {
            "events": [
                {
                    "id": "315",
                    "name": "Example",
                    "groupings": [
                        {
                            "grouping": {"slug": "mens-singles"},
                            "competitions": [
                                {
                                    "id": "123",
                                    "date": (now - timedelta(hours=3)).isoformat(),
                                    "status": {
                                        "type": {
                                            "state": state,
                                            "name": name,
                                            "completed": completed,
                                        }
                                    },
                                    "competitors": [
                                        {
                                            "athlete": {"displayName": player},
                                            "winner": won,
                                        }
                                        for player, won in zip(["One", "Two"], winners)
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )
    results = parse_outcomes(board, "atp", now)
    assert (results[0].status if results else None) == expected
