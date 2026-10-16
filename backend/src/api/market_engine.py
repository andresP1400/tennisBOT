"""Independent forecasts meet archived prices; every qualifying category decision is saved."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from api.personal_engine import PredictionCard, load_bundle
from config import settings
from features.market_comparison import current_quotes, market_summary
from features.market_contracts import MarketQuote, BettingSplit, QuoteInput, SplitInput
from features.market_provider import TheOddsMarketProvider
from features.public_intelligence import summarize_public
from features.value_categories import ValuePolicy, ValueCandidate, assess_candidate
from features.value_contracts import ValueSelection
from logging_config import get_logger
from pipeline.market_store import append_record, fixture_records
from pipeline.market_validation import evidence_for
from pipeline.value_archive import append_selection as append_selection
from pipeline.personal_model import PersonalBundle
from pipeline.personal_tracking import Prediction
from pipeline.value_performance import score_trials
from pipeline.value_trials import load_trials

logger = get_logger(__name__)
SIDES: tuple[Literal["player1", "player2"], ...] = ("player1", "player2")
CATEGORIES: tuple[Literal["A", "B"], ...] = ("A", "B")
PROVIDER_STATUS: dict[str, str] = {}


class MarketCard(BaseModel):
    checked_at: datetime
    valid_until: datetime
    policy_version: str
    category_a: list[ValueCandidate] = Field(default_factory=list)
    category_b: list[ValueCandidate] = Field(default_factory=list)
    candidates: list[ValueCandidate] = Field(default_factory=list)
    markets: dict[str, dict[str, object]] = Field(default_factory=dict)
    public_intelligence: dict[str, dict[str, object]] = Field(default_factory=dict)
    message_a: str = "No qualifying opportunities."
    message_b: str = "No qualifying opportunities."
    provider_status: str = "Optional sportsbook API disabled or unconfigured"
    performance_a: dict[str, object] = Field(default_factory=dict)
    performance_b: dict[str, object] = Field(default_factory=dict)


def record_manual_quote(value: QuoteInput, path: Path | None = None) -> str:
    """Manual provenance is server-controlled; callers cannot impersonate a trusted feed."""
    quote = MarketQuote(
        **value.model_dump(),
        observed_at=datetime.now(timezone.utc),
        provenance="manual",
    )
    return append_record("market_quotes", quote, quote.fixture.id, path)


def record_manual_split(value: SplitInput, path: Path | None = None) -> str:
    """Retain source/scope/time without calling user-entered money a sharp signal."""
    split = BettingSplit(
        **value.model_dump(),
        observed_at=datetime.now(timezone.utc),
        provenance="manual",
    )
    return append_record("betting_splits", split, split.fixture.id, path)


def ingest_available_prices(card: PredictionCard) -> str:
    """A paid provider failure cannot replace core predictions or leak API keys in logs."""
    fixtures = [item.fixture for item in card.predictions]
    if not settings.tennisbot_market_odds_enabled or not settings.odds_api_key:
        return "Optional sportsbook API disabled or unconfigured"
    try:
        quotes = TheOddsMarketProvider().quotes(fixtures)
        for quote in quotes:
            append_record("market_quotes", quote, quote.fixture.id)
        return f"Recorded {len(quotes)} paired quotes; cached/budget-limited calls may return none"
    except Exception as error:
        logger.warning("Optional market refresh unavailable (%s)", type(error).__name__)
        return f"Optional provider unavailable ({type(error).__name__}); no replacement prices generated"


def build_market_card(card: PredictionCard, path: Path | None = None) -> MarketCard:
    """Re-evaluate quote ages at each request; never serve cached qualifying opportunities."""
    now = datetime.now(timezone.utc)
    policy = ValuePolicy(
        minimum_decimal_odds_a=settings.tennisbot_value_min_decimal_odds
    )
    result = MarketCard(
        checked_at=now,
        valid_until=now + timedelta(seconds=60),
        policy_version=policy.version(),
        provider_status=PROVIDER_STATUS.get(
            card.tour, "Optional sportsbook API disabled or unconfigured"
        ),
        performance_a=score_trials(load_trials("A", path)),
        performance_b=score_trials(load_trials("B", path)),
    )
    if card.model_version is None:
        return result
    bundle = load_bundle(card.tour)
    identifiers = [prediction.fixture.id for prediction in card.predictions]
    quotes_by_fixture = fixture_records("market_quotes", MarketQuote, identifiers, path)
    splits_by_fixture = fixture_records(
        "betting_splits", BettingSplit, identifiers, path
    )
    for prediction in card.predictions:
        fixture = prediction.fixture
        quotes = quotes_by_fixture[fixture.id]
        split = splits_by_fixture[fixture.id]
        current = current_quotes(quotes, fixture, now)
        summary = market_summary(quotes, fixture, now)
        result.markets[fixture.id] = summary
        result.public_intelligence[fixture.id] = summarize_public(
            split, quotes, fixture, now
        )
        result.candidates.extend(
            candidate_for_side(prediction, side, current, summary, bundle, policy, now)
            for side in SIDES
        )
    archive_categories(result, path)
    return result


def archive_categories(card: MarketCard, path: Path | None = None) -> None:
    """One best side per fixture/category/version/price decision; losing picks cannot disappear."""
    for category in CATEGORIES:
        field = "category_a" if category == "A" else "category_b"
        eligible = [
            candidate
            for candidate in card.candidates
            if (candidate.qualifies_a if category == "A" else candidate.qualifies_b)
        ]
        best: dict[str, ValueCandidate] = {}
        for candidate in eligible:
            previous = best.get(candidate.fixture.id)
            if previous is None or float(candidate.conservative_ev or 0) > float(
                previous.conservative_ev or 0
            ):
                best[candidate.fixture.id] = candidate
        for candidate in best.values():
            stamps = [candidate.fixture.commence_time]
            stamps.extend(
                stamp + timedelta(seconds=300)
                for stamp in (candidate.quote_time, candidate.quote_observed_at)
                if stamp is not None
            )
            card.valid_until = min(card.valid_until, *stamps)
            selection = ValueSelection(
                category=category, candidate=candidate, observed_at=card.checked_at
            )
            append_selection(selection, path)
        setattr(card, field, list(best.values()))
    if card.category_a:
        card.message_a = "Potential high-confidence value; not proven profitability"
    if card.category_b:
        card.message_b = "Potential market value; not proven profitability"


def candidate_for_side(
    prediction: Prediction,
    side: Literal["player1", "player2"],
    current: list[MarketQuote],
    summary: dict[str, object],
    bundle: PersonalBundle,
    policy: ValuePolicy,
    now: datetime,
) -> ValueCandidate:
    """Bind the selected best price and validation evidence to the correct player side."""
    best = summary["best1" if side == "player1" else "best2"]
    quote = next(
        (q for q in current if isinstance(best, dict) and q.id == best["quote_id"]),
        None,
    )
    market = summary["consensus1" if side == "player1" else "consensus2"]
    probability = prediction.prob1 if side == "player1" else prediction.prob2
    candidate = assess_candidate(
        prediction,
        side,
        quote,
        float(market) if isinstance(market, (float, int)) else None,
        len(current),
        evidence_for(bundle, probability),
        policy,
        now,
    )
    return candidate
