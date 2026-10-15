"""Disjoint annual stages for frozen chronological out-of-sample evaluation."""

from __future__ import annotations

import pandas as pd


def annual_partitions(
    frame: pd.DataFrame, test_year: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """No fitting-stage label may become available during the following stage."""
    selection_year, calibration_year = test_year - 2, test_year - 1
    training = frame[
        (frame.year >= 2008)
        & (frame.year < selection_year)
        & (frame.available_at < pd.Timestamp(f"{selection_year}-01-01"))
    ]
    selection = frame[
        (frame.year == selection_year)
        & (frame.available_at < pd.Timestamp(f"{calibration_year}-01-01"))
    ]
    calibration = frame[
        (frame.year == calibration_year)
        & (frame.available_at < pd.Timestamp(f"{test_year}-01-01"))
    ]
    testing = frame[
        (frame.year == test_year)
        & (frame.available_at <= pd.Timestamp.today().normalize())
    ]
    parts = training, selection, calibration, testing
    if any(part.empty for part in parts):
        raise ValueError(
            "All annual train/selection/calibration/test stages require mature real matches"
        )
    return parts


def evaluation_metadata(test: pd.DataFrame, test_year: int | None) -> dict[str, object]:
    """Observed source coverage is distinct from a complete calendar year."""
    return {
        "period": (
            "2024–2025"
            if test_year is None
            else f"{test_year} (available source matches)"
        ),
        "test_start": str(test.date.min().date()),
        "test_end": str(test.date.max().date()),
        "protocol": "Frozen estimators; chronological stages; 21-day result availability embargo",
        "coverage_note": "Source coverage is partial and does not establish every match in the period",
    }
