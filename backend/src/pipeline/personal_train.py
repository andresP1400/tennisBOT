"""Train on 2008–2021; select on 2022; calibrate on 2023; test on 2024–2025."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from config import MODELS_DIR, REPORTS_DIR
from logging_config import get_logger
from pipeline.personal_data import build_dataset, load_history, player_index
from pipeline.personal_model import (
    Estimator,
    PersonalBundle,
    calibrate,
    elo_raw,
    raw_probability,
)
from pipeline.personal_state import Player
from pipeline.personal_metadata import runtime_metadata
from pipeline.personal_protocol import annual_partitions, evaluation_metadata
from pipeline.personal_scores import arrays, metrics, coverage_metrics
from pipeline.personal_fitting import fit_candidates, fit_calibrator

logger = get_logger(__name__)


def test_report(
    frame: pd.DataFrame,
    estimator: Estimator,
    calibrator: LogisticRegression,
    elo_calibrator: LogisticRegression,
) -> dict[str, object]:
    """Expanding-history features, frozen estimators; no test-time refitting."""
    features, labels = arrays(frame)
    ml = calibrate(calibrator, raw_probability(estimator, features))
    elo = calibrate(elo_calibrator, elo_raw(features))
    by_year = {
        str(year): metrics(
            labels[np.asarray(frame.year == year)], ml[np.asarray(frame.year == year)]
        )
        for year in sorted(frame.year.unique())
    }
    by_surface = {
        surface: metrics(
            labels[np.asarray(frame.surface == surface)],
            ml[np.asarray(frame.surface == surface)],
        )
        for surface in sorted(frame.surface.unique())
    }
    return {
        "ml_calibrated": metrics(labels, ml),
        "elo_calibrated": metrics(labels, elo),
        "ml_uncalibrated": metrics(labels, raw_probability(estimator, features)),
        "elo_uncalibrated": metrics(labels, elo_raw(features)),
        "constant_50_percent": metrics(labels, np.full(len(labels), 0.5)),
        "by_year": by_year,
        "by_surface": by_surface,
        "history_coverage": coverage_metrics(frame, ml),
    }


def chronological_partitions(
    frame: pd.DataFrame,
    test_year: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Labels must have become available before the next chronological stage."""
    if test_year is not None:
        return annual_partitions(frame, test_year)
    training = frame[
        (frame.year >= 2008)
        & (frame.year <= 2021)
        & (frame.available_at < pd.Timestamp("2022-01-01"))
    ]
    validation = frame[
        (frame.year == 2022) & (frame.available_at < pd.Timestamp("2023-01-01"))
    ]
    calibration = frame[
        (frame.year == 2023) & (frame.available_at < pd.Timestamp("2024-01-01"))
    ]
    testing = frame[(frame.year >= 2024) & (frame.year <= 2025)]
    if any(part.empty for part in [training, validation, calibration, testing]):
        raise ValueError("All chronological partitions must contain real matches")
    return training, validation, calibration, testing


def train(
    tour: str, use_recent_form: bool = True, test_year: int | None = None
) -> dict[str, object]:
    """Build real-data artifacts and save every version without replacing earlier ones."""
    history, audit = load_history(tour)
    frame, players = build_dataset(
        history, feature_schema=2, use_recent_form=use_recent_form
    )
    training, validation, calibration, testing = chronological_partitions(
        frame, test_year
    )
    estimator, family, selection = fit_candidates(training, validation)
    features, labels = arrays(calibration)
    calibrator = fit_calibrator(raw_probability(estimator, features), labels)
    elo_calibrator = fit_calibrator(elo_raw(features), labels)
    report: dict[str, object] = {
        "tour": tour,
        "family": family,
        "audit": audit,
        f"selection_{test_year - 2}" if test_year else "selection_2022": selection,
        "feature_schema": 2,
        "use_recent_form": use_recent_form,
        "opponent_adjustment": "Pre-event Elo expectation residuals and opponent serve/return baselines",
    }
    scores = test_report(testing, estimator, calibrator, elo_calibrator)
    report[f"test_{test_year}" if test_year else "test_2024_2025"] = scores
    report["evaluation"] = evaluation_metadata(testing, test_year) | {
        "metrics": scores["ml_calibrated"]
    }
    report.update(
        partition_metadata(
            history, (training, validation, calibration, testing), test_year
        )
    )
    report.update(runtime_metadata())
    return save_artifacts(
        tour, family, estimator, calibrator, elo_calibrator, players, report
    )


def partition_metadata(
    history: pd.DataFrame,
    parts: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
    test_year: int | None = None,
) -> dict[str, object]:
    """Keep the timing protocol and eligible sample counts with every artifact."""
    return {
        "splits": {
            "warmup": "2005–2007",
            "train": f"2008–{test_year - 3}" if test_year else "2008–2021",
            "selection": str(test_year - 2) if test_year else "2022",
            "calibration": str(test_year - 1) if test_year else "2023",
            "test": str(test_year) if test_year else "2024–2025",
        },
        "split_counts": {
            name: len(part)
            for name, part in zip(("train", "selection", "calibration", "test"), parts)
        },
        "data_through": str(history.date.max().date()),
        "method": "21-day result embargo; labels available before partition boundaries; frozen test estimators",
        "result_delay_days": 21,
    }


def save_artifacts(
    tour: str,
    family: str,
    estimator: Estimator,
    calibrator: LogisticRegression,
    elo_calibrator: LogisticRegression,
    players: dict[int, Player],
    report: dict[str, object],
) -> dict[str, object]:
    """Publish a local version pointer only after model and audit report are durable."""
    fingerprint = hashlib.sha256(
        json.dumps(report, sort_keys=True).encode()
    ).hexdigest()[:12]
    version = f"{tour}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{fingerprint}"
    directory = MODELS_DIR / "personal"
    directory.mkdir(parents=True, exist_ok=True)
    report["model_version"] = version
    bundle = PersonalBundle(
        tour,
        version,
        family,
        estimator,
        calibrator,
        elo_calibrator,
        players,
        player_index(players),
        str(report["data_through"]),
        report,
        feature_schema=int(str(report.get("feature_schema", 1))),
        use_recent_form=bool(report.get("use_recent_form", True)),
    )
    joblib.dump(bundle, directory / f"{version}.joblib", compress=3)
    report_directory = REPORTS_DIR / "personal" / tour
    report_directory.mkdir(parents=True, exist_ok=True)
    (report_directory / f"{version}.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    pointer = directory / f"{tour}-latest.json.tmp"
    pointer.write_text(json.dumps({"version": version}))
    pointer.replace(directory / f"{tour}-latest.json")
    logger.info(
        "Trained %s: %s",
        version,
        report.get("evaluation", report.get("test_2024_2025")),
    )
    return report


def main() -> None:
    """Train both personal-use tours from verified local historical results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tour", choices=["atp", "wta", "both"], default="both")
    parser.add_argument("--no-recent-form", action="store_true")
    parser.add_argument(
        "--test-year",
        type=int,
        help="Annual protocol: fit through year-3, select year-2, calibrate year-1, test year",
    )
    args = parser.parse_args()
    for tour in (["atp", "wta"] if args.tour == "both" else [args.tour]):
        train(tour, use_recent_form=not args.no_recent_form, test_year=args.test_year)


if __name__ == "__main__":
    main()
