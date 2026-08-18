"""Probability calibration module."""
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from logging_config import get_logger

logger = get_logger(__name__)


class ProbabilityCalibrator:
    """Wraps isotonic regression or Platt scaling for probability calibration."""

    def __init__(self, method: str = "platt"):
        self.method = method
        if method == "isotonic":
            self.model = IsotonicRegression(out_of_bounds="clip")
        elif method == "platt":
            self.model = LogisticRegression(max_iter=2000)
        else:
            raise ValueError(f"Unknown calibration method: {method}")

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray) -> "ProbabilityCalibrator":
        """Fit calibrator on validation set probabilities."""
        if self.method == "isotonic":
            self.model.fit(raw_probs, y_true)
        elif self.method == "platt":
            self.model.fit(raw_probs.reshape(-1, 1), y_true)
        return self

    def predict(self, raw_probs: np.ndarray) -> np.ndarray:
        """Calibrate probabilities, returning continuous values in [0, 1]."""
        if self.method == "isotonic":
            probs = self.model.predict(raw_probs.ravel())
            return np.clip(probs, 0.0, 1.0)
        elif self.method == "platt":
            return self.model.predict_proba(raw_probs.reshape(-1, 1))[:, 1]


def calibrate_probabilities(
    raw_probs: np.ndarray,
    y_true: np.ndarray,
    method: str = "platt",
) -> ProbabilityCalibrator:
    """Fit and return a probability calibrator."""
    logger.info(f"\n  Calibration method: {method}")
    cal = ProbabilityCalibrator(method=method)
    cal.fit(raw_probs, y_true)
    calibrated = cal.predict(raw_probs)
    from sklearn.metrics import brier_score_loss
    brier_before = brier_score_loss(y_true, raw_probs)
    brier_after = brier_score_loss(y_true, calibrated)
    logger.info(f"  Brier score BEFORE calibration: {brier_before:.5f}")
    logger.info(f"  Brier score AFTER  calibration: {brier_after:.5f}")
    improvement = (brier_before - brier_after) / brier_before * 100
    logger.info(f"  Improvement: {improvement:.2f}%")
    return cal
