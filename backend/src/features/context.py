"""Match context features.

Encodes the contextual information about a match:
  - Surface (one-hot)
  - Tournament level (ordinal)
  - Round (ordinal)
  - Best of (3 or 5)
  - Indoor/outdoor flag
  - Altitude
  - Month (seasonality)
"""
from __future__ import annotations

import os
import sys

import pandas as pd

from logging_config import get_logger
logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402


def encode_surface(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode the surface column."""
    for surf in config.SURFACES:
        col = f"surface_{surf}"
        df[col] = (df["surface"] == surf).astype(int)
    known_mask = df["surface"].isin(config.SURFACES)
    if (~known_mask).any():
        n_unknown = (~known_mask).sum()
        logger.info(f"  [INFO] {n_unknown} matches with unknown/null surface")
    return df


def encode_tourney_level(df: pd.DataFrame) -> pd.DataFrame:
    """Ordinal encode tournament level.

    Grand Slam(4) > Masters(3) > ATP500/250(2) > Others(1)
    """
    level_map = {
        "G": 4,  # Grand Slam
        "M": 3,  # Masters 1000
        "A": 2,  # ATP 500/250
        "F": 3,  # Tour Finals (treat as Masters-level)
        "D": 1,  # Davis Cup
        "C": 0,  # Challengers
    }
    df["tourney_level_encoded"] = (
        df["tourney_level"].map(level_map).fillna(1).astype(int)
    )
    return df


def encode_round(df: pd.DataFrame) -> pd.DataFrame:
    """Ordinal encode round. Later rounds = higher value."""
    df["round_encoded"] = df["round"].map(config.ROUND_ORDER).fillna(0).astype(int)
    return df


def compute_context_features(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all context encodings."""
    logger.info("\n  Computing match context features ...")
    df = encode_surface(df)
    df = encode_tourney_level(df)
    df = encode_round(df)
    if "best_of" in df.columns:
        df["best_of"] = (
            pd.to_numeric(df["best_of"], errors="coerce").fillna(3).astype(int)
        )
    if "month" not in df.columns and "tourney_date" in df.columns:
        df["month"] = pd.to_datetime(df["tourney_date"]).dt.month
    logger.info("  Context features added: surface one-hot, level, round, best_of, month")
    return df
