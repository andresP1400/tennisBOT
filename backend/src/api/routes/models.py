"""Model inventory route: list available trained models."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from logging_config import get_logger
from config import MODELS_DIR
from api.predict_core import MODEL_NAME_PATTERN

log = get_logger(__name__)

router = APIRouter()


@router.get("/api/models")
def list_models() -> dict[str, Any]:
    try:
        models = [
            p.name for p in MODELS_DIR.glob("*.pkl") if MODEL_NAME_PATTERN.match(p.name)
        ]
        return {"models": sorted(models)}
    except OSError as e:
        log.warning("Could not list model dir %s: %s", MODELS_DIR, e)
        return {"models": []}
