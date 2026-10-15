"""Train on 2008–2021; select on 2022; calibrate on 2023; test on 2024–2025."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import MODELS_DIR, REPORTS_DIR
from logging_config import get_logger
from pipeline.personal_data import build_dataset, load_history, player_index
from pipeline.personal_model import (
    Estimator,
    PersonalBundle,
    calibrate,
    elo_raw,
    logits,
    raw_probability,
    reversed_features,
)
from pipeline.personal_state import Player

logger = get_logger(__name__)


def metrics(
    labels: NDArray[np.int64], probabilities: NDArray[np.float64]
) -> dict[str, float | int]:
    """Evaluate one row per real match; mirrored training rows are never counted."""
    result: dict[str, float | int] = {
        "matches": len(labels),
        "accuracy": float(accuracy_score(labels, probabilities >= 0.5)),
        "brier": float(brier_score_loss(labels, probabilities)),
        "log_loss": float(log_loss(labels, probabilities)),
        "roc_auc": (
            float(roc_auc_score(labels, probabilities)) if len(set(labels)) > 1 else 0.5
        ),
    }
    bins = np.minimum((probabilities * 10).astype(int), 9)
    result["ece_10_bins"] = float(
        sum(
            abs(
                float(np.mean(labels[bins == index]))
                - float(np.mean(probabilities[bins == index]))
            )
            * float(np.mean(bins == index))
            for index in range(10)
            if np.any(bins == index)
        )
    )
    return result


def arrays(frame: pd.DataFrame) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Extract real canonical player orientation for evaluation."""
    return np.asarray(frame["features"].tolist(), dtype=float), np.asarray(
        frame["label"], dtype=np.int64
    )


def fit_candidates(
    train: pd.DataFrame, validation: pd.DataFrame
) -> tuple[Estimator, str, dict[str, object]]:
    """Choose model family on 2022 only, without inspecting calibration/test data."""
    features, labels = arrays(train)
    augmented = np.concatenate([features, reversed_features(features)])
    outcomes = np.concatenate([labels, 1 - labels])
    candidates: dict[str, Estimator] = {
        "logistic": make_pipeline(
            StandardScaler(), LogisticRegression(C=0.1, max_iter=500, random_state=42)
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=180,
            max_leaf_nodes=15,
            learning_rate=0.05,
            l2_regularization=10.0,
            min_samples_leaf=60,
            early_stopping=False,
            random_state=42,
        ),
    }
    val_features, val_labels = arrays(validation)
    scores = {}
    for name, estimator in candidates.items():
        estimator.fit(augmented, outcomes)
        scores[name] = metrics(val_labels, raw_probability(estimator, val_features))
        logger.info("2022 selection %s: %s", name, scores[name])
    chosen = min(scores, key=lambda name: float(scores[name]["log_loss"]))
    return candidates[chosen], chosen, dict(scores)


def fit_calibrator(
    probabilities: NDArray[np.float64], labels: NDArray[np.int64]
) -> LogisticRegression:
    """Platt scaling fitted on a later, disjoint full year; preserve symmetry."""
    calibrator = LogisticRegression(C=1.0, fit_intercept=False, random_state=42)
    calibrator.fit(
        logits(np.concatenate([probabilities, 1 - probabilities])),
        np.concatenate([labels, 1 - labels]),
    )
    return calibrator


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
    }


def chronological_partitions(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Labels must have become available before the next chronological stage."""
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


def train(tour: str) -> dict[str, object]:
    """Build real-data artifacts and save every version without replacing earlier ones."""
    history, audit = load_history(tour)
    frame, players = build_dataset(history)
    training, validation, calibration, testing = chronological_partitions(frame)
    estimator, family, selection = fit_candidates(training, validation)
    features, labels = arrays(calibration)
    calibrator = fit_calibrator(raw_probability(estimator, features), labels)
    elo_calibrator = fit_calibrator(elo_raw(features), labels)
    report: dict[str, object] = {
        "tour": tour,
        "family": family,
        "audit": audit,
        "selection_2022": selection,
        "test_2024_2025": test_report(testing, estimator, calibrator, elo_calibrator),
    }
    report.update(
        partition_metadata(history, (training, validation, calibration, testing))
    )
    return save_artifacts(
        tour, family, estimator, calibrator, elo_calibrator, players, report
    )


def partition_metadata(
    history: pd.DataFrame,
    parts: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> dict[str, object]:
    """Keep the timing protocol and eligible sample counts with every artifact."""
    return {
        "splits": {
            "warmup": "2005–2007",
            "train": "2008–2021",
            "selection": "2022",
            "calibration": "2023",
            "test": "2024–2025",
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
    logger.info("Trained %s: %s", version, report["test_2024_2025"])
    return report


def main() -> None:
    """Train both personal-use tours from verified local historical results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tour", choices=["atp", "wta", "both"], default="both")
    args = parser.parse_args()
    for tour in (["atp", "wta"] if args.tour == "both" else [args.tour]):
        train(tour)


if __name__ == "__main__":
    main()
