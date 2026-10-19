"""Ablation preprocessing and calibration cannot learn from selection/test outcomes."""

import numpy as np
import pandas as pd
from pathlib import Path
import hashlib
import joblib
import pytest

from pipeline.context_fitting import context_arrays, fit_context, reverse_context
from pipeline.context_fitting import context_probability
from pipeline.context_study import save_fits
from pipeline.personal_model import calibrate


def parts() -> tuple[pd.DataFrame, ...]:
    result = []
    for year in (2023, 2024, 2025, 2026):
        result.append(
            pd.DataFrame(
                {
                    "date": pd.date_range(f"{year}-01-01", periods=12),
                    "features": [[float(index % 3 - 1)] * 18 for index in range(12)],
                    "label": [index % 2 for index in range(12)],
                    "player1_matches": [30] * 12,
                    "player2_matches": [60] * 12,
                    "context_features": [
                        [float(index), 0.1, float("nan"), 0.3, 0.2]
                        for index in range(12)
                    ],
                }
            )
        )
    return tuple(result)


def test_reversal_preserves_coverage_sum_and_missingness_but_inverts_context_differences() -> (
    None
):
    frame = parts()[0]
    features, _ = context_arrays(frame, True)
    reverse = reverse_context(features)
    assert features.shape == (12, 25)
    np.testing.assert_allclose(reverse[:, 20:], -features[:, 20:], equal_nan=True)
    np.testing.assert_allclose(reverse[:, 19], features[:, 19])
    np.testing.assert_allclose(reverse_context(reverse), features, equal_nan=True)


def test_selection_and_test_changes_cannot_change_training_transforms_or_calibration() -> (
    None
):
    original = parts()
    fit = fit_context(original, True)
    changed = tuple(frame.copy(deep=True) for frame in original)
    changed[1]["label"] = 1 - changed[1].label
    changed[3]["label"] = 1 - changed[3].label
    changed[3]["context_features"] = [[999999.0] * 5] * 12
    other = fit_context(changed, True)
    np.testing.assert_allclose(
        fit.estimator.steps[0][1].statistics_, other.estimator.steps[0][1].statistics_
    )
    np.testing.assert_allclose(
        fit.estimator.steps[-1][1].coef_, other.estimator.steps[-1][1].coef_
    )
    np.testing.assert_allclose(fit.calibrator.coef_, other.calibrator.coef_)
    np.testing.assert_allclose(
        np.delete(fit.estimator.steps[0][1].statistics_[:25], 19),
        np.zeros(24),
        atol=1e-12,
    )


def test_research_models_roundtrip_without_replacing_a_prior_artifact(
    tmp_path: Path,
) -> None:
    frames = parts()
    fitted = fit_context(frames, True)
    hashes = save_fits("atp", {"surface_context": fitted}, tmp_path)
    path = tmp_path / "atp-surface_context.joblib"
    original = path.read_bytes()
    assert hashes[path.name] == hashlib.sha256(original).hexdigest()
    loaded = joblib.load(path)
    features, _ = context_arrays(frames[-1], True)
    probabilities = calibrate(
        loaded["calibrator"], context_probability(loaded["estimator"], features)
    )
    np.testing.assert_array_equal(probabilities, fitted.probabilities)
    with pytest.raises(FileExistsError):
        save_fits("atp", {"surface_context": fitted}, tmp_path)
    assert path.read_bytes() == original
