"""Public singles fixtures, independent of sportsbook and research credentials."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

import requests
from pydantic import BaseModel, Field


class Athlete(BaseModel):
    displayName: str = ""


class Competitor(BaseModel):
    athlete: Athlete = Field(default_factory=Athlete)
    homeAway: str = ""


class MoneyLine(BaseModel):
    moneyLine: float | None = None


class OddsProvider(BaseModel):
    name: str = ""


class MarketOdds(BaseModel):
    provider: OddsProvider = Field(default_factory=OddsProvider)
    homeTeamOdds: MoneyLine = Field(default_factory=MoneyLine)
    awayTeamOdds: MoneyLine = Field(default_factory=MoneyLine)


class StatusType(BaseModel):
    state: str = ""
    name: str = ""


class Status(BaseModel):
    type: StatusType = Field(default_factory=StatusType)


class Competition(BaseModel):
    id: str
    date: datetime
    status: Status = Field(default_factory=Status)
    competitors: list[Competitor] = Field(default_factory=list)
    odds: list[MarketOdds] = Field(default_factory=list)


class GroupingName(BaseModel):
    slug: str = ""


class Grouping(BaseModel):
    grouping: GroupingName = Field(default_factory=GroupingName)
    competitions: list[Competition] = Field(default_factory=list)


class Tournament(BaseModel):
    id: str
    name: str
    groupings: list[Grouping] = Field(default_factory=list)


class Scoreboard(BaseModel):
    events: list[Tournament] = Field(default_factory=list)


class Fixture(BaseModel):
    id: str
    tour: str
    player1: str
    player2: str
    tournament: str
    commence_time: datetime
    source: str
    fetched_at: datetime
    surface: str | None = None
    surface_source: str | None = None
    odds1: float | None = None
    odds2: float | None = None
    odds_source: str | None = None
    odds_observed_at: datetime | None = None


# Only confirmed tournament identities are used; unknown surfaces remain unavailable.
TOURNAMENT_SURFACES = {("atp", "315"): "Hard", ("wta", "381"): "Hard"}


def decimal_odds(american: float | None) -> float | None:
    """Convert a quoted real market price; missing prices remain missing."""
    if american is None or not math.isfinite(american) or abs(american) < 100:
        return None
    return 1 + (american / 100 if american > 0 else 100 / abs(american))


def attach_available_odds(fixture: Fixture, match: Competition) -> None:
    """Keep any provider-supplied prices in player order with their observation time."""
    for market in match.odds:
        sides = {
            "home": market.homeTeamOdds.moneyLine,
            "away": market.awayTeamOdds.moneyLine,
        }
        prices = [
            decimal_odds(sides.get(player.homeAway)) for player in match.competitors
        ]
        if len(prices) == 2 and all(price is not None for price in prices):
            fixture.odds1, fixture.odds2 = prices
            fixture.odds_source = market.provider.name or "ESPN scoreboard market"
            fixture.odds_observed_at = fixture.fetched_at
            return


def parse_fixtures(scoreboard: Scoreboard, tour: str, now: datetime) -> list[Fixture]:
    """Exclude finished/live matches, doubles, unresolved draws, and past starts."""
    slug = "mens-singles" if tour == "atp" else "womens-singles"
    fixtures: dict[str, Fixture] = {}
    for event in scoreboard.events:
        for group in event.groupings:
            if group.grouping.slug != slug:
                continue
            for match in group.competitions:
                names = [item.athlete.displayName.strip() for item in match.competitors]
                if (
                    match.status.type.state != "pre"
                    or match.status.type.name not in ("STATUS_SCHEDULED", "STATUS_TBD")
                    or not now < match.date <= now + timedelta(days=7)
                    or len(names) != 2
                    or any(
                        not name or name.casefold() in {"tbd", "bye", "qualifier"}
                        for name in names
                    )
                ):
                    continue
                key = (tour, event.id.split("-")[0])
                surface = TOURNAMENT_SURFACES.get(key)
                fixtures[match.id] = Fixture(
                    id=f"espn:{tour}:{match.id}",
                    tour=tour,
                    player1=names[0],
                    player2=names[1],
                    tournament=event.name,
                    commence_time=match.date,
                    source="ESPN public scoreboard",
                    fetched_at=now,
                    surface=surface,
                    surface_source="Confirmed tournament identity" if surface else None,
                )
                attach_available_odds(fixtures[match.id], match)
    return sorted(fixtures.values(), key=lambda fixture: fixture.commence_time)


def fetch_fixtures(tour: str, now: datetime | None = None) -> list[Fixture]:
    """Fetch small public schedule responses; do not scrape or bypass restrictions."""
    if tour not in ("atp", "wta"):
        raise ValueError("Expected ATP or WTA")
    now = now or datetime.now(timezone.utc)
    url = f"https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard"
    response = requests.get(url, params={"dates": now.strftime("%Y%m%d")}, timeout=15)
    response.raise_for_status()
    return parse_fixtures(Scoreboard.model_validate_json(response.content), tour, now)
