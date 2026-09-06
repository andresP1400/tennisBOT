"""Raw-data loading for the cleaning pipeline.

Split out of features/cleaning.py to respect the 300-line module budget
(AGENT.md): this module owns CSV discovery/loading only.
"""

import glob
import os
import sys

import pandas as pd
from tqdm import tqdm

from logging_config import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from exceptions import DataNotFoundError  # noqa: E402


def load_raw_matches(
    tour: str = "atp", start_year: int | None = None, end_year: int | None = None
) -> pd.DataFrame:
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
        raise DataNotFoundError(
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
        raise DataNotFoundError(
            f"No matches loaded for {tour} in {start_year}-{end_year}"
        )

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
