"""Head-to-Head (H2H) features.

Computes for each matchup:
  - h2h_win_pct         : historical win percentage of p1 vs p2
  - h2h_win_pct_surface : H2H filtered by the match surface

CRITICAL: forward-only. H2H at match i uses only matches 0..i-1.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from logging_config import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class H2HTracker:
    """Track head-to-head records between all player pairs."""

    def __init__(self) -> None:
        # (player_a_id, player_b_id) -> list of (won_by_a: bool, surface: str)
        self.records: dict[tuple[int, int], list[tuple[bool, str]]] = defaultdict(list)

    @staticmethod
    def _key(p1_id: int, p2_id: int) -> tuple[int, int]:
        """Canonical key: always smaller id first."""
        return (min(p1_id, p2_id), max(p1_id, p2_id))

    def get_h2h(
        self, p1_id: int, p2_id: int, surface: str | None = None
    ) -> dict[str, Any]:
        """Get H2H stats BEFORE current match."""
        key = self._key(p1_id, p2_id)
        history = self.records[key]
        result: dict[str, Any] = {
            "h2h_win_pct": np.nan,
            "h2h_win_pct_surface": np.nan,
            "h2h_total_matches": 0,
        }
        if not history:
            return result
        is_first = p1_id == key[0]
        wins = sum(
            1
            for won_first, _ in history
            if (won_first and is_first) or (not won_first and not is_first)
        )
        total = len(history)
        result["h2h_win_pct"] = wins / total
        result["h2h_total_matches"] = total
        if surface:
            surface_matches = [(w, s) for w, s in history if s == surface]
            if surface_matches:
                s_wins = sum(
                    1
                    for won_first, _ in surface_matches
                    if (won_first and is_first) or (not won_first and not is_first)
                )
                result["h2h_win_pct_surface"] = s_wins / len(surface_matches)
        return result

    def update(self, winner_id: int, loser_id: int, surface: str) -> None:
        """Record a match result. Call AFTER feature extraction."""
        key = self._key(winner_id, loser_id)
        won_by_first = winner_id == key[0]
        self.records[key].append((won_by_first, surface))


def compute_h2h_features(
    df_original: pd.DataFrame, return_state: bool = False
) -> pd.DataFrame | tuple[pd.DataFrame, H2HTracker]:
    """Compute H2H features on the ORIGINAL (non-symmetric) dataset.

    With return_state=True, also returns the H2HTracker for live inference.
    """
    logger.info("\n  Computing head-to-head features ...")
    sort_cols = [
        c
        for c in ["match_date_est", "tourney_date", "match_num"]
        if c in df_original.columns
    ]
    df = df_original.sort_values(sort_cols).reset_index(drop=True)
    tracker = H2HTracker()
    records = []
    for idx in range(len(df)):
        row = df.iloc[idx]
        w_id = row["winner_id"]
        l_id = row["loser_id"]
        surface = row.get("surface", None)
        h2h = tracker.get_h2h(w_id, l_id, surface)
        record = {
            "winner_h2h_win_pct": h2h["h2h_win_pct"],
            "loser_h2h_win_pct": (
                1.0 - h2h["h2h_win_pct"] if not np.isnan(h2h["h2h_win_pct"]) else np.nan
            ),
            "winner_h2h_win_pct_surface": h2h["h2h_win_pct_surface"],
            "loser_h2h_win_pct_surface": (
                1.0 - h2h["h2h_win_pct_surface"]
                if not np.isnan(h2h["h2h_win_pct_surface"])
                else np.nan
            ),
            "h2h_total_matches": h2h["h2h_total_matches"],
        }
        records.append(record)
        tracker.update(w_id, l_id, surface)  # type: ignore[arg-type]
    h2h_df = pd.DataFrame(records, index=df.index)
    result = pd.concat([df, h2h_df], axis=1)
    logger.info(f"  H2H features computed for {len(result):,} matches")
    h2h_known = (h2h_df["h2h_total_matches"] > 0).sum()
    logger.info(
        f"  Matches with prior H2H: {h2h_known:,} ({100*h2h_known/len(result):.1f}%)"
    )
    if return_state:
        return result, tracker
    return result
