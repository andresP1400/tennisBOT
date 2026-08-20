"""Loading + standardization of tennis-data.co.uk odds files.

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
import config  # noqa: E402


def extract_last_name(full_name: str) -> str:
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
        combined["odds_winner_key"] = combined["odds_winner"].apply(extract_last_name)
    if "odds_loser" in combined.columns:
        combined["odds_loser_key"] = combined["odds_loser"].apply(extract_last_name)
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
