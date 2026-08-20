"""
Data loading and cleaning module.

Responsibilities:
  1. Load raw CSVs into a single DataFrame
  2. Remove W/O (walkover) and RET (retirement) matches
  3. Impute missing values:
       - rank null -> 2000 (not mean)
       - height null -> global mean
  4. Parse dates, derive temporal columns
  5. Create symmetric rows (p1 vs p2) + (p2 vs p1) with label flipped
"""

import os
import sys
import glob
import pandas as pd
from tqdm import tqdm

from logging_config import get_logger
logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from utils.constants import (  # noqa: E402
    WINNER_TO_P1, LOSER_TO_P2,
    LOSER_TO_P1_MAP, WINNER_TO_P2_MAP,
    KNOWN_INDOOR_TOURNAMENTS,
)


def load_raw_matches(tour: str = "atp", start_year: int = None, end_year: int = None) -> pd.DataFrame:
    """Load and concatenate yearly match CSVs.

    Parameters
    ----------
    tour : str
        'atp' or 'wta'
    start_year, end_year : int or None
        Filter to these years. None = use config defaults.

    Returns
    -------
    pd.DataFrame with all matches, chronologically sorted.
    """
    raw_dir = os.path.join(config.RAW_DIR, tour)
    pattern = os.path.join(raw_dir, f"{tour}_matches_[0-9]*.csv")
    files = sorted(glob.glob(pattern))

    if not files:
        raise FileNotFoundError(
            f"No match files found in {raw_dir}. Run `python -m data.download` first."
        )

    start_year = start_year or config.MATCH_YEAR_START
    end_year = end_year or config.MATCH_YEAR_END

    frames = []
    for fp in tqdm(files, desc=f"Loading {tour.upper()} matches"):
        # Extract year from filename
        basename = os.path.basename(fp)
        try:
            year = int(basename.split("_")[-1].replace(".csv", ""))
        except ValueError:
            continue
        if year < start_year or year > end_year:
            continue
        try:
            df = pd.read_csv(fp, low_memory=False)
            df["source_file"] = basename
            frames.append(df)
        except Exception as exc:
            logger.warning(f"  [WARN] Could not read {fp}: {exc}")
    if not frames:
        raise ValueError(f"No matches loaded for {tour} in {start_year}-{end_year}")

    combined = pd.concat(frames, ignore_index=True)
    logger.info(f"  Loaded {len(combined):,} raw matches from {len(frames)} files")
    return combined


def load_players(tour: str = "atp") -> pd.DataFrame:
    """Load the player master file."""
    fp = os.path.join(config.RAW_DIR, tour, f"{tour}_players.csv")
    if not os.path.exists(fp):
        logger.warning(f"  [WARN] Player file not found: {fp}")
        return pd.DataFrame()
    return pd.read_csv(fp, low_memory=False)


def remove_incomplete_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Remove walkovers (W/O) and retirements (RET) from the score column."""
    before = len(df)
    # Drop rows where score contains W/O or RET (case insensitive)
    mask = df["score"].astype(str).str.contains(r"W/O|RET|DEF|Def|w/o|ret", na=False, regex=True)
    df = df[~mask].copy()
    removed = before - len(df)
    logger.info(f"  Removed {removed:,} incomplete matches (W/O, RET, DEF)")
    return df


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Parse tourney_date (YYYYMMDD int) into proper datetime columns.

    Also builds match_date_est = tourney_date + ROUND_DAY_OFFSET so that
    fatigue and intra-tournament ordering are not collapsed onto the start date.
    """
    df["tourney_date"] = pd.to_datetime(df["tourney_date"].astype(str), format="%Y%m%d", errors="coerce")
    df["year"] = df["tourney_date"].dt.year
    df["month"] = df["tourney_date"].dt.month
    df["day_of_year"] = df["tourney_date"].dt.dayofyear

    if "round" in df.columns:
        offset_days = df["round"].map(config.ROUND_DAY_OFFSET).fillna(0).astype(int)
        df["match_date_est"] = df["tourney_date"] + pd.to_timedelta(offset_days, unit="D")
    else:
        df["match_date_est"] = df["tourney_date"]
    return df


def impute_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Impute missing values following the rules:
      - rank null -> 2000 (NOT the mean)
      - height null -> global mean
      - age null -> global mean
    """
    # Rankings
    for col in ["winner_rank", "loser_rank"]:
        if col in df.columns:
            n_missing = df[col].isna().sum()
            df[col] = df[col].fillna(config.DEFAULT_RANK_IMPUTATION)
            if n_missing > 0:
                logger.info(f"  Imputed {n_missing:,} missing {col} -> {config.DEFAULT_RANK_IMPUTATION}")
    # Ranking points
    for col in ["winner_rank_points", "loser_rank_points"]:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    # Height -> global mean
    for col in ["winner_ht", "loser_ht"]:
        if col in df.columns:
            mean_ht = df[col].mean()
            n_missing = df[col].isna().sum()
            df[col] = df[col].fillna(mean_ht)
            if n_missing > 0:
                logger.info(f"  Imputed {n_missing:,} missing {col} -> {mean_ht:.1f} (mean)")
    # Age -> global mean
    for col in ["winner_age", "loser_age"]:
        if col in df.columns:
            mean_age = df[col].mean()
            n_missing = df[col].isna().sum()
            df[col] = df[col].fillna(mean_age)
            if n_missing > 0:
                logger.info(f"  Imputed {n_missing:,} missing {col} -> {mean_age:.1f} (mean)")
    return df


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
        "tourney_id", "tourney_name", "tourney_date", "tourney_level",
        "surface", "draw_size", "best_of", "round", "minutes", "score",
        "year", "month", "day_of_year", "indoor_outdoor", "altitude",
        "match_num", "source_file",
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
    symmetric = symmetric.sort_values(["tourney_date", "match_id"]).reset_index(drop=True)

    logger.info(f"  Created {len(symmetric):,} symmetric rows from {len(df):,} matches")
    return symmetric


def clean_pipeline(tour: str = "atp", start_year: int = None, end_year: int = None) -> pd.DataFrame:
    """Full cleaning pipeline: load -> clean -> impute -> augment -> symmetrize.

    Parameters
    ----------
    tour : str
    start_year, end_year : int or None

    Returns
    -------
    pd.DataFrame : cleaned, symmetric dataset ready for feature engineering.
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"  CLEANING PIPELINE - {tour.upper()}")
    logger.info(f"{'='*60}")
    # 1. Load
    df = load_raw_matches(tour, start_year, end_year)

    # 2. Remove incomplete
    df = remove_incomplete_matches(df)

    # 3. Parse dates
    df = parse_dates(df)

    # 4. Impute missing values
    df = impute_missing(df)

    # 5. Add context flags
    df = add_indoor_flag(df)
    df = add_altitude(df)

    # 6. Create symmetric rows
    sym = create_symmetric_rows(df)

    # 7. Save processed file
    os.makedirs(config.PROCESSED_DIR, exist_ok=True)
    out_path = os.path.join(config.PROCESSED_DIR, f"{tour}_cleaned.parquet")
    sym.to_parquet(out_path, index=False)
    logger.info(f"\n  Saved cleaned data to {out_path}")
    logger.info(f"  Shape: {sym.shape}")
    return sym


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Clean and prepare tennis data")
    parser.add_argument("--tour", default="atp", choices=["atp", "wta"])
    parser.add_argument("--start", type=int, default=config.STATS_RELIABLE_FROM)
    parser.add_argument("--end", type=int, default=config.MATCH_YEAR_END)
    args = parser.parse_args()

    clean_pipeline(args.tour, args.start, args.end)
