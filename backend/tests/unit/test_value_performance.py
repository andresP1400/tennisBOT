"""Paper returns use real archived prices; outcomes cannot retroactively invent bets."""

from datetime import datetime, timedelta, tzinfo
from pathlib import Path

import pytest

from api.market_engine import append_selection
from features.value_contracts import ValueSelection, ValueCandidate
from features.value_categories import assess_candidate, ValuePolicy
from features.personal_results import MatchOutcome
from pipeline.market_store import append_record
from pipeline.personal_tracking import Prediction
from features.market_contracts import MarketQuote
from pipeline.personal_settlement import append_outcomes
from pipeline.value_performance import performance_report
from test_value_categories import inputs


def stored_trial(
    path: Path,
) -> tuple[Prediction, MarketQuote, ValueCandidate, datetime]:
    prediction, quote, evidence, now = inputs(path)
    candidate = assess_candidate(
        prediction, "player1", quote, 0.67, 2, evidence, ValuePolicy(), now
    )
    for category in ("A", "B"):
        append_selection(
            ValueSelection(category=category, candidate=candidate, observed_at=now),
            path,
        )
    return prediction, quote, candidate, now


def settle(
    prediction: Prediction,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    winner: str | None = "One",
) -> None:
    observed = prediction.fixture.commence_time + timedelta(hours=3)

    class Clock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return observed + timedelta(minutes=1)

    monkeypatch.setattr("pipeline.personal_settlement.datetime", Clock)
    outcome = MatchOutcome(
        fixture_id=prediction.fixture.id,
        tour="atp",
        player1="One",
        player2="Two",
        winner=winner,
        status="completed" if winner else "void",
        scheduled_start=prediction.fixture.commence_time,
        observed_at=observed,
    )
    assert append_outcomes([outcome], path) == 1


def test_no_selections_do_not_create_zero_roi_or_a_profitable_result(
    tmp_path: Path,
) -> None:
    report = performance_report("A", tmp_path / "empty.sqlite3")
    assert report["summary"]["completed"] == 0
    assert report["summary"]["paper_roi"] is None
    assert report["summary"]["accuracy"] is None
    assert report["summary"]["closing_line"]["mean_fair_closing_ev"] is None
    assert not report["market_beating_advantage_established"]
    assert all(
        not milestone["resolved"] and milestone["metrics"] is None
        for milestone in report["milestones"]
    )


def test_each_category_scores_archived_prices_without_double_counting_repeated_decisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "events.sqlite3"
    prediction, quote, candidate, now = stored_trial(path)
    assert performance_report("A", path)["summary"]["pending"] == 1
    repriced = quote.model_copy(
        update={"odds1": 1.6, "observed_at": now - timedelta(seconds=5)}
    )
    repriced.id = append_record("market_quotes", repriced, quote.fixture.id, path)
    later = candidate.model_copy(update={"decimal_odds": 1.6, "quote_id": repriced.id})
    append_selection(
        ValueSelection(category="A", candidate=later, observed_at=now), path
    )
    settle(prediction, path, monkeypatch)
    for category in ("A", "B"):
        report = performance_report(category, path)["summary"]
        assert report["qualifying_unique_matches"] == report["completed"] == 1
        assert report["accuracy"] == 1
        assert report["paper_roi"] == pytest.approx(0.5)
        assert report["elo_brier"] == pytest.approx(0.3**2)
        assert report["closing_line"]["matches_with_actual_closing"] == 0
        assert report["roi_interval"] is None


def test_loss_and_void_remain_visible_and_do_not_become_missing_or_winning_picks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    losing = tmp_path / "loss.sqlite3"
    prediction, _, _, _ = stored_trial(losing)
    settle(prediction, losing, monkeypatch, "Two")
    summary = performance_report("A", losing)["summary"]
    assert summary["accuracy"] == 0 and summary["paper_roi"] == -1
    assert summary["maximum_drawdown_units"] == 1
    void = tmp_path / "void.sqlite3"
    prediction, _, _, _ = stored_trial(void)
    settle(prediction, void, monkeypatch, None)
    summary = performance_report("B", void)["summary"]
    assert summary["void"] == 1 and summary["completed"] == 0
    assert summary["paper_roi"] is None and summary["accuracy"] is None


def test_clv_requires_an_explicit_archived_same_book_closing_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "events.sqlite3"
    prediction, quote, candidate, now = stored_trial(path)
    close = quote.model_copy(
        update={
            "kind": "closing",
            "odds1": 1.4,
            "odds2": 3.3,
            "observed_at": now,
            "quoted_at": now - timedelta(seconds=1),
        }
    )
    append_record("market_quotes", close, quote.fixture.id, path)
    settle(prediction, path, monkeypatch)
    summary = performance_report("A", path)["summary"]
    no_vig = (1 / 1.4) / (1 / 1.4 + 1 / 3.3)
    assert summary["closing_line"]["matches_with_actual_closing"] == 1
    assert summary["closing_line"]["mean_fair_closing_ev"] == pytest.approx(
        1.5 * no_vig - 1
    )


def test_wrong_recorded_probability_cannot_supply_archived_roi(tmp_path: Path) -> None:
    path = tmp_path / "events.sqlite3"
    _, _, candidate, now = stored_trial(path)
    invented = candidate.model_copy(update={"probability": 0.99})
    with pytest.raises(ValueError, match="does not match"):
        append_selection(
            ValueSelection(category="A", candidate=invented, observed_at=now), path
        )
