"""Rolling public schedules retain provider identity and real observation times."""

from datetime import datetime, timedelta, timezone

import pytest

from features import personal_schedule as schedule


def scoreboard_event(
    identifier: str, name: str, matches: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "id": identifier,
        "name": name,
        "groupings": [
            {"grouping": {"slug": "womens-singles"}, "competitions": matches}
        ],
    }


def scheduled_match(
    identifier: str,
    start: datetime,
    names: tuple[str, str] = ("Player One", "Player Two"),
) -> dict[str, object]:
    return {
        "id": identifier,
        "date": start.isoformat(),
        "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED"}},
        "competitors": [
            {"athlete": {"displayName": name}, "homeAway": side}
            for name, side in zip(names, ("home", "away"))
        ],
    }


def test_rolling_schedule_includes_next_tournament_without_fabricating_draws(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 10, 16, 5, tzinfo=timezone.utc)
    matches = [
        scheduled_match("future", now + timedelta(days=3)),
        scheduled_match("placeholder", now + timedelta(days=3), ("TBD", "Two")),
        scheduled_match("outside", now + timedelta(days=7, seconds=1)),
        scheduled_match("started", now),
    ]
    board = schedule.Scoreboard.model_validate(
        {"events": [scoreboard_event("963-2026", "Ningbo Open", matches)]}
    )
    observed = now - timedelta(seconds=10)
    requests: list[tuple[str, str]] = []

    def fetch(tour: str, dates: str) -> tuple[schedule.Scoreboard, datetime]:
        requests.append((tour, dates))
        return board, observed

    monkeypatch.setattr(schedule, "fetch_scoreboard", fetch)
    fixtures = schedule.fetch_fixtures("wta", now)
    assert requests == [("wta", "20261016-20261023")]
    assert len(fixtures) == 1
    assert fixtures[0].id == "espn:wta:future"
    assert fixtures[0].surface == "Hard"
    assert fixtures[0].tournament_level == "WTA 500"
    assert fixtures[0].fetched_at == observed


def test_range_uses_utc_dates_across_year_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 12, 31, 23, tzinfo=timezone(timedelta(hours=-5)))
    requests: list[tuple[str, str]] = []

    def fetch(tour: str, dates: str) -> tuple[schedule.Scoreboard, datetime]:
        requests.append((tour, dates))
        return schedule.Scoreboard(), now.astimezone(timezone.utc)

    monkeypatch.setattr(schedule, "fetch_scoreboard", fetch)
    assert schedule.fetch_fixtures("atp", now) == []
    assert requests == [("atp", "20270101-20270108")]


def test_cached_schedule_preserves_original_quote_observation_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 10, 16, 5, tzinfo=timezone.utc)
    match = scheduled_match("priced", now + timedelta(days=1))
    match["odds"] = [
        {
            "provider": {"name": "Observed provider"},
            "homeTeamOdds": {"moneyLine": -200},
            "awayTeamOdds": {"moneyLine": 170},
        }
    ]
    board = schedule.Scoreboard.model_validate(
        {"events": [scoreboard_event("963-2026", "Ningbo Open", [match])]}
    )
    observed = now - timedelta(minutes=2)
    monkeypatch.setattr(schedule, "fetch_scoreboard", lambda *_: (board, observed))
    fixture = schedule.fetch_fixtures("wta", now)[0]
    assert fixture.odds_observed_at == fixture.fetched_at == observed
    assert fixture.odds1 == pytest.approx(1.5)
    assert fixture.odds2 == pytest.approx(2.7)
