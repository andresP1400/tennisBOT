"""Surface research must obey the same delayed chronology and preserve missing values."""

from collections import deque
import numpy as np
import pandas as pd
import pytest

from pipeline.context_features import (
    ContextPlayer,
    SurfaceHistory,
    attach_context,
    context_rows,
    observe_context,
    observed_ratio,
)
from pipeline.personal_data import build_dataset


def sample_history() -> pd.DataFrame:
    rows = []
    for day, surface in (
        ("2025-01-01", "Hard"),
        ("2025-01-21", "Clay"),
        ("2025-01-22", "Hard"),
        ("2025-01-23", "Clay"),
    ):
        rows.append(
            {
                "date": pd.Timestamp(day),
                "surface": surface,
                "winner_id": 1,
                "loser_id": 2,
                "winner_name": "One",
                "loser_name": "Two",
                "best_of": 3,
                "w_1stWon": 8,
                "w_2ndWon": 0,
                "w_svpt": 10,
                "l_1stWon": 3,
                "l_2ndWon": 0,
                "l_svpt": 10,
            }
        )
    return pd.DataFrame(rows)


def test_surface_context_releases_only_matured_results_before_the_current_match() -> (
    None
):
    rows = context_rows(sample_history())
    assert np.isnan(rows.iloc[0].context_features[0])
    assert np.isnan(rows.iloc[1].context_features[0])
    assert rows.iloc[2].context_features[:3] == pytest.approx([0.5, 0.5, 1])
    assert rows.iloc[2].player1_matches == rows.iloc[2].player2_matches == 1
    assert np.isnan(rows.iloc[3].context_features[0])


def test_current_or_unmatured_result_changes_cannot_change_its_own_predictors() -> None:
    history = sample_history()
    first = context_rows(history)
    history.loc[2, ["winner_id", "loser_id"]] = [2, 1]
    history.loc[2, "w_1stWon"] = 1
    changed = context_rows(history)
    for index in range(len(first)):
        np.testing.assert_allclose(
            first.iloc[index].context_features,
            changed.iloc[index].context_features,
            equal_nan=True,
        )


def test_inactivity_is_observed_history_and_missing_or_partial_points_stay_missing() -> (
    None
):
    players = {1: ContextPlayer(), 2: ContextPlayer()}
    row = sample_history().iloc[0].copy()
    row["w_2ndWon"] = float("nan")
    observe_context(row, players)
    first = players[1].values("Hard", pd.Timestamp("2025-01-22").date())
    assert np.isnan(first[0]) and first[2] == 1
    assert first[4] == pytest.approx(np.log1p(21))
    assert players[1].count == 1
    assert np.isnan(players[1].values("Grass", pd.Timestamp("2025-01-22").date())[0])
    assert np.isnan(observed_ratio(deque()))
    assert observed_ratio(deque([(8.0, 10.0), (4.0, 10.0)])) == 0.6


def test_context_alignment_checks_dates_labels_surface_and_counts_without_mutating_baseline() -> (
    None
):
    history = sample_history()
    baseline, _ = build_dataset(history, feature_schema=2)
    original = baseline.copy(deep=True)
    enriched = attach_context(history, baseline)
    assert len(enriched.iloc[0].context_features) == 5
    pd.testing.assert_frame_equal(baseline, original)
    for key, replacement in (
        ("label", 0),
        ("surface", "Grass"),
        ("player1_matches", 99),
        ("date", pd.Timestamp("2024-01-01")),
    ):
        corrupted = baseline.copy()
        corrupted.loc[0, key] = replacement
        with pytest.raises(ValueError, match="align"):
            attach_context(history, corrupted)


def test_surface_history_keeps_only_twenty_observations() -> None:
    history = SurfaceHistory()
    for value in range(25):
        history.results.append(float(value))
    assert list(history.results) == list(range(5, 25))
