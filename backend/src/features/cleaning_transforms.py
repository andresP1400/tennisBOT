"""Row-level transforms for the cleaning pipeline.

Split out of features/cleaning.py to respect the 300-line module budget
(AGENT.md): incomplete-match removal, date parsing and imputation only.
"""

import os
import sys

import pandas as pd

from logging_config import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402


def remove_incomplete_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Remove walkovers (W/O) and retirements (RET) from the score column."""
    before = len(df)
    # Drop rows where score contains W/O or RET (case insensitive)
    mask = (
        df["score"]
        .astype(str)
        .str.contains(r"W/O|RET|DEF|Def|w/o|ret", na=False, regex=True)
    )
    df = df[~mask].copy()
    removed = before - len(df)
    logger.info(f"  Removed {removed:,} incomplete matches (W/O, RET, DEF)")
    return df


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Parse tourney_date (YYYYMMDD int) into proper datetime columns.

    Also builds match_date_est = tourney_date + ROUND_DAY_OFFSET so that
    fatigue and intra-tournament ordering are not collapsed onto the start date.
    """
    df["tourney_date"] = pd.to_datetime(
        df["tourney_date"].astype(str), format="%Y%m%d", errors="coerce"
    )
    df["year"] = df["tourney_date"].dt.year
    df["month"] = df["tourney_date"].dt.month
    df["day_of_year"] = df["tourney_date"].dt.dayofyear

    if "round" in df.columns:
        offset_days = df["round"].map(config.ROUND_DAY_OFFSET).fillna(0).astype(int)
        df["match_date_est"] = df["tourney_date"] + pd.to_timedelta(
            offset_days, unit="D"
        )
    else:
        df["match_date_est"] = df["tourney_date"]
    return df


def impute_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Use fixed rank defaults; leave demographics to training-fold imputation.

    Dataset-wide age/height means would expose future validation/test values.
    """
    df = df.copy()
    # Rankings
    for col in ["winner_rank", "loser_rank"]:
        if col in df.columns:
            n_missing = df[col].isna().sum()
            df[col] = df[col].fillna(config.DEFAULT_RANK_IMPUTATION)
            if n_missing > 0:
                logger.info(
                    f"  Imputed {n_missing:,} missing {col} -> {config.DEFAULT_RANK_IMPUTATION}"
                )
    # Ranking points
    for col in ["winner_rank_points", "loser_rank_points"]:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    return df
