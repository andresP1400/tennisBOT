"""Training-only transforms, earlier-year family selection, and later calibration."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from logging_config import get_logger
from pipeline.personal_model import (
    Estimator,
    raw_probability,
    reversed_features,
    logits,
)
from pipeline.personal_scores import arrays, metrics

logger = get_logger(__name__)


def fit_candidates(
    train: pd.DataFrame, validation: pd.DataFrame
) -> tuple[Estimator, str, dict[str, object]]:
    """Choose the family on the provided selection period only."""
    features, labels = arrays(train)
    augmented = np.concatenate([features, reversed_features(features)])
    outcomes = np.concatenate([labels, 1 - labels])
    candidates: dict[str, Estimator] = {
        "logistic": make_pipeline(
            StandardScaler(), LogisticRegression(C=0.1, max_iter=500, random_state=42)
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=180,
            max_leaf_nodes=15,
            learning_rate=0.05,
            l2_regularization=10.0,
            min_samples_leaf=60,
            early_stopping=False,
            random_state=42,
        ),
    }
    val_features, val_labels = arrays(validation)
    scores = {}
    for name, estimator in candidates.items():
        estimator.fit(augmented, outcomes)
        scores[name] = metrics(val_labels, raw_probability(estimator, val_features))
        logger.info(
            "Selection %s, %s: %s",
            sorted(validation.year.unique().tolist()),
            name,
            scores[name],
        )
    chosen = min(scores, key=lambda name: float(scores[name]["log_loss"]))
    return candidates[chosen], chosen, dict(scores)


def fit_calibrator(
    probabilities: NDArray[np.float64], labels: NDArray[np.int64]
) -> LogisticRegression:
    """Platt scaling fitted on a later, disjoint full year; preserve symmetry."""
    calibrator = LogisticRegression(C=1.0, fit_intercept=False, random_state=42)
    calibrator.fit(
        logits(np.concatenate([probabilities, 1 - probabilities])),
        np.concatenate([labels, 1 - labels]),
    )
    return calibrator
