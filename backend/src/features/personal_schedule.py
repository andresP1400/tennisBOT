"""Public singles fixtures, independent of sportsbook and research credentials."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from pydantic import BaseModel, Field

from features.personal_surfaces import verified_surface


class Athlete(BaseModel):
    displayName: str = ""


class Competitor(BaseModel):
    athlete: Athlete = Field(default_factory=Athlete)
    homeAway: str = ""
    winner: bool = False


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
    completed: bool = False


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


class TournamentVenue(BaseModel):
    displayName: str = ""


class Tournament(BaseModel):
    id: str
    name: str
    venue: TournamentVenue = Field(default_factory=TournamentVenue)
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
    tournament_level: str | None = None
    odds1: float | None = None
    odds2: float | None = None
    odds_source: str | None = None
    odds_observed_at: datetime | None = None


_scoreboards: dict[tuple[str, str], tuple[float, Scoreboard, datetime]] = {}
_scoreboard_lock = threading.Lock()


def fetch_scoreboard(tour: str, day: str) -> tuple[Scoreboard, datetime]:
    """Share short-lived schedule/result responses without falsifying fetch times."""
    if tour not in ("atp", "wta"):
        raise ValueError("Expected ATP or WTA")
    with _scoreboard_lock:
        cached = _scoreboards.get((tour, day))
        if cached and time.monotonic() - cached[0] < 240:
            return cached[1], cached[2]
    url = f"https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard"
    response = requests.get(url, params={"dates": day}, timeout=15)
    response.raise_for_status()
    board = Scoreboard.model_validate_json(response.content)
    observed = datetime.now(timezone.utc)
    with _scoreboard_lock:
        _scoreboards[(tour, day)] = (time.monotonic(), board, observed)
        if len(_scoreboards) > 64:
            oldest = min(_scoreboards, key=lambda key: _scoreboards[key][0])
            del _scoreboards[oldest]
        return board, observed


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
                review = verified_surface(
                    tour, event.id, event.name, match.date, event.venue.displayName
                )
                fixtures[match.id] = Fixture(
                    id=f"espn:{tour}:{match.id}",
                    tour=tour,
                    player1=names[0],
                    player2=names[1],
                    tournament=event.name,
                    commence_time=match.date,
                    source="ESPN public scoreboard",
                    fetched_at=now,
                    surface=review.surface if review else None,
                    surface_source=review.source if review else None,
                    tournament_level=review.level if review else None,
                )
                attach_available_odds(fixtures[match.id], match)
    return sorted(fixtures.values(), key=lambda fixture: fixture.commence_time)


def fetch_fixtures(tour: str, now: datetime | None = None) -> list[Fixture]:
    """Range responses omit events; bounded cached day indexes cover the actual horizon."""
    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc)
    days = [(now + timedelta(days=index)).strftime("%Y%m%d") for index in range(8)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        snapshots = list(pool.map(lambda day: fetch_scoreboard(tour, day), days))
    return merge_schedule_snapshots(snapshots, tour, now)


def merge_schedule_snapshots(
    snapshots: list[tuple[Scoreboard, datetime]],
    tour: str,
    now: datetime,
) -> list[Fixture]:
    """A newer live/cancelled status removes older pre-match rows for the same ID."""
    fixtures: dict[str, Fixture] = {}
    slug = "mens-singles" if tour == "atp" else "womens-singles"
    for board, observed in sorted(snapshots, key=lambda item: item[1]):
        for event in board.events:
            for group in event.groupings:
                if group.grouping.slug == slug:
                    for match in group.competitions:
                        fixtures.pop(f"espn:{tour}:{match.id}", None)
        for fixture in parse_fixtures(board, tour, now):
            fixture.fetched_at = observed
            if fixture.odds_observed_at:
                fixture.odds_observed_at = observed
            fixtures[fixture.id] = fixture
    return sorted(fixtures.values(), key=lambda fixture: fixture.commence_time)
