"""Descriptive split/movement signals; no inference that money means informed betting."""

from __future__ import annotations

from datetime import datetime

from features.market_comparison import same_fixture
from features.market_contracts import BettingSplit, MarketQuote
from features.personal_schedule import Fixture


def summarize_public(
    splits: list[BettingSplit],
    quotes: list[MarketQuote],
    fixture: Fixture,
    as_of: datetime,
) -> dict[str, object]:
    """Respect publication/observation times and report missing public data explicitly."""
    eligible = [
        item
        for item in splits
        if same_fixture(item.fixture, fixture)
        and item.published_at <= item.observed_at <= as_of < fixture.commence_time
    ]
    if not eligible:
        return {
            "available": False,
            "message": "No timestamped betting splits available",
            "incremental_performance": None,
        }
    latest = max(eligible, key=lambda item: item.observed_at)
    movement = movement_summary(latest, quotes, fixture)
    return {
        "available": True,
        "observation": latest.model_dump(mode="json"),
        "money_minus_tickets1": (
            latest.money1 - latest.tickets1 if latest.money1 is not None else None
        ),
        "movement": movement,
        "incremental_performance": None,
        "warning": "Descriptive percentages do not identify sharp bettors or establish predictive value",
    }


def movement_summary(
    latest: BettingSplit, quotes: list[MarketQuote], fixture: Fixture
) -> list[dict[str, object]]:
    """Compare same-book movement only within the public observation window."""
    paired = [
        q
        for q in quotes
        if same_fixture(q.fixture, fixture)
        and q.observed_at <= latest.observed_at
        and q.provenance == "theoddsapi"
        and q.kind != "closing"
    ]
    movement: list[dict[str, object]] = []
    for book in sorted({q.bookmaker for q in paired}):
        history = sorted(
            (q for q in paired if q.bookmaker == book), key=lambda q: q.observed_at
        )
        if len(history) < 2:
            continue
        first, last = history[0], history[-1]
        before = (1 / first.odds1) / (1 / first.odds1 + 1 / first.odds2)
        after = (1 / last.odds1) / (1 / last.odds1 + 1 / last.odds2)
        reverse = (
            latest.tickets1 > 50
            and after < before
            or latest.tickets1 < 50
            and after > before
        )
        movement.append(
            {
                "bookmaker": book,
                "no_vig_change1": after - before,
                "reverse_to_ticket_majority": reverse,
            }
        )
    return movement
