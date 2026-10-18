"""Preserve supplied point counts and demographics without filling missing statistics."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def tml_results(directory: Path, filenames: tuple[str, ...]) -> pd.DataFrame:
    """The publisher explicitly offers main-tour CSV downloads, including ongoing events."""
    frame = pd.concat(
        [pd.read_csv(directory / name, low_memory=False) for name in filenames],
        ignore_index=True,
    )
    frame["date"] = pd.to_datetime(
        frame["tourney_date"].astype(str), format="%Y%m%d", errors="coerce"
    )
    frame["first"], frame["second"] = frame["winner_name"], frame["loser_name"]
    frame["winner_first"] = True
    frame["event"] = frame["tourney_name"]
    frame["source_id"] = (
        frame["tourney_id"].astype(str) + ":" + frame["match_num"].astype(str)
    )
    for side, prefix in ((1, "winner"), (2, "loser")):
        frame[f"rank{side}"] = frame[f"{prefix}_rank"]
        frame[f"points{side}"] = frame[f"{prefix}_rank_points"]
    frame["detailed_statistics"] = True
    return frame[
        frame["tourney_level"]
        .astype(str)
        .isin(["A", "M", "G", "F", "D", "250", "500", "1000"])
    ]


def retained_statistics(row: pd.Series) -> dict[str, object]:
    """Incomplete count triplets remain incomplete and are rejected by serve_counts."""
    if not bool(row.get("detailed_statistics", False)):
        return {}
    result: dict[str, object] = {}
    for key in row.index:
        if str(key).startswith(("w_", "l_")) or key in [
            "winner_age",
            "loser_age",
            "winner_ht",
            "loser_ht",
        ]:
            value = pd.to_numeric(row[key], errors="coerce")
            minimum, maximum = (
                (100, 250)
                if str(key).endswith("_ht")
                else (12, 65) if str(key).endswith("_age") else (0, float("inf"))
            )
            result[str(key)] = (
                float(value)
                if pd.notna(value)
                and np.isfinite(value)
                and minimum <= value <= maximum
                else np.nan
            )
    return result
