"""Rolling statistics features for the TennisBot pipeline.

The per-player tracker (PlayerStatsTracker with exponential-decay rolling
stats) lives in features/player_stats_tracker.py; this module exposes
compute_rolling_features(), which walks the ORIGINAL (non-symmetric) dataset
chronologically and attaches pre-match rolling columns.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from logging_config import get_logger
from features.player_stats_tracker import PlayerStatsTracker

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def compute_rolling_features(
    df_original: pd.DataFrame, return_state: bool = False
) -> pd.DataFrame | tuple[pd.DataFrame, dict[str, PlayerStatsTracker]]:
    """Compute rolling statistics on the ORIGINAL (non-symmetric) dataset.

    CRITICAL: stats at match i use only matches 0..i-1 (forward-only).
    With return_state=True, also returns per-player trackers as a plain dict.
    """
    logger.info("\n  Computing rolling statistics (forward-only, exp-decay) ...")
    sort_cols = [
        c
        for c in ["match_date_est", "tourney_date", "match_num"]
        if c in df_original.columns
    ]
    df = df_original.sort_values(sort_cols).reset_index(drop=True)
    trackers: dict[str, Any] = defaultdict(lambda: PlayerStatsTracker())
    records = []
    for idx in range(len(df)):
        row = df.iloc[idx]
        w_id = row["winner_id"]
        l_id = row["loser_id"]
        surface = row.get("surface", None)
        w_stats = trackers[w_id].get_rolling_stats(surface)
        l_stats = trackers[l_id].get_rolling_stats(surface)
        record: dict[str, Any] = {}
        for key in w_stats:
            record[f"winner_{key}"] = w_stats[key]
            record[f"loser_{key}"] = l_stats[key]
        records.append(record)
        trackers[w_id].update(
            won=True,
            surface=surface,
            ace=row.get("w_ace", np.nan),
            df=row.get("w_df", np.nan),
            svpt=row.get("w_svpt", np.nan),
            first_in=row.get("w_1stIn", np.nan),
            first_won=row.get("w_1stWon", np.nan),
            second_won=row.get("w_2ndWon", np.nan),
            bp_saved=row.get("w_bpSaved", np.nan),
            bp_faced=row.get("w_bpFaced", np.nan),
            opp_bp_saved=row.get("l_bpSaved", np.nan),
            opp_bp_faced=row.get("l_bpFaced", np.nan),
            opp_svpt=row.get("l_svpt", np.nan),
            opp_1stIn=row.get("l_1stIn", np.nan),
            opp_1stWon=row.get("l_1stWon", np.nan),
            opp_2ndWon=row.get("l_2ndWon", np.nan),
            opp_SvGms=row.get("l_SvGms", np.nan),
            score=row.get("score", ""),
            opp_rank=row.get("loser_rank", np.nan),
        )
        trackers[l_id].update(
            won=False,
            surface=surface,
            ace=row.get("l_ace", np.nan),
            df=row.get("l_df", np.nan),
            svpt=row.get("l_svpt", np.nan),
            first_in=row.get("l_1stIn", np.nan),
            first_won=row.get("l_1stWon", np.nan),
            second_won=row.get("l_2ndWon", np.nan),
            bp_saved=row.get("l_bpSaved", np.nan),
            bp_faced=row.get("l_bpFaced", np.nan),
            opp_bp_saved=row.get("w_bpSaved", np.nan),
            opp_bp_faced=row.get("w_bpFaced", np.nan),
            opp_svpt=row.get("w_svpt", np.nan),
            opp_1stIn=row.get("w_1stIn", np.nan),
            opp_1stWon=row.get("w_1stWon", np.nan),
            opp_2ndWon=row.get("w_2ndWon", np.nan),
            opp_SvGms=row.get("w_SvGms", np.nan),
            score=row.get("score", ""),
            opp_rank=row.get("winner_rank", np.nan),
        )
    rolling_df = pd.DataFrame(records, index=df.index)
    result = pd.concat([df, rolling_df], axis=1)
    logger.info(f"  Rolling features computed for {len(result):,} matches")
    if return_state:
        # Plain dict: defaultdict with lambda factory is not picklable
        return result, dict(trackers)
    return result
