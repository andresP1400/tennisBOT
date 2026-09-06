"""Data loading and cleaning orchestrator.

Thin orchestration layer (AGENT.md pattern): implementations live in
  - features/cleaning_loaders.py     (raw CSV loading)
  - features/cleaning_transforms.py  (row-level transforms, imputation)
  - features/cleaning_enrichment.py  (indoor/altitude flags, symmetric rows)
This module re-exports the public surface so existing imports
`from features.cleaning import ...` keep working.
"""

import os
import sys

import pandas as pd

from logging_config import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

from features.cleaning_loaders import (  # noqa: F401
    load_players,
    load_raw_matches,
)
from features.cleaning_transforms import (  # noqa: F401
    impute_missing,
    parse_dates,
    remove_incomplete_matches,
)
from features.cleaning_enrichment import (  # noqa: F401
    add_altitude,
    add_indoor_flag,
    create_symmetric_rows,
)

__all__ = [
    "load_raw_matches",
    "load_players",
    "remove_incomplete_matches",
    "parse_dates",
    "impute_missing",
    "add_indoor_flag",
    "add_altitude",
    "create_symmetric_rows",
    "clean_pipeline",
]


def clean_pipeline(
    tour: str = "atp", start_year: int | None = None, end_year: int | None = None
) -> pd.DataFrame:
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
