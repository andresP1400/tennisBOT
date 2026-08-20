"""Model inventory route: list available trained models."""
from __future__ import annotations

from fastapi import APIRouter

from config import MODELS_DIR
from api.predict_core import MODEL_NAME_PATTERN

router = APIRouter()


@router.get("/api/models")
def list_models() -> dict:
    try:
        models = [
            p.name for p in MODELS_DIR.glob("*.pkl")
            if MODEL_NAME_PATTERN.match(p.name)
        ]
        return {"models": sorted(models)}
    except Exception:
        return {"models": []}
