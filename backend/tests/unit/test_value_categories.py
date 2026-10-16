"""Selection rules must fail closed on price, identity, uncertainty and timing defects."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from features.market_contracts import MarketQuote, ProbabilityEvidence
from features.personal_schedule import Fixture
from features.value_categories import ValuePolicy, assess_candidate
from pipeline.personal_tracking import Prediction, record_prediction
from pipeline.market_store import append_record


def inputs(
    path: Path, probability: float = 0.82, odds: float = 1.5, opposite: float = 3.0
) -> tuple[Prediction, MarketQuote, ProbabilityEvidence, datetime]:
    now = datetime.now(timezone.utc)
    fixture = Fixture(
        id="unit-value",
        tour="atp",
        player1="One",
        player2="Two",
        tournament="Unit event",
        commence_time=now + timedelta(days=1),
        fetched_at=now,
        source="unit-test",
        surface="Hard",
    )
    prediction = unit_prediction(fixture, probability, now, path)
    quote = MarketQuote(
        fixture=fixture,
        bookmaker="book_a",
        odds1=odds,
        odds2=opposite,
        quoted_at=now - timedelta(seconds=30),
        observed_at=now - timedelta(seconds=20),
        provenance="theoddsapi",
    )
    quote.id = append_record("market_quotes", quote, fixture.id, path)
    evidence = unit_evidence(probability, now)
    return prediction, quote, evidence, now


def unit_prediction(
    fixture: Fixture, probability: float, now: datetime, path: Path
) -> Prediction:
    return record_prediction(
        Prediction(
            fixture=fixture,
            model_version="unit-model",
            model_family="unit",
            prob1=probability,
            prob2=1 - probability,
            elo_prob1=0.7,
            winner="One",
            predicted_at=now - timedelta(seconds=1),
            data_through=str((now - timedelta(days=1)).date()),
            history_age_days=1,
        ),
        path,
    )


def unit_evidence(probability: float, now: datetime) -> ProbabilityEvidence:
    return ProbabilityEvidence(
        model_version="unit-model",
        estimated_probability=probability,
        lower_probability=max(0, probability - 0.04),
        upper_probability=min(1, probability + 0.04),
        matches=200,
        date_blocks=30,
        method="unit-test evidence only",
        validation_end=now - timedelta(days=3),
        source_digest="a" * 64,
    )


def test_categories_separate_probability_price_and_economic_objectives(
    tmp_path: Path,
) -> None:
    prediction, quote, evidence, now = inputs(tmp_path / "a.sqlite3")
    candidate = assess_candidate(
        prediction, "player1", quote, 0.67, 2, evidence, ValuePolicy(), now
    )
    assert candidate.qualifies_a and candidate.qualifies_b
    assert candidate.estimated_ev == pytest.approx(0.82 * 1.5 - 1)
    assert candidate.conservative_ev == pytest.approx(0.78 * 1.5 - 1)
    low, price, bounds, clock = inputs(tmp_path / "b.sqlite3", 0.75, 1.6, 2.5)
    value = assess_candidate(
        low, "player1", price, 0.62, 2, bounds, ValuePolicy(), clock
    )
    assert value.qualifies_b and not value.qualifies_a
    assert "below 80%" in " ".join(value.category_a_reasons)


def test_short_odds_can_pass_but_never_the_initial_high_confidence_price_filter(
    tmp_path: Path,
) -> None:
    prediction, quote, evidence, now = inputs(
        tmp_path / "events.sqlite3", 0.85, 1.3, 4.3
    )
    candidate = assess_candidate(
        prediction, "player1", quote, 0.77, 2, evidence, ValuePolicy(), now
    )
    assert candidate.qualifies_b and not candidate.qualifies_a
    assert ValuePolicy(minimum_decimal_odds_a=1.5).version() != ValuePolicy().version()


@pytest.mark.parametrize(
    "defect",
    [
        "stale_history",
        "stale_quote",
        "future_quote",
        "manual",
        "missing_uncertainty",
        "wrong_model",
        "wrong_players",
        "one_book",
        "huge_edge",
        "post_start",
        "unknown_fee",
        "nonfinite_market",
    ],
)
def test_material_defects_never_become_a_qualifying_pick(
    tmp_path: Path, defect: str
) -> None:
    prediction, quote, evidence, now = inputs(tmp_path / "events.sqlite3")
    books, market = 2, 0.67
    if defect == "stale_history":
        prediction.data_through = str((now - timedelta(days=100)).date())
    if defect == "stale_quote":
        quote.quoted_at = now - timedelta(seconds=301)
    if defect == "future_quote":
        quote.quoted_at = now + timedelta(seconds=1)
    if defect == "manual":
        quote.provenance = "manual"
    if defect == "missing_uncertainty":
        evidence = None
    if defect == "wrong_model":
        evidence.model_version = "different"
    if defect == "wrong_players":
        quote.fixture = quote.fixture.model_copy(update={"player1": "Unrelated"})
    if defect == "one_book":
        books = 1
    if defect == "huge_edge":
        market = 0.4
    if defect == "post_start":
        now = prediction.fixture.commence_time
    if defect == "unknown_fee":
        quote.commission = None
    if defect == "nonfinite_market":
        market = float("nan")
    candidate = assess_candidate(
        prediction, "player1", quote, market, books, evidence, ValuePolicy(), now
    )
    assert not candidate.qualifies_a and not candidate.qualifies_b
    assert candidate.reasons


def test_positive_point_ev_does_not_override_negative_conservative_ev(
    tmp_path: Path,
) -> None:
    prediction, quote, evidence, now = inputs(
        tmp_path / "events.sqlite3", 0.8, 1.4, 3.2
    )
    evidence.lower_probability = 0.65
    result = assess_candidate(
        prediction, "player1", quote, 0.70, 2, evidence, ValuePolicy(), now
    )
    assert result.estimated_ev > 0 and result.conservative_ev < 0
    assert not result.qualifies_b
