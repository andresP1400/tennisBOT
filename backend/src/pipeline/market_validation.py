"""Out-of-sample calibration-bin evidence for unchanged deployed independent models."""

from __future__ import annotations

from datetime import timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from config import REPORTS_DIR
from features.market_contracts import ProbabilityEvidence
from pipeline.personal_model import PersonalBundle
from logging_config import get_logger

EVIDENCE_DIR = REPORTS_DIR / "personal" / "market-validation"
logger = get_logger(__name__)
METHOD = (
    "Approximate 95% tournament-date-block bootstrap of held-out calibration-bin win frequency; "
    "not an individual posterior"
)


def bin_evidence(
    frame: pd.DataFrame, probabilities: NDArray[np.float64], resamples: int = 1000
) -> list[dict[str, object]]:
    """One selected-winner observation per canonical match; never inflate counts with mirrors."""
    confidence = np.maximum(probabilities, 1 - probabilities)
    bin_index = np.minimum(4, np.floor((confidence - 0.5) * 10 + 1e-10).astype(int))
    correct = np.asarray((probabilities >= 0.5) == np.asarray(frame.label), dtype=float)
    result: list[dict[str, object]] = []
    for index in range(5):
        start = 0.5 + index / 10
        mask = bin_index == index
        selected = pd.DataFrame(
            {"date": np.asarray(frame.date)[mask], "correct": correct[mask]}
        )
        groups = selected.groupby("date").correct.agg(["sum", "count"])
        lower, upper = empirical_bounds(groups, resamples)
        result.append(
            {
                "minimum": start,
                "maximum": start + 0.1,
                "matches": len(selected),
                "date_blocks": len(groups),
                "accuracy": float(correct[mask].mean()) if mask.any() else None,
                "mean_probability": (
                    float(confidence[mask].mean()) if mask.any() else None
                ),
                "lower": lower,
                "upper": upper,
            }
        )
    return result


def empirical_bounds(
    groups: pd.DataFrame, resamples: int
) -> tuple[float | None, float | None]:
    """Small or sparse validation groups cannot manufacture a precise probability bound."""
    if len(groups) < 20 or int(groups["count"].sum()) < 100:
        return None, None
    generator = np.random.default_rng(42)
    choices = generator.integers(0, len(groups), size=(resamples, len(groups)))
    wins = groups["sum"].to_numpy(dtype=float)[choices].sum(axis=1)
    counts = groups["count"].to_numpy(dtype=float)[choices].sum(axis=1)
    low, high = np.quantile(wins / counts, [0.025, 0.975])
    return float(low), float(high)


def save_evidence(
    bundle: PersonalBundle, frame: pd.DataFrame, probabilities: NDArray[np.float64]
) -> Path:
    """Versioned local evidence is separate from immutable model bytes and reports."""
    audit = bundle.report["audit"]
    if not isinstance(audit, dict):
        raise ValueError("Missing source audit")
    payload = {
        "model_version": bundle.version,
        "model_source_digest": audit["source_digest"],
        "implementation_sha256": bundle.report["implementation_sha256"],
        "validation_end": frame.available_at.max()
        .to_pydatetime()
        .replace(tzinfo=timezone.utc)
        .isoformat(),
        "method": METHOD,
        "bins": bin_evidence(frame, probabilities),
        "scope": "Retrospective frozen-model held-out evidence, not an untouched new test or proof of profitability",
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / f"{bundle.version}.json"
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text() != encoded:
            raise ValueError(
                "Conflicting evidence is preserved; use a new model version"
            )
    else:
        with path.open("x") as output:
            output.write(encoded)
        path.chmod(0o600)
    return path


def evidence_for(
    bundle: PersonalBundle, probability: float
) -> ProbabilityEvidence | None:
    """Unavailable or corrupt local evidence cannot admit a value opportunity."""
    try:
        return _read_evidence(bundle, probability)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        logger.warning(
            "Market validation evidence unavailable (%s)", type(error).__name__
        )
        return None


def _read_evidence(
    bundle: PersonalBundle, probability: float
) -> ProbabilityEvidence | None:
    """Only matching locally generated, sufficiently populated validation bins may qualify."""
    path = EVIDENCE_DIR / f"{bundle.version}.json"
    if not 0 < probability < 1 or not path.exists():
        return None
    content = path.read_bytes()
    value = json.loads(content)
    audit = bundle.report["audit"]
    if not isinstance(audit, dict):
        return None
    if (
        value["model_version"] != bundle.version
        or value["implementation_sha256"] != bundle.report["implementation_sha256"]
        or value["model_source_digest"] != audit["source_digest"]
    ):
        return None
    confidence = max(probability, 1 - probability)
    index = min(4, max(0, int(np.floor((confidence - 0.5) * 10 + 1e-10))))
    band = value["bins"][index] if len(value["bins"]) == 5 else None
    if band is None or band["lower"] is None or band["upper"] is None:
        return None
    lower, upper = (
        (band["lower"], band["upper"])
        if probability >= 0.5
        else (1 - band["upper"], 1 - band["lower"])
    )
    return ProbabilityEvidence(
        model_version=bundle.version,
        estimated_probability=probability,
        lower_probability=min(probability, lower),
        upper_probability=max(probability, upper),
        matches=band["matches"],
        date_blocks=band["date_blocks"],
        method=value["method"],
        validation_end=value["validation_end"],
        source_digest=hashlib.sha256(content).hexdigest(),
    )
