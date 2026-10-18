"""Distinguish downloaded result dates from mature state and per-feature coverage."""

from __future__ import annotations

import numpy as np
import pandas as pd


def point_statistics_dates(history: pd.DataFrame) -> tuple[str | None, str | None]:
    """Only complete, arithmetically consistent point triplets establish stat freshness."""
    valid = pd.Series(True, index=history.index)
    for side in ("w", "l"):
        counts = history.reindex(
            columns=[f"{side}_1stWon", f"{side}_2ndWon", f"{side}_svpt"]
        )
        first, second, total = (counts.iloc[:, index] for index in range(3))
        valid &= (
            np.isfinite(counts).all(axis=1)
            & (first >= 0)
            & (second >= 0)
            & (total > 0)
            & (first + second <= total)
        )
    observed = history.loc[valid, "date"]
    mature = observed[
        observed + pd.Timedelta(days=21) <= pd.Timestamp.today().normalize()
    ]
    return (
        str(observed.max().date()) if not observed.empty else None,
        str(mature.max().date()) if not mature.empty else None,
    )


def freshness_metadata(history: pd.DataFrame, detailed: bool) -> dict[str, object]:
    """A current source snapshot does not establish complete current player histories."""
    mature = history[
        history.date + pd.Timedelta(days=21) <= pd.Timestamp.today().normalize()
    ]
    through = str(mature.date.max().date())
    observed_stats, applied_stats = point_statistics_dates(history)
    return {
        "feature_state_through": through,
        "statistics_through": applied_stats,
        "observed_statistics_through": observed_stats,
        "input_limitations": (
            f"Partial {'detailed-statistics' if detailed else 'result-only'} refresh; unresolved identities, "
            "possible overlaps and incomplete matches withheld. "
            f"Feature state uses results dated through {through} under a 21-day embargo. "
            "Individual player statistics may be older or missing; source coverage is not complete."
        ),
    }
