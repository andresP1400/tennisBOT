"""Walk-forward evaluation must never fit test labels or replace serving pointers."""

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from pipeline.personal_model import reversed_features
import pipeline.personal_walkforward as module


def dataset():
    records = []
    for year in [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]:
        for month in [1, 2, 3]:
            for label in [0, 1]:
                features = np.zeros(18)
                features[0] = (1 if label else -1) * 0.3
                features[1] = features[0] / 2
                features[10] = 1
                day = pd.Timestamp(year=year, month=month, day=1)
                records.append(
                    dict(
                        date=day,
                        available_at=day + pd.Timedelta(days=21),
                        year=year,
                        surface="Hard",
                        label=label,
                        features=features,
                        player1_matches=20,
                        player2_matches=20,
                    )
                )
    return pd.DataFrame(records)


def earlier_fitting(training, selection):
    assert training.available_at.max() < selection.date.min()
    features = np.asarray(training.features.tolist())
    labels = np.asarray(training.label)
    model = make_pipeline(LogisticRegression(C=0.1, random_state=42)).fit(
        np.concatenate([features, reversed_features(features)]),
        np.concatenate([labels, 1 - labels]),
    )
    return model, "unit-test-logistic", {}


def test_changing_heldout_outcomes_cannot_change_fitted_forecasts(monkeypatch):
    monkeypatch.setattr(module, "fit_candidates", earlier_fitting)
    frame = dataset()
    first = module.evaluate_year(frame, 2026)
    frame.loc[frame.year == 2026, "label"] = 1 - frame.loc[frame.year == 2026, "label"]
    changed = module.evaluate_year(frame, 2026)
    np.testing.assert_array_equal(first.ml, changed.ml)
    np.testing.assert_array_equal(first.elo, changed.elo)
    assert (
        first.report["ml_calibrated"]["accuracy"]
        != changed.report["ml_calibrated"]["accuracy"]
    )
    stages = first.report["stages"]
    assert stages["train"]["end"] == "2023-03-01"
    assert stages["selection"]["start"] == "2024-01-01"
    assert stages["calibration"]["start"] == "2025-01-01"
    assert stages["test"]["start"] == "2026-01-01"


def test_annual_pool_uses_unique_years_and_keeps_reference_separate(monkeypatch):
    monkeypatch.setattr(module, "fit_candidates", earlier_fitting)
    report = module.evaluate(dataset(), (2024, 2025, 2026), resamples=100)
    assert report["aggregate"]["ml_calibrated"]["matches"] == 18
    assert [fold["test_year"] for fold in report["folds"]] == [2024, 2025, 2026]
    assert (
        report["latest_year_frozen_reference"]["stages"]["calibration"]["end"]
        == "2023-03-01"
    )
    assert report["latest_year_paired_comparison"]["ml"]["accuracy"]["estimate"] == 1
    for years in [(), (2026, 2025), (2026, 2026)]:
        with pytest.raises(ValueError, match="unique and strictly increasing"):
            module.evaluate(dataset(), years, resamples=100)
    with pytest.raises(ValueError, match="resamples"):
        module.evaluate(dataset(), (2026,), resamples=1)


def test_old_reference_is_not_backtested_before_its_calibration_period(monkeypatch):
    monkeypatch.setattr(module, "fit_candidates", earlier_fitting)
    report = module.evaluate(dataset(), (2022,), resamples=100)
    assert report["latest_year_frozen_reference"] is None
    assert report["latest_year_paired_comparison"] is None


def test_evaluation_report_retains_existing_files_and_never_activates_a_model(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(module, "REPORTS_DIR", tmp_path / "reports")
    pointer = tmp_path / "models/personal/atp-latest.json"
    pointer.parent.mkdir(parents=True)
    pointer.write_text('{"version":"keep-current-version"}')
    report = {"tour": "atp", "aggregate": {"unit_test_only": True}}
    first = module.save_report(report)
    original = first.read_bytes()
    second = module.save_report(report)
    assert first != second and first.read_bytes() == original
    assert pointer.read_text() == '{"version":"keep-current-version"}'
    assert len(list((tmp_path / "models").rglob("*latest.json"))) == 1
