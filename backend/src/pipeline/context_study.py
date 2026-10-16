"""Reproducible surface-context research; never replace a deployed model or report."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import joblib

from config import REPORTS_DIR
from pipeline.context_features import attach_context, CONTEXT_NAMES
from pipeline.context_fitting import fit_context, ContextFit
from pipeline.market_comparison_study import choose_by_selection
from pipeline.personal_data import load_history, build_dataset
from pipeline.personal_protocol import annual_partitions
from pipeline.personal_uncertainty import paired_date_bootstrap
from logging_config import get_logger

logger = get_logger(__name__)


def study_tour(tour: str, destination: Path) -> dict[str, object]:
    """Match both arms to the identical chronological partitions and canonical matches."""
    history, audit = load_history(tour)
    baseline, _ = build_dataset(history, feature_schema=2)
    frame = attach_context(history, baseline)
    parts = annual_partitions(frame, 2026)
    fits = {
        "baseline": fit_context(parts, False),
        "surface_context": fit_context(parts, True),
    }
    reports: dict[str, object] = {name: fit.report for name, fit in fits.items()}
    artifact_hashes = save_fits(tour, fits, destination)
    difference = paired_date_bootstrap(
        parts[-1].label.to_numpy(dtype="int64"),
        fits["surface_context"].probabilities,
        fits["baseline"].probabilities,
        parts[-1].date.to_numpy(dtype="datetime64[D]"),
        reference_name="frozen_ml",
    )
    result = {
        "source_audit": audit,
        "artifact_sha256": artifact_hashes,
        "candidates": reports,
        "selected_on_2024_only": choose_by_selection(reports),
        "paired_context_minus_baseline": difference,
        "paired_reference": "Fixed 20-feature research logistic",
        "newly_untouched_test": False,
        "automatically_deployed": False,
        "sportsbook_roi": None,
    }
    logger.info("Context ablation %s: %s", tour, reports)
    return result


def save_fits(
    tour: str, fits: dict[str, ContextFit], destination: Path
) -> dict[str, str]:
    """Private research artifacts have content hashes and never overwrite an earlier fit."""
    hashes: dict[str, str] = {}
    for name, fitted in fits.items():
        path = destination / f"{tour}-{name}.joblib"
        with path.open("xb") as output:
            joblib.dump(
                {
                    "estimator": fitted.estimator,
                    "calibrator": fitted.calibrator,
                    "feature_names_added": (
                        list(CONTEXT_NAMES) if name == "surface_context" else []
                    ),
                },
                output,
            )
        path.chmod(0o600)
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def main() -> None:
    """Save every fitted research arm privately, without altering active model pointers."""
    stamp = datetime.now(timezone.utc)
    destination = REPORTS_DIR / "personal" / f"context-study-{stamp:%Y%m%dT%H%M%S%fZ}"
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    sources = [
        Path(__file__).with_name(f"context_{name}.py")
        for name in ("features", "fitting", "study")
    ]
    report = {
        "created_at": stamp.isoformat(),
        "protocol": "docs/context-research-protocol.md",
        "implementation_sha256": hashlib.sha256(
            b"".join(path.read_bytes() for path in sources)
        ).hexdigest(),
        "new_features": list(CONTEXT_NAMES),
        "tours": {tour: study_tour(tour, destination) for tour in ("atp", "wta")},
    }
    path = destination / "report.json"
    with path.open("x") as output:
        json.dump(report, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")
    path.chmod(0o600)
    logger.info("Private context study saved to %s", destination)


if __name__ == "__main__":
    main()
