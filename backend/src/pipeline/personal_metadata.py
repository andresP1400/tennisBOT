"""Reproducibility metadata kept beside each trained artifact."""

from __future__ import annotations

import hashlib
from importlib.metadata import version as package_version
from pathlib import Path

from pipeline.personal_state import FEATURES, SURFACES

MODEL_SOURCE_FILES = (
    "data",
    "state",
    "model",
    "train",
    "metadata",
    "protocol",
    "scores",
    "fitting",
)


def runtime_metadata() -> dict[str, object]:
    """Keep library versions, feature order, and implementation identity auditable."""
    directory = Path(__file__).parent
    sources = [directory / f"personal_{name}.py" for name in MODEL_SOURCE_FILES]
    return {
        "runtime_versions": {
            name: package_version(name)
            for name in ("numpy", "pandas", "scikit-learn", "joblib")
        },
        "implementation_sha256": hashlib.sha256(
            b"".join(path.read_bytes() for path in sources)
        ).hexdigest(),
        "feature_names": list(FEATURES)
        + [f"surface_{surface}" for surface in SURFACES]
        + [
            "best_of_5",
            "opponent_adjusted_form",
            "opponent_adjusted_serve",
            "opponent_adjusted_return",
        ],
    }
