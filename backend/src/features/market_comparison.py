"""As-of paired-book comparisons; opening and closing are never reconstructed."""

from __future__ import annotations

from datetime import datetime

from features.market_contracts import MarketQuote
from features.market_math import bookmaker_consensus
from features.personal_schedule import Fixture
from pipeline.personal_state import normalize_name


def same_fixture(first: Fixture, second: Fixture) -> bool:
    """Do not accept relabeled players, tours, or a different match with the same names."""
    return (
        first.id == second.id
        and first.tour == second.tour
        and normalize_name(first.player1) == normalize_name(second.player1)
        and normalize_name(first.player2) == normalize_name(second.player2)
        and abs((first.commence_time - second.commence_time).total_seconds()) <= 300
    )


def current_quotes(
    quotes: list[MarketQuote], fixture: Fixture, as_of: datetime
) -> list[MarketQuote]:
    """Choose the latest actual observation per independent book, then apply freshness."""
    latest: dict[str, MarketQuote] = {}
    for quote in quotes:
        if (
            not same_fixture(quote.fixture, fixture)
            or quote.kind == "closing"
            or not quote.observed_at <= as_of < fixture.commence_time
        ):
            continue
        previous = latest.get(quote.bookmaker)
        if previous is None or quote.observed_at > previous.observed_at:
            latest[quote.bookmaker] = quote
    return [
        quote
        for quote in latest.values()
        if quote.provenance == "theoddsapi"
        and quote.quoted_at is not None
        and 0 <= (as_of - quote.quoted_at).total_seconds() <= 300
        and 0 <= (as_of - quote.observed_at).total_seconds() <= 300
        and 0.95 <= 1 / quote.odds1 + 1 / quote.odds2 <= 1.20
    ]


def market_summary(
    quotes: list[MarketQuote], fixture: Fixture, as_of: datetime
) -> dict[str, object]:
    """Keep price-shopping, per-book no-vig probabilities and historical labels distinct."""
    current = current_quotes(quotes, fixture, as_of)
    pairs = {q.bookmaker: {"player1": q.odds1, "player2": q.odds2} for q in current}
    consensus = bookmaker_consensus(pairs) if pairs else None
    return {
        "independent_books": len(current),
        "consensus1": consensus.prob1 if consensus else None,
        "consensus2": consensus.prob2 if consensus else None,
        "best1": best_price(current, 1),
        "best2": best_price(current, 2),
        "bookmakers": [
            book_history(q.bookmaker, quotes, fixture, as_of) for q in current
        ],
        "closing_policy": "Only explicitly archived closing quotes; first/last observed are not official opens/closes",
    }


def best_price(quotes: list[MarketQuote], side: int) -> dict[str, object] | None:
    """Compare executable net prices, refusing exchanges with unknown commission."""
    eligible = [q for q in quotes if q.commission is not None]
    if not eligible:
        return None
    quote = max(
        eligible,
        key=lambda q: 1
        + ((q.odds1 if side == 1 else q.odds2) - 1) * (1 - float(q.commission or 0)),
    )
    odds = quote.odds1 if side == 1 else quote.odds2
    return {
        "quote_id": quote.id,
        "bookmaker": quote.bookmaker,
        "decimal_odds": odds,
        "commission": quote.commission,
        "quoted_at": quote.quoted_at,
        "observed_at": quote.observed_at,
    }


def book_history(
    book: str, quotes: list[MarketQuote], fixture: Fixture, as_of: datetime
) -> dict[str, object]:
    """Historical movement uses the same bookmaker and only information available as of the decision."""
    history = [
        q
        for q in quotes
        if q.bookmaker == book
        and same_fixture(q.fixture, fixture)
        and q.provenance == "theoddsapi"
        and q.observed_at <= as_of
    ]
    history.sort(key=lambda q: q.observed_at)
    opening = next((q for q in history if q.kind == "opening"), None)
    closing = next((q for q in reversed(history) if q.kind == "closing"), None)
    decision_prices = [quote for quote in history if quote.kind != "closing"]
    first, last = decision_prices[0], decision_prices[-1]
    return {
        "bookmaker": book,
        "opening": opening.model_dump(mode="json") if opening else None,
        "closing": closing.model_dump(mode="json") if closing else None,
        "first_observed": first.model_dump(mode="json"),
        "current": last.model_dump(mode="json"),
        "raw_implied1": 1 / last.odds1,
        "raw_implied2": 1 / last.odds2,
        "no_vig1": (1 / last.odds1) / (1 / last.odds1 + 1 / last.odds2),
        "odds_movement1": last.odds1 - first.odds1,
        "odds_movement2": last.odds2 - first.odds2,
    }
