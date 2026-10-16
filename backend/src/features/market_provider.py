"""Opt-in paid-API adapter; strict identity/timing, bounded calls, no scraper fallback."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from pathlib import Path
from typing import Protocol

import requests
from pydantic import BaseModel, Field

from config import settings
from features.market_contracts import MarketQuote, BettingSplit
from features.personal_schedule import Fixture
from pipeline.market_store import market_connect
from pipeline.personal_state import normalize_name


class MarketProvider(Protocol):
    def quotes(self, fixtures: list[Fixture]) -> list[MarketQuote]: ...


class PublicIntelligenceProvider(Protocol):
    def splits(self, fixtures: list[Fixture]) -> list[BettingSplit]: ...


class Outcome(BaseModel):
    name: str
    price: float


class Market(BaseModel):
    key: str
    last_update: datetime | None = None
    outcomes: list[Outcome] = Field(default_factory=list)


class Book(BaseModel):
    key: str
    last_update: datetime | None = None
    markets: list[Market] = Field(default_factory=list)


class Event(BaseModel):
    id: str
    home_team: str
    away_team: str
    commence_time: datetime
    bookmakers: list[Book] = Field(default_factory=list)


def reserve_request(sport: str, now: datetime, path: Path | None = None) -> bool:
    """Persist request admission before I/O so restarts cannot reset the daily cap."""
    database = market_connect(path)
    try:
        database.execute("BEGIN IMMEDIATE")
        rows = database.execute(
            "SELECT fixture_id, recorded_at FROM market_requests WHERE recorded_at >= ?",
            (now.date().isoformat(),),
        ).fetchall()
        allowed = len(rows) < max(
            0, settings.tennisbot_market_requests_per_day
        ) and not any(
            key == sport and (now - datetime.fromisoformat(stamp)).total_seconds() < 300
            for key, stamp in rows
        )
        if allowed:
            stamp = now.isoformat()
            identifier = hashlib.sha256(f"{sport}:{stamp}".encode()).hexdigest()
            database.execute(
                "INSERT INTO market_requests VALUES (?, ?, ?, ?)",
                (identifier, sport, stamp, "{}"),
            )
        database.commit()
        return allowed
    finally:
        database.close()


def matching_fixture(
    event: Event, fixtures: list[Fixture], tour: str
) -> Fixture | None:
    """No fuzzy matching or cross-day merging may assign an unrelated bookmaker line."""
    names = {normalize_name(event.home_team), normalize_name(event.away_team)}
    matches = [
        fixture
        for fixture in fixtures
        if fixture.tour == tour
        and {normalize_name(fixture.player1), normalize_name(fixture.player2)} == names
        and abs((fixture.commence_time - event.commence_time).total_seconds()) <= 300
    ]
    return matches[0] if len(matches) == 1 else None


def parse_market_event(
    event: Event, fixtures: list[Fixture], tour: str, observed: datetime
) -> list[MarketQuote]:
    """Require the actual book/market update time and align both outcomes by name."""
    fixture = matching_fixture(event, fixtures, tour)
    if fixture is None or fixture.commence_time <= observed:
        return []
    result = []
    for book in event.bookmakers:
        for market in book.markets:
            stamp = market.last_update or book.last_update
            if (
                market.key != "h2h"
                or stamp is None
                or stamp.tzinfo is None
                or stamp > observed
            ):
                continue
            prices = {normalize_name(item.name): item.price for item in market.outcomes}
            if len(market.outcomes) != 2 or len(prices) != 2:
                continue
            first, second = prices.get(normalize_name(fixture.player1)), prices.get(
                normalize_name(fixture.player2)
            )
            if first is None or second is None:
                continue
            result.append(
                make_quote(fixture, book, first, second, stamp, observed, event.id)
            )
    return result


class TheOddsMarketProvider:
    """No calls unless explicitly enabled, configured and under the stored budget."""

    def quotes(self, fixtures: list[Fixture]) -> list[MarketQuote]:
        if not settings.tennisbot_market_odds_enabled or not settings.odds_api_key:
            return []
        result = []
        sports = tuple(
            dict.fromkeys(
                item.strip()
                for item in settings.tennisbot_market_sports.split(",")
                if item.strip()
            )
        )
        if len(sports) > 4 or any(
            not re.fullmatch(r"tennis_(?:atp|wta)_[a-z0-9_]+", key) for key in sports
        ):
            raise ValueError("Configure at most four explicit ATP/WTA sport keys")
        tours = {fixture.tour for fixture in fixtures}
        for sport in sports:
            tour = "atp" if sport.startswith("tennis_atp_") else "wta"
            now = datetime.now(timezone.utc)
            if tour not in tours or not reserve_request(sport, now):
                continue
            response = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport}/odds/",
                params={
                    "apiKey": settings.odds_api_key,
                    "regions": "us",
                    "markets": "h2h",
                    "oddsFormat": "decimal",
                },
                timeout=15,
            )
            response.raise_for_status()
            observed = datetime.now(timezone.utc)
            for value in response.json():
                result.extend(
                    parse_market_event(
                        Event.model_validate(value), fixtures, tour, observed
                    )
                )
        return result


def make_quote(
    fixture: Fixture,
    book: Book,
    first: float,
    second: float,
    stamp: datetime,
    observed: datetime,
    provider_id: str,
) -> MarketQuote:
    """Unknown exchange commission is preserved as unknown, never zero-filled."""
    exchange = (
        book.key.startswith(("betfair", "matchbook", "smarkets"))
        or "exchange" in book.key
    )
    return MarketQuote(
        fixture=fixture,
        bookmaker=book.key,
        odds1=first,
        odds2=second,
        quoted_at=stamp,
        observed_at=observed,
        provenance="theoddsapi",
        provider_event_id=provider_id,
        commission=None if exchange else 0,
    )
