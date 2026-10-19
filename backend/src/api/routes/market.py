"""Private market research endpoints; manual entry can never assert provider authority."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException

from api.market_engine import (
    build_market_card,
    MarketCard,
    record_manual_quote,
    record_manual_split,
)
from api.personal_engine import get_card
from features.market_contracts import QuoteInput, SplitInput
from pipeline.value_performance import performance_report

router = APIRouter()


@router.get("/api/personal/value-performance")
def value_performance(
    category: Literal["A", "B"] = "A", policy_version: str | None = None
) -> dict[str, object]:
    """Paper performance uses genuine archived selections/prices only, separately by category."""
    return performance_report(category, policy=policy_version)


@router.get("/api/personal/markets", response_model=MarketCard)
def markets(tour: Literal["atp", "wta"] = "atp") -> MarketCard:
    """Read local observations; visiting the dashboard never triggers paid API calls."""
    return build_market_card(get_card(tour))


@router.post("/api/personal/markets/manual-quote")
def manual_quote(value: QuoteInput) -> dict[str, str]:
    """Record an attributed manual observation, explicitly excluded from admission."""
    try:
        return {"id": record_manual_quote(value), "provenance": "manual"}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/api/personal/markets/manual-split")
def manual_split(value: SplitInput) -> dict[str, str]:
    """Optional percentages remain separate from independent model probabilities."""
    try:
        return {"id": record_manual_split(value), "provenance": "manual"}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
