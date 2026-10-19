"""Feature Builder -- Orchestrates the full feature engineering pipeline.

Steps:
  1. Load raw matches (non-symmetric, from cleaning module or directly)
  2. Compute forward-only features on ORIGINAL data:
     - ELO (global + surface)
     - Rolling stats (exp-decay)
     - Fatigue
     - H2H
     - Odds (if available)
  3. Compute context features (surface, level, round encoding)
  4. Create symmetric rows (winner=p1/label=1, loser=p1/label=0)
  5. Compute player-level diff features on symmetric data
  6. Compute all diff columns (p1 - p2) from the forward-only features
  7. Filter to reliable stats era (>= 2000)
  8. Save final dataset

The heavy lifting is in features/builder_helpers.py; this module keeps
the orchestration entry point build_features().
"""

import os
import sys

import numpy as np
import pandas as pd

from logging_config import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from features.builder_helpers import (  # noqa: E402
    compute_news_features,
    save_inference_state,
)
from features.builder_symmetric import (  # noqa: E402
    compute_diffs,
    rename_forward_features_for_symmetric,
)
from features.cleaning import (  # noqa: E402
    add_altitude,
    add_indoor_flag,
    create_symmetric_rows,
    impute_missing,
    load_raw_matches,
    parse_dates,
    remove_incomplete_matches,
)
from features.context import compute_context_features  # noqa: E402
from features.elo import compute_elo_features  # noqa: E402
from features.fatigue import compute_fatigue_features  # noqa: E402
from features.h2h import compute_h2h_features  # noqa: E402
from features.odds import load_odds_data, merge_odds_to_matches  # noqa: E402
from features.player import compute_player_features  # noqa: E402
from features.rolling_stats import compute_rolling_features  # noqa: E402
from features.weather import compute_weather_features  # noqa: E402


def build_features(
    tour: str = "atp",
    start_year: int | None = None,
    end_year: int | None = None,
    odds_path: str | None = None,
    stats_from_year: int | None = None,
) -> pd.DataFrame:
    """Full feature engineering pipeline.

    Parameters
    ----------
    tour : str
        'atp' or 'wta'
    start_year, end_year : int or None
        Year range for loading raw data.
    odds_path : str or None
        Path to odds CSV. None = skip odds features.
    stats_from_year : int or None
        Only output rows from this year onwards.
    """
    stats_from_year = stats_from_year or config.STATS_RELIABLE_FROM
    logger.info("\n" + "=" * 70)
    logger.info(f"  FEATURE ENGINEERING PIPELINE - {tour.upper()}")
    logger.info("=" * 70)
    logger.info("\n[1/10] Loading raw matches ...")
    df = load_raw_matches(tour, start_year, end_year)

    logger.info("\n[2/10] Cleaning data ...")
    df = remove_incomplete_matches(df)
    df = parse_dates(df)
    df = impute_missing(df)
    df = add_indoor_flag(df)
    df = add_altitude(df)

    # Forward-only features with return_state for live inference
    logger.info("\n[3/10] Computing ELO ratings ...")
    df, elo_state = compute_elo_features(df, return_state=True)
    logger.info("\n[4/10] Computing rolling statistics ...")
    df, rolling_state = compute_rolling_features(df, return_state=True)
    logger.info("\n[5/10] Computing fatigue features ...")
    df, fatigue_state = compute_fatigue_features(df, return_state=True)
    logger.info("\n[6/10] Computing H2H features ...")
    df, h2h_state = compute_h2h_features(df, return_state=True)

    logger.info("\n[6b/10] Processing odds ...")
    odds_df = load_odds_data(odds_path, tour=tour)
    df = merge_odds_to_matches(df, odds_df)

    # Weather is RUNTIME-only (API). Batch historical fetch is slow/rate-limited
    # and weather columns are NOT in ALL_FEATURES, so skip live API during build.
    logger.info(
        "\n[6c/10] Weather columns left empty for batch (live via /api/weather) ..."
    )
    for col in [
        "temperature_c",
        "wind_speed_kmh",
        "rain_probability",
        "humidity_pct",
        "cloud_cover_pct",
    ]:
        if col not in df.columns:
            df[col] = np.nan
    # Optional opt-in for offline research: TENNISBOT_BATCH_WEATHER=1
    if config.settings.tennisbot_batch_weather.strip() in ("1", "true", "yes"):
        try:
            df = compute_weather_features(df)
        except Exception as exc:
            logger.warning(f"  Weather batch fetch failed: {exc}")

    logger.info("\n[6d/10] Computing player news placeholders ...")
    df = compute_news_features(df)

    logger.info("\n[7/10] Creating symmetric rows ...")
    sym = create_symmetric_rows(df)

    sym = rename_forward_features_for_symmetric(df, sym)

    logger.info("\n[8/10] Computing context features ...")
    sym = compute_context_features(sym)

    logger.info("\n[9/10] Computing player-level features ...")
    sym = compute_player_features(sym)

    logger.info("\n[10/10] Computing diff features and finalizing ...")
    sym = compute_diffs(sym)

    if stats_from_year:
        before = len(sym)
        sym = sym[sym["year"] >= stats_from_year].reset_index(drop=True)
        logger.info(
            f"  Filtered to year >= {stats_from_year}: {before:,} -> {len(sym):,} rows"
        )

    threshold = config.COLD_START_THRESHOLD
    if "p1_match_count" in sym.columns and "p2_match_count" in sym.columns:
        sym["cold_start_flag"] = (
            (sym["p1_match_count"] < threshold) | (sym["p2_match_count"] < threshold)
        ).astype(int)
        n_cold = int(sym["cold_start_flag"].sum())
        logger.info(f"  Cold start matches (< {threshold} prior matches): {n_cold:,}")
    else:
        sym["cold_start_flag"] = 0

    # Serialize tracker state for live API inference
    save_inference_state(df, tour, elo_state, rolling_state, fatigue_state, h2h_state)

    # Normalize object dtypes for Parquet
    for col in sym.columns:
        if sym[col].dtype == object:
            coerced = pd.to_numeric(sym[col], errors="coerce")
            non_null = sym[col].notna().sum()
            if non_null > 0 and coerced.notna().sum() >= non_null * 0.5:
                sym[col] = coerced
            else:
                sym[col] = sym[col].astype(str)

    os.makedirs(config.PROCESSED_DIR, exist_ok=True)
    out_path = os.path.join(config.PROCESSED_DIR, f"{tour}_features.parquet")
    sym.to_parquet(out_path, index=False)
    logger.info(f"\n  Final dataset saved to: {out_path}")
    logger.info(f"  Shape: {sym.shape}")
    logger.info(f"  Year range: {sym['year'].min()} - {sym['year'].max()}")
    logger.info(f"  Unique matches: {len(sym) // 2:,}")
    return sym


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build feature dataset for tennis prediction"
    )
    parser.add_argument("--tour", default="atp", choices=["atp", "wta"])
    parser.add_argument(
        "--start",
        type=int,
        default=None,
        help="Start year for raw data loading (default: 1968)",
    )
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--odds", type=str, default=None, help="Path to odds CSV file")
    parser.add_argument(
        "--stats-from",
        type=int,
        default=None,
        help=f"Only output rows from this year (default: {config.STATS_RELIABLE_FROM})",
    )
    args = parser.parse_args()
    build_features(args.tour, args.start, args.end, args.odds, args.stats_from)
