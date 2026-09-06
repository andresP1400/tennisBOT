"""Shared mutable state for the TennisBot API.

The FastAPI routes were split out of api_server.py into api/routes/*.py;
module-level globals (training status, dataset cache, inference-state cache)
now live here so every route module reads and writes the same objects
without import cycles.

Keep this module free of route decorators: it only holds state + loaders.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import HTTPException
from config import BASE_DIR

# Training progress (mutated by the background training subprocess reader).
training_status: dict[str, Any] = {
    "is_training": False,
    "current_task": "Idle",
    "progress": 0,
    "logs": [],
    "error": False,
    "success": False,
}

# Dataset cache (parquet) with mtime invalidation, per tour.
_global_dataset: pd.DataFrame | None = None
_global_dataset_mtime: float | None = None
_global_dataset_tour: str | None = None

# Serialized tracker state cache, per tour.
_inference_states: dict[str, Any] = {}


def load_dataset(tour: str) -> pd.DataFrame | None:
    """Load full parquet (both _A and _B) with mtime cache invalidation.

    IMPORTANT: do NOT filter to _A only — that would bias player lookups
    toward wins only (each player appears as p1 only when they win in _A).
    """
    global _global_dataset, _global_dataset_mtime, _global_dataset_tour

    if tour not in ("atp", "wta"):
        raise HTTPException(status_code=400, detail="Invalid tour")

    data_path = BASE_DIR / "data" / "processed" / f"{tour}_features.parquet"
    if not data_path.exists():
        return None

    current_mtime = data_path.stat().st_mtime
    if (
        _global_dataset is None
        or _global_dataset_mtime != current_mtime
        or _global_dataset_tour != tour
    ):
        _global_dataset = pd.read_parquet(data_path)
        _global_dataset_mtime = current_mtime
        _global_dataset_tour = tour

    return _global_dataset


def load_state(tour: str = "atp") -> Any | None:
    """Tracker state serialized by the feature builder (tour-aware cache)."""
    if tour not in _inference_states:
        from pipeline.inference import load_inference_state

        _inference_states[tour] = load_inference_state(tour)
    return _inference_states[tour]


def invalidate_caches() -> None:
    """Drop dataset and inference-state caches (after training/reload)."""
    global _global_dataset, _global_dataset_mtime, _global_dataset_tour
    _global_dataset = None
    _global_dataset_mtime = None
    _global_dataset_tour = None
    _inference_states.clear()
