"""ELO feature computation for the TennisBot pipeline.

The rating engine (EloRatingSystem + set-margin parsing) lives in
features/elo_system.py; this module exposes compute_elo_features(), which
walks the ORIGINAL (non-symmetric) dataset chronologically and attaches
pre-match ELO columns.
"""
from __future__ import annotations

import pandas as pd

from logging_config import get_logger
from features.elo_system import EloRatingSystem

logger = get_logger(__name__)


def compute_elo_features(df_original: pd.DataFrame, return_state: bool = False):
    """Compute ELO features on the ORIGINAL (non-symmetric) dataset.

    The DataFrame must have winner/loser columns and be sorted by date.
    Returns a DataFrame with elo columns added, which will later be mapped
    into the symmetric p1/p2 format.

    With return_state=True, also returns the EloRatingSystem with the final
    post-build ratings (used for live inference).

    CRITICAL: ELO at row i uses only matches 0..i-1 (forward-only).
    """
    logger.info("\n  Computing ELO ratings (forward-only) ...")

    # Ensure sorted chronologically (match_date_est orders rounds within
    # the same tournament, so a final never updates ratings before a R32)
    sort_cols = [c for c in ["match_date_est", "tourney_date", "match_num"] if c in df_original.columns]
    df = df_original.sort_values(sort_cols).reset_index(drop=True)

    has_est_date = "match_date_est" in df.columns

    elo_system = EloRatingSystem()

    elo_records = []

    for idx in range(len(df)):
        row = df.iloc[idx]
        w_id = row["winner_id"]
        l_id = row["loser_id"]
        surface = row.get("surface", None)
        match_date = row["match_date_est"] if has_est_date else row["tourney_date"]

        # Decay ratings for long layoffs BEFORE reading them
        elo_system.apply_inactivity_decay(w_id, match_date)
        elo_system.apply_inactivity_decay(l_id, match_date)

        # Read PRE-match ratings
        pre_match = {
            "winner_elo": elo_system.get_rating(w_id),
            "loser_elo": elo_system.get_rating(l_id),
            "winner_elo_surface": elo_system.get_rating(w_id, surface),
            "loser_elo_surface": elo_system.get_rating(l_id, surface),
            "winner_elo_blend": elo_system.get_blended_rating(w_id, surface),
            "loser_elo_blend": elo_system.get_blended_rating(l_id, surface),
            "winner_elo_matches": elo_system.get_match_count(w_id),
            "loser_elo_matches": elo_system.get_match_count(l_id),
        }
        elo_records.append(pre_match)

        # Update ratings (AFTER reading pre-match)
        elo_system.update(
            w_id, l_id, surface,
            level=row.get("tourney_level", None),
            score=row.get("score", None),
            date=match_date,
        )

    elo_df = pd.DataFrame(elo_records, index=df.index)

    # Merge with original
    result = pd.concat([df, elo_df], axis=1)

    logger.info(f"  ELO computed for {len(result):,} matches")
    logger.info(f"  Unique players tracked: {len(elo_system.ratings_global)}")

    if return_state:
        return result, elo_system
    return result
