"""Compare refreshed history with preserved models on identical later holdout matches."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from api.personal_engine import load_version
from config import BASE_DIR, REPORTS_DIR
from pipeline.personal_data import load_history, build_dataset
from pipeline.personal_model import PersonalBundle, raw_probability, calibrate
from pipeline.personal_protocol import annual_partitions
from pipeline.personal_scores import arrays, metrics
from pipeline.personal_state import match_vector, normalize_name
from pipeline.personal_uncertainty import paired_date_bootstrap


def probabilities(bundle: PersonalBundle, frame: pd.DataFrame) -> NDArray[np.float64]:
    """Estimators and calibrators never refit on evaluation outcomes."""
    features, _ = arrays(frame)
    return calibrate(bundle.calibrator, raw_probability(bundle.estimator, features))


def frozen_state_probabilities(
    bundle: PersonalBundle, frame: pd.DataFrame
) -> NDArray[np.float64]:
    """Use old player state only after every possible source result was available."""
    boundary = pd.Timestamp(bundle.data_through) + pd.Timedelta(days=21)
    if frame.empty or (frame.date <= boundary).any():
        raise ValueError(
            "Frozen-state comparison must follow the entire baseline history embargo"
        )
    vectors = []
    for _, row in frame.iterrows():
        first = bundle.players[bundle.names[normalize_name(str(row.player1))]]
        second = bundle.players[bundle.names[normalize_name(str(row.player2))]]
        vectors.append(
            match_vector(
                first,
                second,
                str(row.surface),
                int(row.best_of),
                feature_schema=bundle.feature_schema,
                use_recent_form=bundle.use_recent_form,
            )
        )
    raw = raw_probability(bundle.estimator, np.asarray(vectors, dtype=float))
    return calibrate(bundle.calibrator, raw)


def paired_extension_report(
    baseline: PersonalBundle,
    candidate: PersonalBundle,
    testing: pd.DataFrame,
) -> dict[str, object]:
    """Compare the same outcomes and player population, never unrelated accuracy percentages."""
    extension = testing[
        testing.date > pd.Timestamp(baseline.data_through) + pd.Timedelta(days=21)
    ]
    _, labels = arrays(extension)
    updated = probabilities(candidate, extension)
    frozen = frozen_state_probabilities(baseline, extension)
    return {
        "start": str(extension.date.min().date()),
        "end": str(extension.date.max().date()),
        "refreshed_state": metrics(labels, updated),
        "preserved_stale_state": metrics(labels, frozen),
        "paired_uncertainty": paired_date_bootstrap(
            labels,
            updated,
            frozen,
            extension.date.to_numpy(dtype="datetime64[D]"),
            reference_name="frozen_ml",
        ),
    }


def compare_versions(
    tour: str, baseline_version: str, candidate_version: str
) -> dict[str, object]:
    """Prefix invariance guards earlier reports; extended outcomes remain out of sample."""
    baseline = load_version(baseline_version)
    candidate = load_version(candidate_version)
    if baseline.tour != tour or candidate.tour != tour:
        raise ValueError("Both model versions must match the requested tour")
    history, audit = load_history(tour)
    frame, _ = build_dataset(history, feature_schema=2)
    _, _, _, testing = annual_partitions(frame, 2026)
    shared = testing[testing.date <= pd.Timestamp(baseline.data_through)]
    updated = probabilities(candidate, shared)
    original = probabilities(baseline, shared)
    np.testing.assert_allclose(updated, original, rtol=0, atol=1e-12)
    _, labels = arrays(shared)
    previous = json.loads((BASE_DIR / f"docs/model-validation/{tour}.json").read_text())
    original_metrics = metrics(labels, original)
    if original_metrics != previous["evaluation"]["metrics"]:
        raise ValueError(
            "Original chronological evaluation no longer reproduces exactly"
        )
    return {
        "tour": tour,
        "baseline_version": baseline_version,
        "candidate_version": candidate_version,
        "audit": audit,
        "original_prefix_metrics": original_metrics,
        "original_prefix_probabilities_unchanged": True,
        "expanded_2026_metrics": metrics(
            arrays(testing)[1], probabilities(candidate, testing)
        ),
        "later_same_match_comparison": paired_extension_report(
            baseline, candidate, testing
        ),
        "protocol": "Fit through 2023; select 2024; calibrate 2025; frozen 2026 test; 21-day result embargo",
        "limitations": (
            "Partial sources, missing point counts, conservative identity exclusions; retrospective evaluation"
        ),
    }


def main() -> None:
    """Write a new private report; never select models or edit active pointers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tour", choices=["atp", "wta"], required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    report = compare_versions(args.tour, args.baseline, args.candidate)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = REPORTS_DIR / "personal" / f"result-update-{args.tour}-{stamp}.json"
    with path.open("x") as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
