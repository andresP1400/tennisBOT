"""One calibration order shared by evaluation, single inference, and history."""

from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class Calibrator(Protocol):
    def predict(self, probabilities: NDArray[np.float64]) -> NDArray[np.float64]: ...


def symmetric_calibration(
    probabilities: NDArray[np.float64], calibrator: Calibrator | None
) -> NDArray[np.float64]:
    """Calibrate a symmetrized raw probability and its complement identically."""
    values = np.asarray(probabilities, dtype=np.float64).ravel()
    if calibrator is None:
        return values
    forward = np.asarray(calibrator.predict(values), dtype=np.float64)
    reverse = np.asarray(calibrator.predict(1 - values), dtype=np.float64)
    return np.asarray(np.clip((forward + 1 - reverse) / 2, 0, 1), dtype=np.float64)
