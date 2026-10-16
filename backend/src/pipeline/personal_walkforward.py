"""Annual out-of-sample evaluation without changing deployed model pointers."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from config import REPORTS_DIR
from pipeline.personal_data import load_history, build_dataset
from pipeline.personal_fitting import fit_candidates, fit_calibrator
from pipeline.personal_metadata import runtime_metadata
from pipeline.personal_model import raw_probability, elo_raw, calibrate
from pipeline.personal_protocol import annual_partitions
from pipeline.personal_scores import arrays, metrics, coverage_metrics
from pipeline.personal_train import chronological_partitions
from pipeline.personal_uncertainty import paired_date_bootstrap


@dataclass
class FoldResult:
    frame: pd.DataFrame
    report: dict[str, object]
    ml: NDArray[np.float64]
    elo: NDArray[np.float64]


def fit_and_score(
    parts: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> FoldResult:
    """All fitting/selection/calibration receives earlier data than the test rows."""
    training, selection, calibration, testing = parts
    estimator, family, selection_scores = fit_candidates(training, selection)
    calibration_features, calibration_labels = arrays(calibration)
    fitted = fit_calibrator(
        raw_probability(estimator, calibration_features), calibration_labels
    )
    elo_fitted = fit_calibrator(elo_raw(calibration_features), calibration_labels)
    features, labels = arrays(testing)
    raw = raw_probability(estimator, features)
    ml = calibrate(fitted, raw)
    elo = calibrate(elo_fitted, elo_raw(features))
    report: dict[str, object] = {
        "family": family,
        "selection_scores": selection_scores,
        "stages": {
            name: {
                "matches": len(part),
                "start": str(part.date.min().date()),
                "end": str(part.date.max().date()),
                "labels_available_through": str(part.available_at.max().date()),
            }
            for name, part in zip(("train", "selection", "calibration", "test"), parts)
        },
        "ml_calibrated": metrics(labels, ml),
        "ml_uncalibrated": metrics(labels, raw),
        "elo_calibrated": metrics(labels, elo),
        "elo_uncalibrated": metrics(labels, elo_raw(features)),
        "history_coverage": coverage_metrics(testing, ml),
    }
    return FoldResult(testing, report, ml, elo)


def evaluate_year(frame: pd.DataFrame, test_year: int) -> FoldResult:
    """Annual family choice uses year-2 and calibration uses year-1 only."""
    result = fit_and_score(annual_partitions(frame, test_year))
    result.report["test_year"] = test_year
    return result


def frozen_reference(frame: pd.DataFrame, test_year: int) -> FoldResult:
    """Compare to the original 2021-fit/2022-selection/2023-calibration protocol."""
    if test_year < 2024:
        raise ValueError("Frozen reference calibration must precede its test year")
    train, select, calibration, _ = chronological_partitions(frame)
    testing = frame[
        (frame.year == test_year)
        & (frame.available_at <= pd.Timestamp.today().normalize())
    ]
    if testing.empty:
        raise ValueError("No mature matches for the frozen reference test")
    result = fit_and_score((train, select, calibration, testing))
    result.report["test_year"] = test_year
    result.report["protocol"] = (
        "Original frozen estimator on the same newer holdout matches"
    )
    return result


def summarize_folds(results: list[FoldResult], resamples: int) -> dict[str, object]:
    """Pool real matches across disjoint annual tests; never average fold accuracies equally."""
    frame = pd.concat([result.frame for result in results], ignore_index=True)
    _, labels = arrays(frame)
    ml = np.concatenate([result.ml for result in results])
    elo = np.concatenate([result.elo for result in results])
    return {
        "ml_calibrated": metrics(labels, ml),
        "elo_calibrated": metrics(labels, elo),
        "history_coverage": coverage_metrics(frame, ml),
        "uncertainty": paired_date_bootstrap(
            labels,
            ml,
            elo,
            frame.date.to_numpy(dtype="datetime64[D]"),
            resamples=resamples,
        ),
    }


def reference_comparison(
    frame: pd.DataFrame, latest: FoldResult, resamples: int
) -> dict[str, object]:
    """The old reference is unavailable when its 2023 calibration follows a test."""
    year = int(latest.frame.year.max())
    if year < 2024:
        return {
            "latest_year_frozen_reference": None,
            "latest_year_paired_comparison": None,
        }
    reference = frozen_reference(frame, year)
    _, labels = arrays(latest.frame)
    return {
        "latest_year_frozen_reference": reference.report,
        "latest_year_paired_comparison": paired_date_bootstrap(
            labels,
            latest.ml,
            reference.ml,
            latest.frame.date.to_numpy(dtype="datetime64[D]"),
            resamples=resamples,
            reference_name="frozen_ml",
        ),
    }


def evaluate(
    frame: pd.DataFrame,
    years: tuple[int, ...],
    *,
    resamples: int = 1000,
) -> dict[str, object]:
    """Keep all annual folds and the original protocol comparison, including bad years."""
    if not years or years != tuple(sorted(set(years))):
        raise ValueError("Test years must be unique and strictly increasing")
    if not 100 <= resamples <= 10000:
        raise ValueError("Expected 100–10000 bootstrap resamples")
    results = [evaluate_year(frame, year) for year in years]
    return {
        "protocol": "Each test year: train through year-3; select year-2; calibrate year-1; freeze throughout test",
        "result_delay_days": 21,
        "test_years": list(years),
        "folds": [result.report for result in results],
        "aggregate": summarize_folds(results, resamples),
        "limitations": (
            "Retrospective chronological validation, not a new prospective trial. "
            "Source seasons may be partial. No profitability measured."
        ),
    } | reference_comparison(frame, results[-1], resamples)


def evaluate_tour(
    tour: str, years: tuple[int, ...], resamples: int = 1000
) -> dict[str, object]:
    """Verify source bytes and build features forward once for every annual fold."""
    history, audit = load_history(tour)
    frame, _ = build_dataset(history, feature_schema=2)
    report = evaluate(frame, years, resamples=resamples)
    directory = Path(__file__).parent
    evaluation_code = b"".join(
        (directory / name).read_bytes()
        for name in ("personal_walkforward.py", "personal_uncertainty.py")
    )
    return (
        report
        | {
            "tour": tour,
            "audit": audit,
            "data_through": str(history.date.max().date()),
            "feature_schema": 2,
            "use_recent_form": True,
            "evaluation_implementation_sha256": hashlib.sha256(
                evaluation_code
            ).hexdigest(),
        }
        | runtime_metadata()
    )


def save_report(report: dict[str, object]) -> Path:
    """Evaluation reports never rewrite a deployed model or its active pointer."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = REPORTS_DIR / "personal" / "walkforward"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{report["tour"]}-{timestamp}.json'
    with path.open("x") as output:
        output.write(
            json.dumps(report | {"created_at": timestamp}, indent=2, sort_keys=True)
            + "\n"
        )
    return path


def main() -> None:
    """Run retrospective annual tests separately from production model deployment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tour", choices=("atp", "wta", "both"), default="both")
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--resamples", type=int, default=1000)
    args = parser.parse_args()
    years = tuple(range(args.start_year, args.end_year + 1))
    for tour in (("atp", "wta") if args.tour == "both" else (args.tour,)):
        save_report(evaluate_tour(tour, years, args.resamples))


if __name__ == "__main__":
    main()
