"""Whole-date partitions keep mirrored matches out of neighboring data splits."""

from __future__ import annotations

import pandas as pd

from exceptions import TrainingError


def date_partitions(
    frame: pd.DataFrame, fractions: tuple[float, ...]
) -> list[pd.DataFrame]:
    """Refuse insufficient chronology instead of inventing independent row groups."""
    column = "tourney_date" if "tourney_date" in frame else "year"
    groups = sorted(frame[column].dropna().unique())
    if len(groups) < len(fractions):
        raise TrainingError("Insufficient distinct dates for chronological evaluation")
    bounds = [0]
    cumulative = 0.0
    for index, fraction in enumerate(fractions[:-1]):
        cumulative += fraction
        bounds.append(
            min(
                len(groups) - (len(fractions) - index - 1),
                max(bounds[-1] + 1, int(len(groups) * cumulative)),
            )
        )
    bounds.append(len(groups))
    return [
        frame[frame[column].isin(groups[start:end])].sort_values(column).copy()
        for start, end in zip(bounds[:-1], bounds[1:])
    ]
