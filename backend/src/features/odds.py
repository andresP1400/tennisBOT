"""Bookmaker odds features.

Source: tennis-data.co.uk (free, historical ATP/WTA odds).
Contains: Bet365, Pinnacle, Avg market, Max market odds for each match.

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

import glob
import os
import re
import sys

import numpy as np
import pandas as pd

from logging_config import get_logger
logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _extract_last_name(full_name: str) -> str:
    """Extract a normalized last-name token for fuzzy matching.

    Sackmann format:        'Roger Federer'    -> 'federer'
    tennis-data format:    'Federer R.'       -> 'federer'
    Multi-word surname:    'Juan Martin Del Potro' -> 'potro'
    """
    if not isinstance(full_name, str) or not full_name.strip():
        return ""
    name = full_name.strip()
    name = re.sub(r"\b[A-Z]\.\s*", "", name).strip()
    name = name.rstrip(". ")
    if not name:
        return ""
    return name.split()[-1].lower()


def load_odds_from_tennis_data(tour: str = "atp") -> pd.DataFrame:
    """Load all odds files downloaded from tennis-data.co.uk.

    Files are in data/raw/{tour}/odds/ as xlsx or csv.
    Returns a unified DataFrame with standardized column names.

    Handles every historical file layout:
      - 2001:        CBW/CBL, GBW/GBL, IWW/IWL, SBW/SBL (no B365/Pinnacle/Avg)
      - 2002-2005:   + B365W/B365L, EXW/EXL, PSW/PSL (Pinnacle from 2004)
      - 2006-2007:   + UBW/UBL
      - 2008-2012:   + LBW/LBL (Ladbrokes)
      - 2013-2014:   + SJW/SJL (Stan James)
      - 2015-2024:   B365W/B365L, PSW/PSL, MaxW/MaxL, AvgW/AvgL
      - 2025+:       + BFEW/BFEL (Betfair Exchange)

    Internal column names (winner / loser side):
      b365_w/b365_l  Bet365                ps_w/ps_l      Pinnacle
      cb_w/cb_l      Centrebet             ex_w/ex_l      Bet365 Exchange
      lb_w/lb_l      Ladbrokes             ub_w/ub_l      Bet365 UK
      iw_w/iw_l      Interwetten           sj_w/sj_l      Stan James
      gb_w/gb_l      William Hill GB       sb_w/sb_l      Stan James UK
      bf_w/bf_l      Betfair Exchange      max_w/max_l    Max market
      avg_w/avg_l    Avg market (real, or synthetic fallback)
    """
    odds_dir = os.path.join(config.RAW_DIR, tour, "odds")
    if not os.path.exists(odds_dir):
        logger.info(f"  [INFO] No odds directory found: {odds_dir}")
        return pd.DataFrame()
    files = sorted(
        glob.glob(os.path.join(odds_dir, "*.xlsx"))
        + glob.glob(os.path.join(odds_dir, "*.xls"))
        + glob.glob(os.path.join(odds_dir, "*.csv"))
    )
    if not files:
        logger.info(f"  [INFO] No odds files found in {odds_dir}")
        return pd.DataFrame()
    logger.info(f"  Loading {len(files)} odds files from {odds_dir} ...")
    frames: list[pd.DataFrame] = []
    for fp in files:
        try:
            if fp.endswith(".csv"):
                df = pd.read_csv(fp, low_memory=False, encoding="latin-1")
            else:
                df = None
                try:
                    df = pd.read_excel(fp, engine="openpyxl")
                except Exception:
                    try:
                        df = pd.read_excel(fp, engine="xlrd")
                    except Exception:
                        try:
                            df = pd.read_html(fp)[0]
                        except Exception:
                            logger.warning(f"    [WARN] Could not read {os.path.basename(fp)} with any engine")
                            continue
            frames.append(df)
        except Exception as exc:
            logger.warning(f"    [WARN] Failed to read {os.path.basename(fp)}: {exc}")
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    logger.info(f"  Loaded {len(combined):,} odds records total")
    # Standardize columns: tennis-data.co.uk naming -> internal naming
    col_map: dict = {}
    for col in combined.columns:
        cl = str(col).strip().lower()
        if cl == "date":
            col_map[col] = "odds_date"
        elif cl == "winner":
            col_map[col] = "odds_winner"
        elif cl == "loser":
            col_map[col] = "odds_loser"
        elif cl == "psw":
            col_map[col] = "ps_w"
        elif cl == "psl":
            col_map[col] = "ps_l"
        elif cl == "b365w":
            col_map[col] = "b365_w"
        elif cl == "b365l":
            col_map[col] = "b365_l"
        elif cl == "maxw":
            col_map[col] = "max_w"
        elif cl == "maxl":
            col_map[col] = "max_l"
        elif cl == "avgw":
            col_map[col] = "avg_w"
        elif cl == "avgl":
            col_map[col] = "avg_l"
        elif cl == "bfew":
            col_map[col] = "bf_w"
        elif cl == "bfel":
            col_map[col] = "bf_l"
        elif cl == "exw":
            col_map[col] = "ex_w"
        elif cl == "exl":
            col_map[col] = "ex_l"
        elif cl == "cbw":
            col_map[col] = "cb_w"
        elif cl == "cbl":
            col_map[col] = "cb_l"
        elif cl == "lbw":
            col_map[col] = "lb_w"
        elif cl == "lbl":
            col_map[col] = "lb_l"
        elif cl == "ubw":
            col_map[col] = "ub_w"
        elif cl == "ubl":
            col_map[col] = "ub_l"
        elif cl == "iww":
            col_map[col] = "iw_w"
        elif cl == "iwl":
            col_map[col] = "iw_l"
        elif cl == "sjw":
            col_map[col] = "sj_w"
        elif cl == "sjl":
            col_map[col] = "sj_l"
        elif cl == "gbw":
            col_map[col] = "gb_w"
        elif cl == "gbl":
            col_map[col] = "gb_l"
        elif cl == "sbw":
            col_map[col] = "sb_w"
        elif cl == "sbl":
            col_map[col] = "sb_l"
    combined = combined.rename(columns=col_map)
    if "odds_date" in combined.columns:
        combined["odds_date"] = pd.to_datetime(combined["odds_date"], errors="coerce")
    if "odds_winner" in combined.columns:
        combined["odds_winner_key"] = combined["odds_winner"].apply(_extract_last_name)
    if "odds_loser" in combined.columns:
        combined["odds_loser_key"] = combined["odds_loser"].apply(_extract_last_name)
    _add_synthetic_avg(combined)
    return combined


# Columns that participate in the synthetic average fallback, winner/loser.
_SYNTH_AVG_COLS = [
    ("b365_w", "b365_l"), ("ps_w", "ps_l"), ("cb_w", "cb_l"),
    ("ex_w", "ex_l"), ("lb_w", "lb_l"), ("ub_w", "ub_l"),
    ("iw_w", "iw_l"), ("sj_w", "sj_l"), ("gb_w", "gb_l"), ("sb_w", "sb_l"),
]


def _add_synthetic_avg(df: pd.DataFrame) -> None:
    """Fill avg_w/avg_l with the mean of available bookmaker columns for rows
    where the file did not publish a real Avg (legacy layouts, e.g. 2001-2006).
    Real Avg values are never overwritten."""
    if "avg_w" not in df.columns:
        df["avg_w"] = np.nan
        df["avg_l"] = np.nan
    win_cols = [w for w, _ in _SYNTH_AVG_COLS if w in df.columns]
    lose_cols = [loss for _, loss in _SYNTH_AVG_COLS if loss in df.columns]
    if not win_cols:
        return
    need = df["avg_w"].isna()
    if not need.any():
        return
    win_num = df.loc[need, win_cols].apply(pd.to_numeric, errors="coerce")
    lose_num = df.loc[need, lose_cols].apply(pd.to_numeric, errors="coerce")
    df.loc[need, "avg_w"] = win_num.mean(axis=1, skipna=True)
    df.loc[need, "avg_l"] = lose_num.mean(axis=1, skipna=True)
    filled = df.loc[need, "avg_w"].notna().sum()
    if filled:
        logger.info(f"  [INFO] avg_w/avg_l: synthetic average filled for {filled:,} legacy rows")


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
    work["_w_key"] = work["winner_name"].apply(_extract_last_name)
    work["_l_key"] = work["loser_name"].apply(_extract_last_name)
    work["_yw"] = _year_week_key(work["tourney_date"])
    if "odds_winner_key" not in odds.columns:
        odds["odds_winner_key"] = (
            odds.get("odds_winner", pd.Series(dtype=str)).apply(_extract_last_name)
        )
    if "odds_loser_key" not in odds.columns:
        odds["odds_loser_key"] = (
            odds.get("odds_loser", pd.Series(dtype=str)).apply(_extract_last_name)
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
