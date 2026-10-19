"""Preserve complete per-bookmaker quote pairs before consensus aggregation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from features.market_math import valid_price
from features.odds_common import MatchOdds, _is_live, _normalize_player


class Outcome(BaseModel):
    name: str
    price: float


class Market(BaseModel):
    key: str
    outcomes: list[Outcome] = Field(default_factory=list)


class Bookmaker(BaseModel):
    key: str
    markets: list[Market] = Field(default_factory=list)


class Event(BaseModel):
    home_team: str
    away_team: str
    commence_time: str
    bookmakers: list[Bookmaker] = Field(default_factory=list)


def parse_event(value: object, sport: str) -> list[MatchOdds]:
    """Never construct a fictitious bookmaker by combining cross-book best prices."""
    event = Event.model_validate(value)
    quotes: list[MatchOdds] = []
    home, away = _normalize_player(event.home_team), _normalize_player(event.away_team)
    if not home or not away or home == away:
        return quotes
    for book in event.bookmakers:
        for market in book.markets:
            if market.key != "h2h":
                continue
            prices = {
                _normalize_player(item.name): item.price for item in market.outcomes
            }
            first, second = prices.get(home, 0), prices.get(away, 0)
            if not book.key or not valid_price(first) or not valid_price(second):
                continue
            quotes.append(
                MatchOdds(
                    source="theoddsapi",
                    player1=event.home_team,
                    player2=event.away_team,
                    tournament=sport.replace("tennis_atp_", "")
                    .replace("tennis_wta_", "")
                    .replace("_", " ")
                    .title(),
                    commence_time=event.commence_time,
                    is_live=_is_live(event.commence_time),
                    odds_p1=first,
                    odds_p2=second,
                    bookmaker=book.key,
                    tour="atp" if "tennis_atp_" in sport else "wta",
                )
            )
    return quotes
