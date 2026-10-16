"""Fixed surface-context logistic ablation with training-only preprocessing."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from pipeline.market_study import study_arrays, study_reverse, selected_confidence
from pipeline.personal_fitting import fit_calibrator
from pipeline.personal_model import calibrate
from pipeline.personal_scores import metrics


@dataclass
class ContextFit:
    estimator: Pipeline
    calibrator: LogisticRegression
    report: dict[str, object]
    probabilities: NDArray[np.float64]


def context_arrays(
    frame: pd.DataFrame, augmented: bool
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Use the declared research baseline; no market or current outcome features are added."""
    features, labels = study_arrays(frame)
    if augmented:
        features = np.column_stack(
            [features, np.asarray(frame.context_features.to_list(), dtype=float)]
        )
    return features, labels


def reverse_context(features: NDArray[np.float64]) -> NDArray[np.float64]:
    """Preserve the symmetric coverage sum; all five context differences reverse sign."""
    return np.column_stack([study_reverse(features[:, :20]), -features[:, 20:]])


def context_probability(
    estimator: Pipeline, features: NDArray[np.float64]
) -> NDArray[np.float64]:
    """The same symmetrization happens before calibration for both ablation arms."""
    first = np.asarray(estimator.predict_proba(features), dtype=float)[:, 1]
    reverse = np.asarray(
        estimator.predict_proba(reverse_context(features)), dtype=float
    )[:, 1]
    return np.asarray((first + 1 - reverse) / 2, dtype=float)


def fit_context(parts: tuple[pd.DataFrame, ...], augmented: bool) -> ContextFit:
    """Fit transforms only on training, calibrate only on 2025, never activate a model."""
    training, selection, calibration, testing = parts
    features, labels = context_arrays(training, augmented)
    estimator = make_pipeline(
        SimpleImputer(strategy="mean", add_indicator=True, keep_empty_features=True),
        StandardScaler(),
        LogisticRegression(C=0.1, max_iter=500, random_state=42),
    )
    estimator.fit(
        np.concatenate([features, reverse_context(features)]),
        np.concatenate([labels, 1 - labels]),
    )
    selection_features, selection_labels = context_arrays(selection, augmented)
    calibration_features, calibration_labels = context_arrays(calibration, augmented)
    test_features, test_labels = context_arrays(testing, augmented)
    selection_probability = context_probability(estimator, selection_features)
    calibrator = fit_calibrator(
        context_probability(estimator, calibration_features), calibration_labels
    )
    probabilities = calibrate(calibrator, context_probability(estimator, test_features))
    report: dict[str, object] = {
        "selection_2024": metrics(selection_labels, selection_probability),
        "test_2026": metrics(test_labels, probabilities),
        "high_confidence_probability_only": selected_confidence(testing, probabilities),
        "feature_count": features.shape[1],
        "training_imputation_means": estimator.steps[0][1].statistics_.tolist(),
    }
    return ContextFit(estimator, calibrator, report, probabilities)
