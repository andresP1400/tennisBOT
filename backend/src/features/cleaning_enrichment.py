"""Context enrichment for the cleaning pipeline.

Split out of features/cleaning.py to respect the 300-line module budget
(AGENT.md): indoor/altitude flags and symmetric-row creation only.
"""

import os
import sys

import pandas as pd

from logging_config import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from utils.constants import (  # noqa: E402
    WINNER_TO_P1,
    LOSER_TO_P2,
    LOSER_TO_P1_MAP,
    WINNER_TO_P2_MAP,
    KNOWN_INDOOR_TOURNAMENTS,
)


def add_indoor_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Add indoor_outdoor binary flag.

    Heuristic: match tourney_name against KNOWN_INDOOR_TOURNAMENTS.
    Also uses surface == 'Carpet' as indoor indicator.
    """
    df["indoor_outdoor"] = 0  # default: outdoor

    for name in KNOWN_INDOOR_TOURNAMENTS:
        mask = df["tourney_name"].astype(str).str.contains(name, case=False, na=False)
        df.loc[mask, "indoor_outdoor"] = 1

    # Carpet surface is always indoor
    if "surface" in df.columns:
        df.loc[df["surface"] == "Carpet", "indoor_outdoor"] = 1

    n_indoor = df["indoor_outdoor"].sum()
    logger.info(f"  Flagged {n_indoor:,} matches as indoor")
    return df


def add_altitude(df: pd.DataFrame) -> pd.DataFrame:
    """Add altitude column based on tournament name/city matching."""
    df["altitude"] = 0.0

    for city, alt in config.CITY_ALTITUDE.items():
        mask = df["tourney_name"].astype(str).str.contains(city, case=False, na=False)
        df.loc[mask, "altitude"] = alt

    n_with_alt = (df["altitude"] > 0).sum()
    logger.info(f"  Assigned altitude to {n_with_alt:,} matches")
    return df


def create_symmetric_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Create two rows per match: (winner as p1, label=1) and (loser as p1, label=0).

    This ensures the model sees every matchup from both perspectives,
    preventing any bias toward the 'winner' slot.
    """
    # Shared (context) columns
    context_cols = [
        "tourney_id",
        "tourney_name",
        "tourney_date",
        "tourney_level",
        "surface",
        "draw_size",
        "best_of",
        "round",
        "minutes",
        "score",
        "year",
        "month",
        "day_of_year",
        "indoor_outdoor",
        "altitude",
        "match_num",
        "source_file",
    ]
    context_cols = [c for c in context_cols if c in df.columns]

    # --- Row 1: winner = p1, loser = p2, label = 1 ---
    rename_1 = {}
    for old, new in WINNER_TO_P1.items():
        if old in df.columns:
            rename_1[old] = new
    for old, new in LOSER_TO_P2.items():
        if old in df.columns:
            rename_1[old] = new

    row1 = df[context_cols + list(rename_1.keys())].copy()
    row1 = row1.rename(columns=rename_1)
    row1["label"] = 1
    row1["match_id"] = df.index.astype(str) + "_A"

    # --- Row 2: loser = p1, winner = p2, label = 0 ---
    rename_2 = {}
    for old, new in LOSER_TO_P1_MAP.items():
        if old in df.columns:
            rename_2[old] = new
    for old, new in WINNER_TO_P2_MAP.items():
        if old in df.columns:
            rename_2[old] = new

    row2 = df[context_cols + list(rename_2.keys())].copy()
    row2 = row2.rename(columns=rename_2)
    row2["label"] = 0
    row2["match_id"] = df.index.astype(str) + "_B"

    # Combine
    symmetric = pd.concat([row1, row2], ignore_index=True)

    # Sort chronologically, then by match_id for stability
    symmetric = symmetric.sort_values(["tourney_date", "match_id"]).reset_index(
        drop=True
    )

    logger.info(f"  Created {len(symmetric):,} symmetric rows from {len(df):,} matches")
    return symmetric
