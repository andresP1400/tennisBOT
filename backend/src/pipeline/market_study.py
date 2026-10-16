"""Fixed chronological candidate study; no model-pointer updates or odds-derived inputs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from pipeline.market_learners import StudyEstimator

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from api.personal_engine import load_bundle
from config import REPORTS_DIR
from pipeline.personal_data import load_history, build_dataset
from pipeline.personal_fitting import fit_calibrator
from pipeline.personal_model import (
    raw_probability,
    calibrate,
    elo_raw,
    reversed_features,
)
from pipeline.personal_protocol import annual_partitions
from pipeline.market_comparison_study import fit_study, compare_deployed
from pipeline.personal_scores import arrays, metrics
from pipeline.market_validation import bin_evidence, save_evidence
from pipeline.personal_uncertainty import paired_date_bootstrap
from logging_config import get_logger

logger = get_logger(__name__)


def study_arrays(frame: pd.DataFrame) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Observed prior counts provide a rating-coverage uncertainty proxy, not a claimed posterior."""
    features, labels = arrays(frame)
    first = 1 / np.sqrt(np.asarray(frame.player1_matches, dtype=float) + 1)
    second = 1 / np.sqrt(np.asarray(frame.player2_matches, dtype=float) + 1)
    return np.column_stack([features, first - second, first + second]), labels


def study_reverse(features: NDArray[np.float64]) -> NDArray[np.float64]:
    """The last coverage-sum context is symmetric under reversing the player order."""
    reversed_values = reversed_features(features)
    reversed_values[:, -1] = features[:, -1]
    return reversed_values


def probability(
    estimator: StudyEstimator, features: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Preserve the deployed model's symmetrize-before-calibrate convention."""
    first = np.asarray(estimator.predict_proba(features), dtype=float)[:, 1]
    second = np.asarray(estimator.predict_proba(study_reverse(features)), dtype=float)[
        :, 1
    ]
    return np.asarray((first + 1 - second) / 2, dtype=float)


def selected_confidence(
    frame: pd.DataFrame, probabilities: NDArray[np.float64]
) -> dict[str, object]:
    """The declared 80% cut is evaluated unchanged; missing prices preclude Category A claims."""
    eligible = np.maximum(probabilities, 1 - probabilities) >= 0.80
    labels = np.asarray(frame.label, dtype=np.int64)
    return {
        "threshold": 0.80,
        "matches": int(eligible.sum()),
        "coverage": float(eligible.mean()),
        "approximate_date_block_intervals": selected_intervals(
            frame, probabilities, eligible
        ),
        "metrics": (
            metrics(labels[eligible], probabilities[eligible])
            if eligible.any()
            else None
        ),
        "mean_estimated_probability": (
            float(
                np.maximum(probabilities[eligible], 1 - probabilities[eligible]).mean()
            )
            if eligible.any()
            else None
        ),
        "category_a_performance": None,
        "betting_roi": None,
        "closing_line_value": None,
        "scope": "Probability-only historical subset; contemporaneous prices/qualification unavailable",
    }


def selected_intervals(
    frame: pd.DataFrame, probabilities: NDArray[np.float64], eligible: NDArray[np.bool_]
) -> dict[str, object] | None:
    """Report uncertainty for the fixed subset without claiming independent match outcomes."""
    if "date" not in frame or len(frame.loc[eligible, "date"].unique()) < 2:
        return None
    selected = probabilities[eligible]
    intervals = paired_date_bootstrap(
        np.asarray(frame.loc[eligible, "label"], dtype=np.int64),
        selected,
        selected,
        frame.loc[eligible, "date"].to_numpy(dtype="datetime64[D]"),
    )
    return {
        "metrics": intervals["ml"],
        "date_blocks": intervals["date_blocks"],
        "method": intervals["method"],
        "limitations": intervals["limitations"],
    }


def evaluate_candidate(
    name: str,
    estimator: StudyEstimator,
    parts: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> tuple[dict[str, object], list[NDArray[np.float64]]]:
    """Fit on training, calibrate on the later calibration year, score the held-out period once."""
    training, selection, calibration, testing = parts
    train, labels = study_arrays(training)
    estimator.fit(
        np.concatenate([train, study_reverse(train)]),
        np.concatenate([labels, 1 - labels]),
    )
    predictions = [
        probability(estimator, study_arrays(part)[0])
        for part in (selection, calibration, testing)
    ]
    calibrated = calibrate(
        fit_calibrator(predictions[1], np.asarray(calibration.label, dtype=np.int64)),
        predictions[2],
    )
    report: dict[str, object] = {
        "selection_2024": metrics(
            np.asarray(selection.label, dtype=np.int64), predictions[0]
        ),
        "test_2026": metrics(np.asarray(testing.label, dtype=np.int64), calibrated),
        "high_confidence": selected_confidence(testing, calibrated),
        "calibration_bins": bin_evidence(testing, calibrated),
    }
    logger.info("Fixed study %s: %s", name, report["test_2026"])
    return report, predictions


def evaluate_tour(tour: str) -> dict[str, object]:
    """Evaluate frozen alternatives, while preserving every deployed model and earlier live result."""
    history, audit = load_history(tour)
    frame, _ = build_dataset(history, feature_schema=2)
    parts = annual_partitions(frame, 2026)
    reports, raw, selected, missing = fit_study(parts)
    comparison = compare_deployed(tour, parts, raw[selected])
    active = deployed_evidence(tour, parts[-1])
    return {
        "tour": tour,
        "source_audit": audit,
        "candidates": reports,
        "unavailable": missing,
        "deployed_reference": active,
        "selected_using_2024_only": selected,
        "paired_selected_vs_deployed": comparison,
        "protocol": "Fit <=2023; selection 2024; calibration 2025; retrospective inspected partial 2026 test",
        "new_features": [
            "Signed prior-count uncertainty proxy",
            "Symmetric prior-count uncertainty sum",
        ],
        "selection_rule": "2024 raw log-loss only; no candidate automatically deployed",
        "test_is_newly_untouched": False,
        "market_benchmark": None,
        "missing_inputs": [
            "Contemporaneous historical odds",
            "Verified injuries",
            "Exact rest/fatigue timestamps",
            "Indoor/outdoor metadata",
            "Public betting splits",
        ],
    }


def ensemble_report(
    raw: list[list[NDArray[np.float64]]], parts: tuple[pd.DataFrame, ...]
) -> dict[str, object]:
    """Fixed equal weights; no test-score weighting, threshold search, or hidden model exclusion."""
    selection, calibration, testing = parts[1:]
    averaged = [
        np.mean([values[index] for values in raw], axis=0) for index in range(3)
    ]
    probabilities = calibrate(
        fit_calibrator(averaged[1], np.asarray(calibration.label, dtype=np.int64)),
        averaged[2],
    )
    return {
        "selection_2024": metrics(
            np.asarray(selection.label, dtype=np.int64), averaged[0]
        ),
        "test_2026": metrics(np.asarray(testing.label, dtype=np.int64), probabilities),
        "high_confidence": selected_confidence(testing, probabilities),
        "calibration_bins": bin_evidence(testing, probabilities),
    }


def deployed_evidence(tour: str, testing: pd.DataFrame) -> dict[str, object]:
    """Match the actual deployed model's report before publishing independent uncertainty evidence."""
    bundle = load_bundle(tour)
    features, labels = arrays(testing)
    probabilities = calibrate(
        bundle.calibrator, raw_probability(bundle.estimator, features)
    )
    measured = metrics(labels, probabilities)
    expected = bundle.report["evaluation"]
    if not isinstance(expected, dict) or measured != expected["metrics"]:
        raise ValueError(
            "Deployed evaluation no longer matches this real dataset; evidence was not saved"
        )
    evidence = save_evidence(bundle, testing, probabilities)
    return {
        "model_version": bundle.version,
        "metrics": measured,
        "high_confidence": selected_confidence(testing, probabilities),
        "elo": metrics(labels, calibrate(bundle.elo_calibrator, elo_raw(features))),
        "calibration_bins": bin_evidence(testing, probabilities),
        "local_evidence_file": evidence.name,
    }


def main() -> None:
    """Save new private study reports, never replace a deployed pointer or old report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tour", choices=("atp", "wta", "both"), default="both")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    stamp = datetime.now(timezone.utc)
    report = {
        "created_at": stamp.isoformat(),
        "tours": {
            tour: evaluate_tour(tour)
            for tour in (
                ("atp", "wta") if arguments.tour == "both" else (arguments.tour,)
            )
        },
    }
    path = (
        arguments.output
        or REPORTS_DIR / "personal" / f"market-study-{stamp:%Y%m%dT%H%M%S%fZ}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")
    path.chmod(0o600)


if __name__ == "__main__":
    main()
