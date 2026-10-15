"""Paired date-block bootstrap intervals for chronological match predictions."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

MetricIntervals = dict[str, dict[str, float]]


def contributions(
    labels: NDArray[np.int64], probabilities: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Aggregate losses per real match before resampling shared tournament dates."""
    clipped = np.clip(probabilities, np.finfo(float).eps, 1 - np.finfo(float).eps)
    return np.column_stack(
        [
            (probabilities >= 0.5) == labels,
            (probabilities - labels) ** 2,
            -labels * np.log(clipped) - (1 - labels) * np.log1p(-clipped),
        ]
    ).astype(float)


def intervals(
    point: NDArray[np.float64], samples: NDArray[np.float64]
) -> MetricIntervals:
    """Undefined discrimination metrics are not approximated with a made-up AUC."""
    bounds = np.quantile(samples, [0.025, 0.975], axis=0)
    return {
        name: {
            "estimate": float(point[index]),
            "lower_95": float(bounds[0, index]),
            "upper_95": float(bounds[1, index]),
        }
        for index, name in enumerate(("accuracy", "brier", "log_loss"))
    }


def validate_inputs(
    labels: NDArray[np.int64],
    ml: NDArray[np.float64],
    elo: NDArray[np.float64],
    dates: NDArray[np.datetime64],
    resamples: int,
) -> None:
    """Bad alignment or missing dates must not produce spurious certainty."""
    if any(
        values.ndim != 1 or len(values) != len(labels)
        for values in (labels, ml, elo, dates)
    ) or not len(labels):
        raise ValueError(
            "Aligned nonempty one-dimensional evaluation inputs are required"
        )
    if not np.isin(labels, [0, 1]).all() or np.isnat(dates).any():
        raise ValueError("Binary outcomes and known tournament dates are required")
    if any(
        not np.isfinite(values).all() or np.any((values < 0) | (values > 1))
        for values in (ml, elo)
    ):
        raise ValueError("Finite win probabilities in [0,1] are required")
    if not 100 <= resamples <= 10000 or len(np.unique(dates)) < 2:
        raise ValueError(
            "At least two date blocks and 100–10000 resamples are required"
        )


def paired_date_bootstrap(
    labels: NDArray[np.int64],
    ml: NDArray[np.float64],
    elo: NDArray[np.float64],
    dates: NDArray[np.datetime64],
    *,
    resamples: int = 1000,
    seed: int = 42,
    reference_name: str = "elo",
) -> dict[str, object]:
    """Use identical resampled date blocks for ML/Elo and their paired difference."""
    validate_inputs(labels, ml, elo, dates, resamples)
    if reference_name not in ("elo", "frozen_ml"):
        raise ValueError("Unknown paired reference")
    groups, membership = np.unique(dates, return_inverse=True)
    totals = np.zeros((len(groups), 7), dtype=float)
    rows = np.column_stack(
        [np.ones(len(labels)), contributions(labels, ml), contributions(labels, elo)]
    )
    np.add.at(totals, membership, rows)
    indices = np.random.default_rng(seed).integers(
        len(groups), size=(resamples, len(groups))
    )
    sampled = totals[indices].sum(axis=1)
    estimates = sampled[:, 1:] / sampled[:, [0]]
    point = rows[:, 1:].sum(axis=0) / len(labels)
    return {
        "method": "Paired tournament-start-date block bootstrap; approximate intervals",
        "date_blocks": len(groups),
        "resamples": resamples,
        "seed": seed,
        "ml": intervals(point[:3], estimates[:, :3]),
        reference_name: intervals(point[3:], estimates[:, 3:]),
        f"ml_minus_{reference_name}": intervals(
            point[:3] - point[3:], estimates[:, :3] - estimates[:, 3:]
        ),
        "limitations": "Start dates are not completion times; player dependence across date blocks remains",
    }
