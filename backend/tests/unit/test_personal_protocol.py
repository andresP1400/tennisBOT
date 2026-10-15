"""Annual stages and reported probability metrics must remain strictly chronological."""

import numpy as np
import pandas as pd
import pytest

from pipeline.personal_protocol import annual_partitions, evaluation_metadata
from pipeline.personal_scores import metrics, coverage_metrics


def chronology():
    dates = pd.to_datetime(
        [
            "2023-01-01",
            "2023-12-25",
            "2024-01-01",
            "2024-12-25",
            "2025-01-01",
            "2025-12-25",
            "2026-01-01",
            "2026-02-01",
        ]
    )
    return pd.DataFrame(
        {
            "date": dates,
            "year": dates.year,
            "available_at": dates + pd.Timedelta(days=21),
        }
    )


def test_2026_holdout_fits_only_before_2024_selects_2024_and_calibrates_2025():
    train, select, calibrate, test = annual_partitions(chronology(), 2026)
    assert list(train.year) == [2023]
    assert list(select.year) == [2024]
    assert list(calibrate.year) == [2025]
    assert list(test.year) == [2026, 2026]
    for before, after in zip([train, select, calibrate], [select, calibrate, test]):
        assert before.available_at.max() < after.date.min()
        assert set(before.index).isdisjoint(after.index)
    description = evaluation_metadata(test, 2026)
    assert "2026" in description["period"]
    assert description["test_end"] == "2026-02-01"
    assert "partial" in description["coverage_note"]


def test_missing_annual_stages_or_unavailable_results_never_get_invented():
    with pytest.raises(ValueError, match="mature real matches"):
        annual_partitions(chronology(), 2027)
    frame = chronology()
    frame.loc[frame.year == 2026, "available_at"] = pd.Timestamp("2099-01-01")
    with pytest.raises(ValueError, match="mature real matches"):
        annual_partitions(frame, 2026)


def test_single_class_evaluation_reports_undefined_auc_and_valid_log_loss():
    report = metrics(np.asarray([1, 1], dtype=np.int64), np.asarray([0.8, 0.9]))
    assert report["roc_auc"] is None
    assert report["accuracy"] == 1
    assert report["log_loss"] == pytest.approx(-np.mean(np.log([0.8, 0.9])))


def test_history_coverage_matches_runtime_threshold_and_never_counts_cold_starts():
    frame = pd.DataFrame(
        {
            "label": [1, 0, 1],
            "player1_matches": [10, 9, 20],
            "player2_matches": [20, 20, 2],
        }
    )
    result = coverage_metrics(frame, np.asarray([0.8, 0.8, 0.2]))
    assert result["eligible_matches"] == 1
    assert result["unavailable_matches"] == 2
    assert result["metrics"]["accuracy"] == 1
    frame["player1_matches"] = 0
    assert coverage_metrics(frame, np.asarray([0.8, 0.8, 0.2]))["metrics"] is None
