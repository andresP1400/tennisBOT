"""Probability metrics on real canonical matches, with explicit undefined AUC."""

from __future__ import annotations

from typing import TypedDict
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score


class PersonalMetrics(TypedDict):
    matches: int
    accuracy: float
    brier: float
    log_loss: float
    roc_auc: float | None
    ece_10_bins: float


def metrics(
    labels: NDArray[np.int64], probabilities: NDArray[np.float64]
) -> PersonalMetrics:
    """Evaluate one row per real match; mirrored training rows are never counted."""
    result: PersonalMetrics = {
        "matches": len(labels),
        "accuracy": float(accuracy_score(labels, probabilities >= 0.5)),
        "brier": float(brier_score_loss(labels, probabilities)),
        "log_loss": float(log_loss(labels, probabilities, labels=[0, 1])),
        "roc_auc": (
            float(roc_auc_score(labels, probabilities))
            if len(set(labels)) > 1
            else None
        ),
        "ece_10_bins": 0.0,
    }
    bins = np.minimum((probabilities * 10).astype(int), 9)
    result["ece_10_bins"] = float(
        sum(
            abs(
                float(np.mean(labels[bins == index]))
                - float(np.mean(probabilities[bins == index]))
            )
            * float(np.mean(bins == index))
            for index in range(10)
            if np.any(bins == index)
        )
    )
    return result


def arrays(frame: pd.DataFrame) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Extract real canonical player orientation for evaluation."""
    return np.asarray(frame["features"].tolist(), dtype=float), np.asarray(
        frame["label"], dtype=np.int64
    )


def coverage_metrics(
    frame: pd.DataFrame, probabilities: NDArray[np.float64]
) -> dict[str, object]:
    """Apply the same prior-match threshold as live inference, without counting mirrors."""
    eligible = np.asarray(
        (frame.player1_matches >= 10) & (frame.player2_matches >= 10), dtype=bool
    )
    labels = np.asarray(frame.label, dtype=np.int64)
    return {
        "minimum_prior_matches_each": 10,
        "eligible_matches": int(eligible.sum()),
        "unavailable_matches": int((~eligible).sum()),
        "metrics": (
            metrics(labels[eligible], probabilities[eligible])
            if eligible.any()
            else None
        ),
        "scope": "Historical player coverage only; current fixture-provider surface/name coverage is separate",
    }
