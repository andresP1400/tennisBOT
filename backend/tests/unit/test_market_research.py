"""No postmatch backfill, relayed bookmaker inflation, or invented open/closing prices."""

from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
import sqlite3

import pytest
from pydantic import ValidationError

from api.market_engine import ValueSelection, append_selection, record_manual_quote
from features.market_contracts import MarketQuote, QuoteInput, SplitInput, BettingSplit
from features.market_comparison import current_quotes, market_summary
from features.market_provider import (
    Event,
    parse_market_event,
    reserve_request,
    TheOddsMarketProvider,
)
from features.public_intelligence import summarize_public
from features.value_categories import assess_candidate, ValuePolicy
from pipeline.market_store import (
    market_connect,
    append_record,
    records,
    fixture_records,
)
from config import settings
from test_value_categories import inputs


def test_closing_snapshots_never_become_current_prices_and_invalid_pairs_cannot_supply_consensus(
    tmp_path: Path,
) -> None:
    prediction, quote, _, now = inputs(tmp_path / "events.sqlite3")
    close = quote.model_copy(
        update={"kind": "closing", "odds1": 1.1, "odds2": 10.0, "observed_at": now}
    )
    summary = market_summary([quote, close], prediction.fixture, now)
    assert summary["best1"]["decimal_odds"] == quote.odds1
    assert summary["bookmakers"][0]["current"]["kind"] == "current"
    assert summary["bookmakers"][0]["odds_movement1"] == 0
    broken = quote.model_copy(update={"odds1": 1.01, "odds2": 1.01, "observed_at": now})
    assert current_quotes([quote, broken], prediction.fixture, now) == []


def test_fixture_batch_reads_only_the_requested_identity_set(tmp_path: Path) -> None:
    path = tmp_path / "events.sqlite3"
    prediction, quote, _, _ = inputs(path)
    grouped = fixture_records(
        "market_quotes", MarketQuote, [prediction.fixture.id, "absent"], path
    )
    assert [item.id for item in grouped[prediction.fixture.id]] == [quote.id]
    assert grouped["absent"] == []
    assert fixture_records("market_quotes", MarketQuote, [], path) == {}


def test_invalid_sport_keys_cannot_trigger_a_paid_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "tennisbot_market_odds_enabled", True)
    monkeypatch.setattr(settings, "odds_api_key", "unit-placeholder")
    monkeypatch.setattr(settings, "tennisbot_market_sports", "tennis_atp_../../other")
    monkeypatch.setattr(
        "requests.get", lambda *args, **kwargs: pytest.fail("Unexpected request")
    )
    with pytest.raises(ValueError, match="explicit ATP/WTA"):
        TheOddsMarketProvider().quotes([])


def test_real_provider_parser_preserves_source_time_and_player_orientation(
    tmp_path: Path,
) -> None:
    prediction, quote, _, now = inputs(tmp_path / "events.sqlite3")
    event = Event(
        id="provider-id",
        home_team="Two",
        away_team="One",
        commence_time=prediction.fixture.commence_time,
        bookmakers=[
            {
                "key": "book",
                "last_update": now - timedelta(seconds=42),
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Two", "price": 3.1},
                            {"name": "One", "price": 1.5},
                        ],
                    }
                ],
            }
        ],
    )
    result = parse_market_event(event, [prediction.fixture], "atp", now)
    assert result[0].odds1 == 1.5 and result[0].odds2 == 3.1
    assert result[0].quoted_at == now - timedelta(seconds=42)
    assert not parse_market_event(
        event, [prediction.fixture.model_copy(update={"player1": "Other"})], "atp", now
    )
    event.bookmakers[0].last_update = None
    assert parse_market_event(event, [prediction.fixture], "atp", now) == []


def test_book_consensus_deduplicates_and_rejects_stale_last_observations(
    tmp_path: Path,
) -> None:
    prediction, quote, _, now = inputs(tmp_path / "events.sqlite3")
    another = quote.model_copy(
        update={"bookmaker": "book_b", "odds1": 1.6, "odds2": 2.5, "id": "b"}
    )
    summary = market_summary([quote, quote, another], prediction.fixture, now)
    assert summary["independent_books"] == 2
    assert summary["best1"]["decimal_odds"] == 1.6
    assert summary["consensus1"] == pytest.approx(
        ((1 / 1.5) / (1 / 1.5 + 1 / 3) + (1 / 1.6) / (1 / 1.6 + 1 / 2.5)) / 2
    )
    assert all(
        item["opening"] is None and item["closing"] is None
        for item in summary["bookmakers"]
    )
    newer = quote.model_copy(
        update={
            "observed_at": now - timedelta(seconds=10),
            "quoted_at": now - timedelta(seconds=600),
        }
    )
    assert current_quotes([quote, newer], prediction.fixture, now) == []
    assert not current_quotes(
        [quote], prediction.fixture, prediction.fixture.commence_time
    )


def test_manual_quotes_cannot_claim_provider_authority_and_records_are_immutable(
    tmp_path: Path,
) -> None:
    path = tmp_path / "events.sqlite3"
    prediction, quote, _, now = inputs(path)
    manual = QuoteInput.model_validate(
        quote.model_dump(
            exclude={"id", "observed_at", "provenance", "provider_event_id"}
        )
    )
    identifier = record_manual_quote(manual, path)
    saved = next(
        q
        for q in records("market_quotes", MarketQuote, path=path)
        if q.id == identifier
    )
    assert saved.provenance == "manual"
    assert current_quotes([saved], prediction.fixture, now) == []
    with pytest.raises(ValidationError):
        QuoteInput.model_validate({**manual.model_dump(), "provenance": "theoddsapi"})
    database = market_connect(path)
    for operation in (
        "UPDATE market_quotes SET fixture_id='changed'",
        "DELETE FROM market_quotes",
    ):
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            database.execute(operation)
    database.close()


def test_poststart_backdating_cannot_create_market_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, quote, _, now = inputs(tmp_path / "before.sqlite3")

    class Clock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return quote.fixture.commence_time + timedelta(hours=2)

    monkeypatch.setattr("pipeline.market_store.datetime", Clock)
    with pytest.raises(ValueError, match="after match start"):
        append_record(
            "market_quotes", quote, quote.fixture.id, tmp_path / "late.sqlite3"
        )


def test_all_qualifying_categories_are_idempotently_archived_and_require_real_records(
    tmp_path: Path,
) -> None:
    path = tmp_path / "events.sqlite3"
    prediction, quote, evidence, now = inputs(path)
    candidate = assess_candidate(
        prediction, "player1", quote, 0.67, 2, evidence, ValuePolicy(), now
    )
    for category in ("A", "B"):
        first = ValueSelection(category=category, candidate=candidate, observed_at=now)
        assert append_selection(first, path) == append_selection(
            first.model_copy(update={"observed_at": now + timedelta(microseconds=1)}),
            path,
        )
    assert len(records("value_selections", ValueSelection, path=path)) == 2
    with pytest.raises(ValueError, match="archived forecast"):
        append_selection(
            ValueSelection(
                category="A",
                candidate=candidate.model_copy(update={"prediction_id": "invented"}),
                observed_at=now,
            ),
            path,
        )


def test_paid_adapter_is_disabled_by_default_and_budget_survives_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "tennisbot_market_odds_enabled", False)
    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: pytest.fail("Unexpected paid provider request"),
    )
    assert TheOddsMarketProvider().quotes([]) == []
    monkeypatch.setattr(settings, "tennisbot_market_requests_per_day", 2)
    now = datetime.now(timezone.utc)
    assert reserve_request("tennis_atp_unit", now, tmp_path / "budget.sqlite3")
    assert not reserve_request(
        "tennis_atp_unit", now + timedelta(seconds=1), tmp_path / "budget.sqlite3"
    )
    assert reserve_request("tennis_wta_unit", now, tmp_path / "budget.sqlite3")
    assert not reserve_request("tennis_atp_other", now, tmp_path / "budget.sqlite3")


def test_splits_have_no_future_leakage_and_do_not_imply_sharp_money(
    tmp_path: Path,
) -> None:
    prediction, quote, _, now = inputs(tmp_path / "events.sqlite3")
    value = SplitInput(
        fixture=prediction.fixture,
        source="unit manual source",
        scope="unit book/tournament",
        published_at=now - timedelta(seconds=30),
        tickets1=70,
        tickets2=30,
        money1=40,
        money2=60,
    )
    split = BettingSplit(
        **value.model_dump(),
        observed_at=now - timedelta(seconds=20),
        provenance="manual"
    )
    summary = summarize_public([split], [quote], prediction.fixture, now)
    assert summary["money_minus_tickets1"] == -30
    assert summary["incremental_performance"] is None
    assert "do not identify sharp" in summary["warning"]
    assert not summarize_public(
        [split], [quote], prediction.fixture, now - timedelta(minutes=1)
    )["available"]
    with pytest.raises(ValidationError):
        BettingSplit.model_validate({**split.model_dump(), "tickets2": 31})
