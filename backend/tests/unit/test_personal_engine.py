"""Chronology, honest availability, and durable pre-match tracking guarantees."""

from datetime import datetime, timedelta, timezone
import sqlite3

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from api.personal_engine import load_version
from features.personal_schedule import Fixture, Scoreboard, decimal_odds, parse_fixtures
from pipeline.personal_data import build_dataset
from pipeline.personal_state import Player, match_vector, update_ratings
from pipeline.personal_tracking import (
    Prediction,
    connect,
    read_predictions,
    record_prediction,
)
from pipeline.personal_model import raw_probability, reversed_features
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression


def fixture():
    now = datetime.now(timezone.utc)
    return Fixture(
        id="test:1",
        tour="atp",
        player1="Player One",
        player2="Player Two",
        tournament="Test event",
        commence_time=now + timedelta(days=1),
        source="unit-test fixture",
        fetched_at=now,
        surface="Hard",
    )


def prediction():
    return Prediction(
        fixture=fixture(),
        model_version="unit-test-version",
        model_family="test",
        prob1=0.7,
        prob2=0.3,
        elo_prob1=0.6,
        winner="Player One",
        predicted_at=datetime.now(timezone.utc),
        data_through="2025-12-01",
        history_age_days=300,
    )


def test_same_date_results_cannot_leak_into_features():
    frame = pd.DataFrame(
        [
            {
                "winner_id": 1,
                "loser_id": 2,
                "winner_name": "One",
                "loser_name": "Two",
                "surface": "Hard",
                "best_of": 3,
                "date": pd.Timestamp("2020-01-01"),
            },
            {
                "winner_id": 1,
                "loser_id": 3,
                "winner_name": "One",
                "loser_name": "Three",
                "surface": "Hard",
                "best_of": 3,
                "date": pd.Timestamp("2020-01-01"),
            },
            {
                "winner_id": 1,
                "loser_id": 2,
                "winner_name": "One",
                "loser_name": "Two",
                "surface": "Hard",
                "best_of": 3,
                "date": pd.Timestamp("2020-01-08"),
            },
        ]
    )
    dataset, _ = build_dataset(frame)
    assert dataset.iloc[0].features[0] == dataset.iloc[1].features[0] == 0
    assert dataset.iloc[2].features[0] == 0
    later = frame.iloc[[-1]].copy()
    later["date"] = pd.Timestamp("2020-01-29")
    mature, _ = build_dataset(pd.concat([frame, later], ignore_index=True))
    assert mature.iloc[-1].features[0] > 0
    changed = frame.copy()
    changed.loc[2, ["winner_id", "loser_id"]] = [2, 1]
    alternate, _ = build_dataset(changed)
    np.testing.assert_array_equal(
        dataset.iloc[:2].features.tolist(), alternate.iloc[:2].features.tolist()
    )


def test_surface_ratings_and_feature_order_are_real_and_symmetric():
    first, second = Player("One"), Player("Two")
    update_ratings(first, second, "Clay")
    assert first.surface_elo["Clay"] > 1500 > second.surface_elo["Clay"]
    assert first.surface_elo.get("Grass", 1500) == 1500
    forward, reverse = match_vector(first, second, "Clay"), match_vector(
        second, first, "Clay"
    )
    np.testing.assert_allclose(np.asarray(forward[:10]), -np.asarray(reverse[:10]))
    assert forward[10:] == reverse[10:]


def test_machine_probability_is_invariant_to_player_order():
    random = np.random.default_rng(42)
    features = random.normal(size=(100, 15))
    labels = (features[:, 0] > 0).astype(int)
    estimator = make_pipeline(LogisticRegression()).fit(features, labels)
    forward = raw_probability(estimator, features)
    reverse = raw_probability(estimator, reversed_features(features))
    np.testing.assert_allclose(forward + reverse, 1.0, atol=1e-12)


def test_tracking_survives_reopen_and_refuses_mutation(tmp_path):
    path = tmp_path / "events.sqlite3"
    original = prediction()
    stored = record_prediction(original, path)
    repeated = record_prediction(
        original.model_copy(update={"predicted_at": datetime.now(timezone.utc)}), path
    )
    assert stored.tracking_id == repeated.tracking_id
    assert stored.predicted_at == repeated.predicted_at
    assert len(read_predictions(path=path)) == 1
    changed_odds = original.model_copy(deep=True)
    changed_odds.fixture.odds1 = 1.7
    changed_odds.fixture.odds2 = 2.2
    record_prediction(changed_odds, path)
    assert len(read_predictions(path=path)) == 2
    database = connect(path)
    for query in [
        "DELETE FROM prediction_events",
        "UPDATE prediction_events SET model_version = 'changed'",
    ]:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            database.execute(query)
    database.close()


def test_tracking_rejects_post_start_and_invalid_probabilities(tmp_path):
    original = prediction()
    original.fixture.commence_time = datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(ValueError, match="post-start"):
        record_prediction(original, tmp_path / "events.sqlite3")
    with pytest.raises(ValidationError):
        Prediction(**{**prediction().model_dump(), "prob1": 1.2})
    with pytest.raises(ValidationError, match="sum to one"):
        Prediction(**{**prediction().model_dump(), "prob1": 0.4})


@pytest.mark.parametrize(
    "state,slug,offset,names,count",
    [
        ("pre", "mens-singles", 1, ["One", "Two"], 1),
        ("post", "mens-singles", 1, ["One", "Two"], 0),
        ("in", "mens-singles", 1, ["One", "Two"], 0),
        ("pre", "mens-doubles", 1, ["One", "Two"], 0),
        ("pre", "mens-singles", -1, ["One", "Two"], 0),
        ("pre", "mens-singles", 1, ["TBD", "Two"], 0),
    ],
)
def test_schedule_filters_completed_live_doubles_past_and_unknown(
    state, slug, offset, names, count
):
    now = datetime.now(timezone.utc)
    data = {
        "events": [
            {
                "id": "315-2026",
                "name": "Shanghai",
                "groupings": [
                    {
                        "grouping": {"slug": slug},
                        "competitions": [
                            {
                                "id": "123",
                                "date": (now + timedelta(days=offset)).isoformat(),
                                "status": {
                                    "type": {"state": state, "name": "STATUS_SCHEDULED"}
                                },
                                "competitors": [
                                    {"athlete": {"displayName": name}} for name in names
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    assert len(parse_fixtures(Scoreboard.model_validate(data), "atp", now)) == count


def test_model_loader_rejects_path_traversal():
    with pytest.raises(ValueError, match="Invalid model version"):
        load_version("../../some-untrusted-file")


@pytest.mark.parametrize(
    "american,expected", [(150, 2.5), (-200, 1.5), (None, None), (0, None)]
)
def test_real_market_price_conversion(american, expected):
    assert decimal_odds(american) == expected
