"""Choose using the earlier selection period; paired later comparisons never deploy a model."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from api.personal_engine import load_bundle
from pipeline.market_learners import candidates
from pipeline.personal_fitting import fit_calibrator
from pipeline.personal_model import calibrate, raw_probability
from pipeline.personal_scores import arrays
from pipeline.personal_uncertainty import paired_date_bootstrap


def choose_by_selection(reports: dict[str, object]) -> str:
    """Changing a reported test score cannot change the pre-test selection rule."""
    scores: dict[str, float] = {}
    for name, report in reports.items():
        if not isinstance(report, dict) or not isinstance(
            report.get("selection_2024"), dict
        ):
            raise ValueError("Missing earlier selection scores")
        scores[name] = float(report["selection_2024"]["log_loss"])
    return min(scores, key=lambda name: scores[name])


def fit_study(
    parts: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> tuple[dict[str, object], dict[str, list[NDArray[np.float64]]], str, list[str]]:
    """All declared fixed families and equal-weight ensemble remain in the report."""
    from pipeline.market_study import evaluate_candidate, ensemble_report

    estimators, missing = candidates()
    reports: dict[str, object] = {}
    raw: dict[str, list[NDArray[np.float64]]] = {}
    for name, estimator in estimators.items():
        reports[name], raw[name] = evaluate_candidate(name, estimator, parts)
    reports["equal_weight_ensemble"] = ensemble_report(list(raw.values()), parts)
    averaged = [
        np.mean([values[index] for values in raw.values()], axis=0)
        for index in range(3)
    ]
    raw["equal_weight_ensemble"] = averaged
    return reports, raw, choose_by_selection(reports), missing


def compare_deployed(
    tour: str, parts: tuple[pd.DataFrame, ...], raw: list[NDArray[np.float64]]
) -> dict[str, object]:
    """Same matches/date blocks compare the selected candidate against the frozen active model."""
    calibration, testing = parts[2:]
    candidate = calibrate(
        fit_calibrator(raw[1], np.asarray(calibration.label, dtype=np.int64)), raw[2]
    )
    bundle = load_bundle(tour)
    features, labels = arrays(testing)
    reference = calibrate(
        bundle.calibrator, raw_probability(bundle.estimator, features)
    )
    return {
        "reference_model_version": bundle.version,
        "reference_scope": "Current deployed frozen ML model, not a bookmaker benchmark",
        "intervals": paired_date_bootstrap(
            labels,
            candidate,
            reference,
            testing.date.to_numpy(dtype="datetime64[D]"),
            reference_name="frozen_ml",
        ),
    }
