"""Temporal split utilities for walk-forward validation.

Rules:
  - NEVER use random k-fold on time series data
  - Walk-forward: train on [2000-Y], validate on [Y+1]
  - Final fixed split: train [2000-2021] | val [2022-2023] | test [2024+]
  - Zero shuffle before split
"""

from __future__ import annotations

from typing import Any

import os
import sys

import pandas as pd

from logging_config import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from pipeline.temporal_groups import date_partitions  # noqa: E402


def fixed_temporal_split(df: pd.DataFrame) -> dict[str, Any]:
    """Split data into train / validation / test by year.

    Uses config.TRAIN_END_YEAR / VAL_START_YEAR / VAL_END_YEAR /
    TEST_START_YEAR boundaries. When the dataset does not cover those
    fixed boundaries (e.g. the dashboard re-trains on 2025-2026 only),
    falls back to an adaptive boundary so train/val/test are never empty
    (otherwise SimpleImputer crashes on a 0-sample train set).
    """
    logger.info("\n  Temporal split (NO shuffle) ...")
    train = df[df["year"] <= config.TRAIN_END_YEAR].copy()
    val = df[
        (df["year"] >= config.VAL_START_YEAR) & (df["year"] <= config.VAL_END_YEAR)
    ].copy()
    test = df[df["year"] >= config.TEST_START_YEAR].copy()
    if len(train) == 0 or len(val) == 0 or len(test) == 0:
        train, val, test = date_partitions(df, (0.70, 0.15, 0.15))
    logger.info(
        f"  Train: {len(train):,} rows  ({train['year'].min()}-{train['year'].max()})"
    )
    logger.info(
        f"  Val:   {len(val):,} rows  ({val['year'].min()}-{val['year'].max()})"
    )
    logger.info(
        f"  Test:  {len(test):,} rows  ({test['year'].min()}-{test['year'].max()})"
    )
    return {"train": train, "val": val, "test": test}


def walk_forward_splits(
    df: pd.DataFrame,
    train_start: int | None = None,
    train_end_initial: int | None = None,
    val_years: int = 1,
    step: int = 1,
) -> list[dict[str, Any]]:
    """Generate walk-forward validation splits.

    Each split: train on [train_start, boundary], validate on
    [boundary+1, boundary+val_years].

    Skips folds whose train or val window is empty to avoid
    ZeroDivisionError downstream. When the year range is too narrow to
    produce any fold (e.g. the dashboard re-trains on a single year),
    falls back to adaptive temporal-quantile folds so OOF generation
    still works.
    """
    train_start = train_start or config.STATS_RELIABLE_FROM
    train_end_initial = train_end_initial or 2015
    max_year = df["year"].max()
    splits: list[dict[str, Any]] = []
    boundary = train_end_initial
    while boundary + val_years <= max_year:
        train = df[(df["year"] >= train_start) & (df["year"] <= boundary)].copy()
        val = df[(df["year"] > boundary) & (df["year"] <= boundary + val_years)].copy()
        if len(train) > 0 and len(val) > 0:
            splits.append(
                {
                    "train": train,
                    "val": val,
                    "train_years": f"{train_start}-{boundary}",
                    "val_years": f"{boundary+1}-{boundary+val_years}",
                    "fold": len(splits),
                }
            )
        boundary += step
    if not splits and len(df) > 0:
        splits = _adaptive_walk_forward_splits(df)
    logger.info(f"\n  Walk-forward splits generated: {len(splits)} folds")
    for s in splits:
        logger.info(
            f"    Fold {s['fold']}: train {s['train_years']} "
            f"({len(s['train']):,}), val {s['val_years']} ({len(s['val']):,})"
        )
    return splits


def _adaptive_walk_forward_splits(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Fallback folds: split time-ordered rows into quantile blocks.

    Used when the fixed year boundaries can't produce any fold (single
    year data). Order by tourney_date when available, else by year.
    Each fold i trains on blocks [0..i) and validates on block i, which
    preserves temporal ordering and guarantees non-empty folds.
    """
    column = "tourney_date" if "tourney_date" in df else "year"
    distinct = df[column].nunique()
    if distinct < 2:
        return []
    count = min(8, max(2, len(df) // 300), distinct)
    blocks = date_partitions(df, tuple([1 / count] * count))
    return [
        {
            "train": pd.concat(blocks[:index]),
            "val": blocks[index],
            "train_years": f"blocks 0-{index - 1}",
            "val_years": f"block {index}",
            "fold": index - 1,
        }
        for index in range(1, len(blocks))
    ]
