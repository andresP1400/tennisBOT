"""Fatigue and conditioning features.

Computes for each player (forward-only):
  - days_rest                         : days since their last match
  - minutes_on_court_last_10_days     : decay-weighted minutes in last 10 days
  - matches_last_7_days               : number of matches in the last 7 days
  - travel_timezone_diff              : NOT implemented in v1
"""

import os
import sys
from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from logging_config import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FatigueTracker:
    """Track fatigue-related data per player."""

    def __init__(self) -> None:
        self.match_history: list[tuple[pd.Timestamp, float]] = (
            []
        )  # [(ts, minutes), ...]

    def get_fatigue_stats(self, current_date: pd.Timestamp) -> dict[str, Any]:
        """Get fatigue features AT current_date (before this match)."""
        stats: dict[str, Any] = {}
        if not self.match_history:
            stats["days_rest"] = np.nan
            stats["minutes_on_court_last_10_days"] = np.nan
            stats["matches_last_7_days"] = 0
            return stats

        # Days since last match
        last_date = self.match_history[-1][0]
        if pd.notna(current_date) and pd.notna(last_date):
            try:
                delta = (current_date - last_date).days
                stats["days_rest"] = max(delta, 0)
            except (TypeError, ValueError):
                stats["days_rest"] = np.nan
        else:
            stats["days_rest"] = np.nan

        # Minutes on court in last 10 days (decay-weighted)
        if pd.notna(current_date):
            cutoff_10d = current_date - pd.Timedelta(days=10)
            recent_minutes = []
            recent_days_ago = []
            for dt, mins in self.match_history:
                if pd.notna(dt) and dt >= cutoff_10d and dt < current_date:
                    # Guard against pd.NA / pd.NaT that np.isnan cannot handle
                    if mins is None or (isinstance(mins, float) and np.isnan(mins)):
                        safe_mins = 0.0
                    else:
                        safe_mins = float(mins) if pd.notna(mins) else 0.0
                    recent_minutes.append(safe_mins)
                    try:
                        days_ago = (current_date - dt).days
                    except (TypeError, ValueError):
                        continue
                    recent_days_ago.append(days_ago)
            if recent_minutes:
                weights = np.exp(-0.1 * np.array(recent_days_ago))
                stats["minutes_on_court_last_10_days"] = float(
                    np.sum(np.array(recent_minutes) * weights)
                )
            else:
                stats["minutes_on_court_last_10_days"] = 0.0
        else:
            stats["minutes_on_court_last_10_days"] = np.nan

        # Matches in last 7 days
        if pd.notna(current_date):
            cutoff_7d = current_date - pd.Timedelta(days=7)
            count = sum(
                1
                for dt, _ in self.match_history
                if pd.notna(dt) and dt >= cutoff_7d and dt < current_date
            )
            stats["matches_last_7_days"] = count
        else:
            stats["matches_last_7_days"] = 0
        return stats

    def update(self, date: pd.Timestamp, minutes: float) -> None:
        """Record a new match. Call AFTER feature extraction."""
        if minutes is None or (isinstance(minutes, float) and np.isnan(minutes)):
            safe_minutes: float = 0.0
        else:
            safe_minutes = float(minutes) if pd.notna(minutes) else 0.0
        self.match_history.append((date, safe_minutes))
        if len(self.match_history) > 200:
            self.match_history = self.match_history[-200:]


def compute_fatigue_features(
    df_original: pd.DataFrame, return_state: bool = False
) -> pd.DataFrame | tuple[pd.DataFrame, dict[Any, FatigueTracker]]:
    """Compute fatigue features on the ORIGINAL (non-symmetric) dataset.

    Forward-only: features at match i use data from matches 0..i-1.
    With return_state=True, also returns the per-player trackers (picklable dict).
    """
    logger.info("\n  Computing fatigue & conditioning features ...")
    sort_cols = [
        c
        for c in ["match_date_est", "tourney_date", "match_num"]
        if c in df_original.columns
    ]
    df = df_original.sort_values(sort_cols).reset_index(drop=True)
    has_est_date = "match_date_est" in df.columns
    trackers: dict[Any, FatigueTracker] = defaultdict(FatigueTracker)
    records = []
    for idx in range(len(df)):
        row = df.iloc[idx]
        w_id = row["winner_id"]
        l_id = row["loser_id"]
        # Use round-based estimated date so intra-tournament fatigue is visible.
        match_date = row["match_date_est"] if has_est_date else row["tourney_date"]
        minutes = row.get("minutes", np.nan)
        w_fatigue = trackers[w_id].get_fatigue_stats(match_date)
        l_fatigue = trackers[l_id].get_fatigue_stats(match_date)
        record = {}
        for key in w_fatigue:
            record[f"winner_{key}"] = w_fatigue[key]
            record[f"loser_{key}"] = l_fatigue[key]
        records.append(record)
        trackers[w_id].update(match_date, minutes)
        trackers[l_id].update(match_date, minutes)
    fatigue_df = pd.DataFrame(records, index=df.index)
    result = pd.concat([df, fatigue_df], axis=1)
    logger.info(f"  Fatigue features computed for {len(result):,} matches")
    if return_state:
        return result, dict(trackers)
    return result
