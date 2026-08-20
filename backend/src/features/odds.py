"""Bookmaker odds features — merge + line-movement logic.

Loading + standardization of tennis-data.co.uk files lives in
features/odds_loading.py. This module keeps the merge entry points that
the pipeline imports (load_odds_data, merge_odds_to_matches).

Sources: tennis-data.co.uk (free, historical ATP/WTA odds): Bet365,
Pinnacle, Avg market, Max market odds for each match.

Computes:
  - opening_odds  — sharp open reference (Pinnacle → Betfair Exchange → Bet365 → Avg)
  - closing_odds  — market close reference (Avg consensus → Max → Pinnacle)
  - line_movement = closing - opening

Notes on "closing":
  tennis-data publishes one post-match odds snapshot, not a true open/close
  pair per book. We treat Avg as the best free *closing consensus* and Max as
  a soft upper bound. CLV metrics label the source accordingly.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

from logging_config import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from features.odds_loading import (  # noqa: E402
    extract_last_name,
    load_odds_from_tennis_data,
)


def load_odds_data(odds_path: str | None = None, tour: str = "atp") -> pd.DataFrame:
    """Load bookmaker odds.

    Priority:
      1. If odds_path is given, load that CSV/xlsx
      2. Otherwise, try loading from tennis-data.co.uk files in
         data/raw/{tour}/odds/
    """
    if odds_path and os.path.exists(odds_path):
        logger.info(f"  Loading odds data from {odds_path} ...")
        if odds_path.endswith(".csv"):
            df = pd.read_csv(odds_path, low_memory=False)
        else:
            df = pd.read_excel(odds_path, engine="openpyxl")
        logger.info(f"  Loaded {len(df):,} odds records")
        return df
    return load_odds_from_tennis_data(tour)


def _year_week_key(date_series: pd.Series) -> pd.Series:
    """Create YYYY-WW key from dates for fuzzy temporal matching."""
    dt = pd.to_datetime(date_series, errors="coerce")
    year = dt.dt.isocalendar().year.astype(str)
    week = dt.dt.isocalendar().week.astype(str).str.zfill(2)
    return year + "-" + week


def merge_odds_to_matches(
    matches_df: pd.DataFrame,
    odds_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Merge odds data into the match DataFrame.

    Accepts either the original (winner/loser) or the symmetric
    (p1/p2) schema. The function maps p1 -> winner and p2 -> loser
    for keying when needed, but the output columns always reflect
    the original winner/loser semantics so downstream pipeline code
    can stay consistent.

    Uses last-name + ISO week matching to join the two sources.
    Produces: winner_opening_odds, loser_opening_odds,
              winner_closing_odds, loser_closing_odds,
              winner_line_movement, loser_line_movement.
    """
    nan_cols = [
        "winner_opening_odds", "loser_opening_odds",
        "winner_closing_odds", "loser_closing_odds",
        "winner_line_movement", "loser_line_movement",
    ]
    if odds_df is None or odds_df.empty:
        for col in nan_cols:
            matches_df[col] = np.nan
        return matches_df

    # Accept either winner/loser or p1/p2 schema. Build a temporary
    # view that always has winner_name / loser_name.
    work = matches_df.copy()
    if "winner_name" not in work.columns:
        if "p1_name" in work.columns:
            work["winner_name"] = work["p1_name"]
            work["loser_name"] = work["p2_name"]
        else:
            for col in nan_cols:
                work[col] = np.nan
            return work

    odds = odds_df.copy()
    # Backward compatibility: older user-supplied CSVs use pinnacle_w/pinnacle_l.
    if "pinnacle_w" in odds.columns and "ps_w" not in odds.columns:
        odds["ps_w"] = odds["pinnacle_w"]
        odds["ps_l"] = odds["pinnacle_l"]
    # Opening reference priority (sharp -> soft):
    #   1) Pinnacle         — sharpest fixed-odds book
    #   2) Betfair Exchange — sharpest exchange (BFEW/BFEL, 2025+ files)
    #   3) Bet365           — retail European book
    #   4) Avg              — consensus (incl. synthetic fallback for legacy files)
    if "ps_w" in odds.columns and odds["ps_w"].notna().any():
        odds["_open_w"] = odds["ps_w"]
        odds["_open_l"] = odds["ps_l"]
        open_source = "Pinnacle"
    elif "bf_w" in odds.columns and odds["bf_w"].notna().any():
        odds["_open_w"] = odds["bf_w"]
        odds["_open_l"] = odds["bf_l"]
        open_source = "Betfair Exchange"
    elif "b365_w" in odds.columns and odds["b365_w"].notna().any():
        odds["_open_w"] = odds["b365_w"]
        odds["_open_l"] = odds["b365_l"]
        open_source = "Bet365"
    elif "avg_w" in odds.columns and odds["avg_w"].notna().any():
        odds["_open_w"] = odds["avg_w"]
        odds["_open_l"] = odds["avg_l"]
        open_source = "Average"
    else:
        logger.warning("  [WARN] No recognized odds columns found. Skipping odds merge.")
        for col in nan_cols:
            matches_df[col] = np.nan
        return matches_df

    # Closing reference priority:
    #   1) Avg  — market consensus (best free CLV anchor)
    #   2) Max  — softest available line (upper bound, not sharp close)
    #   3) same as open (no separate close)
    if "avg_w" in odds.columns and odds["avg_w"].notna().any():
        odds["_close_w"] = odds["avg_w"]
        odds["_close_l"] = odds["avg_l"]
        close_source = "Avg"
    elif "max_w" in odds.columns:
        odds["_close_w"] = odds["max_w"]
        odds["_close_l"] = odds["max_l"]
        close_source = "Max"
    elif "ps_w" in odds.columns:
        odds["_close_w"] = odds["ps_w"]
        odds["_close_l"] = odds["ps_l"]
        close_source = "Pinnacle"
    else:
        odds["_close_w"] = odds["_open_w"]
        odds["_close_l"] = odds["_open_l"]
        close_source = open_source

    logger.info(f"  Odds source: open={open_source}, close={close_source}")
    work["_w_key"] = work["winner_name"].apply(extract_last_name)
    work["_l_key"] = work["loser_name"].apply(extract_last_name)
    work["_yw"] = _year_week_key(work["tourney_date"])
    if "odds_winner_key" not in odds.columns:
        odds["odds_winner_key"] = (
            odds.get("odds_winner", pd.Series(dtype=str)).apply(extract_last_name)
        )
    if "odds_loser_key" not in odds.columns:
        odds["odds_loser_key"] = (
            odds.get("odds_loser", pd.Series(dtype=str)).apply(extract_last_name)
        )
    if "odds_date" in odds.columns:
        odds["_yw"] = _year_week_key(odds["odds_date"])
    else:
        odds["_yw"] = None

    odds_subset = odds[
        ["_yw", "odds_winner_key", "odds_loser_key",
         "_open_w", "_open_l", "_close_w", "_close_l"]
    ].dropna(subset=["odds_winner_key", "odds_loser_key", "_yw"]).copy()
    odds_subset = odds_subset.drop_duplicates(
        subset=["_yw", "odds_winner_key", "odds_loser_key"],
        keep="first",
    )
    merged = work.merge(
        odds_subset,
        left_on=["_yw", "_w_key", "_l_key"],
        right_on=["_yw", "odds_winner_key", "odds_loser_key"],
        how="left",
        suffixes=("", "_odds"),
    )
    # Ensure the odds columns are always present (may be missing if the
    # merge produced zero rows or if all rows had NaN keys).
    for col in ["_open_w", "_open_l", "_close_w", "_close_l"]:
        if col not in merged.columns:
            merged[col] = np.nan
    merged["winner_opening_odds"] = pd.to_numeric(merged["_open_w"], errors="coerce")
    merged["loser_opening_odds"] = pd.to_numeric(merged["_open_l"], errors="coerce")
    merged["winner_closing_odds"] = pd.to_numeric(merged["_close_w"], errors="coerce")
    merged["loser_closing_odds"] = pd.to_numeric(merged["_close_l"], errors="coerce")
    merged["winner_line_movement"] = (
        merged["winner_closing_odds"] - merged["winner_opening_odds"]
    )
    merged["loser_line_movement"] = (
        merged["loser_closing_odds"] - merged["loser_opening_odds"]
    )
    drop_cols = [
        "_w_key", "_l_key", "_yw",
        "_open_w", "_open_l", "_close_w", "_close_l",
        "odds_winner_key", "odds_loser_key",
    ]
    merged = merged.drop(columns=[c for c in drop_cols if c in merged.columns], errors="ignore")

    matched = merged["winner_opening_odds"].notna().sum()
    if len(merged) > 0:
        logger.info(
            f"  Odds merged for {matched:,} / {len(merged):,} matches "
            f"({100 * matched / len(merged):.1f}%)"
        )
    else:
        logger.info("  Odds merge produced 0 matches (likely no overlapping keys).")
    # Copy back to the user's frame (without the temp winner_name
    # / loser_name aliasing columns).
    for col in nan_cols:
        matches_df[col] = merged[col].values
    return matches_df
