"""Uncertainty evidence and mirrored features remain chronological and honest about sparse samples."""

from pathlib import Path
import json
from sklearn.linear_model import LogisticRegression
import numpy as np
import pandas as pd
import pytest

from pipeline.market_validation import bin_evidence, evidence_for, save_evidence
from pipeline.personal_model import PersonalBundle
from pipeline.market_study import study_arrays, study_reverse, selected_confidence
from pipeline.market_learners import candidates
from pipeline.market_comparison_study import choose_by_selection


def unit_bundle() -> PersonalBundle:
    return PersonalBundle(
        tour="atp",
        version="unit-only",
        family="unit",
        estimator=LogisticRegression(),
        calibrator=LogisticRegression(),
        elo_calibrator=LogisticRegression(),
        players={},
        names={},
        data_through="2025-12-01",
        report={
            "audit": {"source_digest": "a" * 64},
            "implementation_sha256": "b" * 64,
        },
    )


def test_uncertainty_evidence_requires_matching_version_code_source_and_adequate_samples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pipeline.market_validation.EVIDENCE_DIR", tmp_path)
    bundle = unit_bundle()
    path = tmp_path / "unit-only.json"
    assert evidence_for(bundle, 0.82) is None
    payload = {
        "model_version": bundle.version,
        "model_source_digest": "a" * 64,
        "implementation_sha256": "b" * 64,
        "validation_end": "2025-12-01T00:00:00Z",
        "method": "unit evidence",
        "bins": [{"matches": 200, "date_blocks": 25, "lower": 0.75, "upper": 0.90}] * 5,
    }
    path.write_text(json.dumps(payload))
    first, opposite = evidence_for(bundle, 0.82), evidence_for(bundle, 0.18)
    assert first is not None and first.lower_probability == 0.75
    assert opposite is not None and opposite.lower_probability == pytest.approx(0.10)
    for key in ("model_version", "model_source_digest", "implementation_sha256"):
        path.write_text(json.dumps({**payload, key: "mismatch"}))
        assert evidence_for(bundle, 0.82) is None
    payload["bins"][3]["matches"] = 99
    path.write_text(json.dumps(payload))
    assert evidence_for(bundle, 0.82) is None
    path.write_text("corrupt JSON")
    assert evidence_for(bundle, 0.82) is None


def test_saved_evidence_is_immutable_and_rejects_changed_validation_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pipeline.market_validation.EVIDENCE_DIR", tmp_path)
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=200),
            "available_at": pd.date_range("2025-01-22", periods=200),
            "label": [1] * 160 + [0] * 40,
        }
    )
    probabilities = np.full(200, 0.82)
    path = save_evidence(unit_bundle(), frame, probabilities)
    original = path.read_bytes()
    assert save_evidence(unit_bundle(), frame, probabilities) == path
    frame.loc[0, "label"] = 0
    with pytest.raises(ValueError, match="Conflicting evidence"):
        save_evidence(unit_bundle(), frame, probabilities)
    assert path.read_bytes() == original


def test_model_selection_does_not_change_when_future_test_scores_change() -> None:
    reports = {
        "earlier_best": {
            "selection_2024": {"log_loss": 0.60},
            "test_2026": {"accuracy": 0.1},
        },
        "test_winner": {
            "selection_2024": {"log_loss": 0.62},
            "test_2026": {"accuracy": 1.0},
        },
    }
    assert choose_by_selection(reports) == "earlier_best"
    reports["earlier_best"]["test_2026"]["accuracy"] = 0.0
    assert choose_by_selection(reports) == "earlier_best"


def test_calibration_bins_keep_boundaries_and_canonical_counts_without_mirrors() -> (
    None
):
    probabilities = np.asarray([0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 0.2, 0.1])
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=8),
            "label": [1, 1, 0, 1, 0, 1, 0, 0],
        }
    )
    bands = bin_evidence(frame, probabilities)
    assert sum(band["matches"] for band in bands) == 8
    assert [band["matches"] for band in bands] == [1, 1, 1, 2, 3]
    assert all(band["lower"] is None and band["upper"] is None for band in bands)


def test_study_uses_prior_counts_and_reversal_preserves_only_unsigned_context() -> None:
    frame = pd.DataFrame(
        {
            "features": [[0.0] * 18],
            "label": [1],
            "player1_matches": [24],
            "player2_matches": [99],
        }
    )
    features, labels = study_arrays(frame)
    assert features.shape == (1, 20)
    assert features[0, 18] == pytest.approx(0.2 - 0.1)
    assert features[0, 19] == pytest.approx(0.2 + 0.1)
    reverse = study_reverse(features)
    np.testing.assert_allclose(reverse[0, :19], -features[0, :19])
    assert reverse[0, 19] == features[0, 19]
    np.testing.assert_allclose(study_reverse(reverse), features)


def test_probability_only_subset_does_not_claim_category_a_roi_or_clv() -> None:
    frame = pd.DataFrame({"label": [1, 0, 1]})
    report = selected_confidence(frame, np.asarray([0.81, 0.19, 0.79]))
    assert report["matches"] == 2
    assert report["metrics"]["accuracy"] == 1
    assert report["category_a_performance"] is None
    assert report["betting_roi"] is None
    assert report["closing_line_value"] is None


def test_declared_candidate_families_do_not_receive_test_rows_or_odds_features() -> (
    None
):
    models, missing = candidates()
    assert {"logistic", "hist_gradient_boosting", "xgboost", "lightgbm"}.issubset(
        models
    )
    if "catboost" in models:
        assert models["catboost"].get_params()["allow_writing_files"] is False
    else:
        assert missing
