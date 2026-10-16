"""Versioned lightweight estimators and symmetric calibrated probabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from pipeline.personal_state import Player

Estimator: TypeAlias = HistGradientBoostingClassifier | Pipeline


@dataclass
class PersonalBundle:
    """Local trusted artifact; no model bytes are accepted from API callers."""

    tour: str
    version: str
    family: str
    estimator: Estimator
    calibrator: LogisticRegression
    elo_calibrator: LogisticRegression
    players: dict[int, Player]
    names: dict[str, int]
    data_through: str
    report: dict[str, object]
    feature_schema: int = 1
    use_recent_form: bool = True


def reversed_features(features: NDArray[np.float64]) -> NDArray[np.float64]:
    """Invert player differences while preserving surface and match format."""
    reverse = features.copy()
    reverse[:, :10] *= -1
    reverse[:, 15:] *= -1
    return reverse


def raw_probability(
    estimator: Estimator, features: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Enforce player-order invariance before fitting probability calibration."""
    forward = np.asarray(estimator.predict_proba(features), dtype=float)[:, 1]
    reverse = np.asarray(
        estimator.predict_proba(reversed_features(features)), dtype=float
    )[:, 1]
    return np.asarray((forward + 1 - reverse) / 2, dtype=np.float64)


def elo_raw(features: NDArray[np.float64]) -> NDArray[np.float64]:
    """Blend surface and global historical ratings, without sportsbook inputs."""
    return np.asarray(1 / (1 + 10 ** (-features[:, 1])), dtype=float)


def logits(probabilities: NDArray[np.float64]) -> NDArray[np.float64]:
    """Stable one-dimensional inputs to Platt calibration."""
    clipped = np.clip(probabilities, 1e-6, 1 - 1e-6)
    return np.asarray(np.log(clipped / (1 - clipped)).reshape(-1, 1), dtype=float)


def calibrate(
    calibrator: LogisticRegression, probabilities: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Return the learned probability, not a fabricated confidence percentage."""
    return np.asarray(calibrator.predict_proba(logits(probabilities)), dtype=float)[
        :, 1
    ]
