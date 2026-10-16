"""Separate high-confidence selection from uncertainty-adjusted potential market value."""

from __future__ import annotations

from datetime import datetime, date
import math
from typing import Literal


from features.market_comparison import same_fixture
from features.market_contracts import MarketQuote, ProbabilityEvidence
from features.value_contracts import (
    ValuePolicy as ValuePolicy,
    ValueCandidate as ValueCandidate,
    candidate_payload,
)
from pipeline.personal_tracking import Prediction


def common_reasons(
    prediction: Prediction,
    quote: MarketQuote | None,
    evidence: ProbabilityEvidence | None,
    probability: float,
    market_probability: float | None,
    books: int,
    policy: ValuePolicy,
    now: datetime,
) -> list[str]:
    """Price or point-EV alone never supplies missing calibration or freshness evidence."""
    reasons = []
    if not prediction.tracking_id or quote is not None and not quote.id:
        reasons.append("Forecast and price must already have durable record identities")
    age = (now.date() - date.fromisoformat(prediction.data_through)).days
    if not 0 <= age <= policy.maximum_history_age_days:
        reasons.append("Historical player inputs are stale")
    if now >= prediction.fixture.commence_time:
        reasons.append("Match has started")
    if prediction.fixture.tournament_level == "WTA 125":
        reasons.append("This tournament level has no adequate model validation")
    if (
        books < 2
        or market_probability is None
        or not math.isfinite(market_probability)
        or not 0 < market_probability < 1
    ):
        reasons.append("Two independent current paired bookmakers are required")
    if (
        market_probability is not None
        and abs(probability - market_probability)
        > policy.maximum_probability_disagreement
    ):
        reasons.append("Unusually large model/market disagreement requires review")
    reasons.extend(quote_reasons(prediction, quote, policy, now))
    reasons.extend(evidence_reasons(prediction, evidence, probability, now))
    return reasons


def quote_reasons(
    prediction: Prediction,
    quote: MarketQuote | None,
    policy: ValuePolicy,
    now: datetime,
) -> list[str]:
    """Unknown provider timing, mismatches and exchange fees are material concerns."""
    if quote is None:
        return ["No current executable paired sportsbook price"]
    reasons = []
    if not same_fixture(prediction.fixture, quote.fixture):
        reasons.append("Price fixture/player identity does not match the forecast")
    if quote.provenance != "theoddsapi" or quote.kind == "closing":
        reasons.append(
            "Manual, observation-only or closing prices are not admission evidence"
        )
    if (
        quote.quoted_at is None
        or not 0
        <= (now - quote.quoted_at).total_seconds()
        <= policy.maximum_quote_age_seconds
    ):
        reasons.append("Source quote timestamp is missing, stale or future")
    if (
        not 0
        <= (now - quote.observed_at).total_seconds()
        <= policy.maximum_quote_age_seconds
    ):
        reasons.append("Local price observation is stale or future")
    if quote.commission is None:
        reasons.append("Exchange commission is unknown")
    if not 0.95 <= 1 / quote.odds1 + 1 / quote.odds2 <= 1.20:
        reasons.append("Implausible paired market margin requires review")
    return reasons


def evidence_reasons(
    prediction: Prediction,
    evidence: ProbabilityEvidence | None,
    probability: float,
    now: datetime,
) -> list[str]:
    """Uncertainty must refer to this frozen model and precede the decision."""
    if evidence is None:
        return [
            "Reviewed model-specific out-of-sample uncertainty evidence is unavailable"
        ]
    if (
        evidence.model_version != prediction.model_version
        or abs(evidence.estimated_probability - probability) > 1e-9
    ):
        return ["Uncertainty evidence does not match this model/probability"]
    if not evidence.validation_end < prediction.predicted_at <= now:
        return ["Validation evidence does not precede the pre-match forecast"]
    return []


def assess_candidate(
    prediction: Prediction,
    side: Literal["player1", "player2"],
    quote: MarketQuote | None,
    market_probability: float | None,
    books: int,
    evidence: ProbabilityEvidence | None,
    policy: ValuePolicy,
    now: datetime,
) -> ValueCandidate:
    """Use net conservative EV for admission; preserve the requested raw EV formula separately."""
    probability = prediction.prob1 if side == "player1" else prediction.prob2
    odds = (quote.odds1 if side == "player1" else quote.odds2) if quote else None
    net_odds = net_price(quote, odds)
    lower = evidence.lower_probability if evidence else None
    conservative = lower * net_odds - 1 if lower is not None and net_odds else None
    reasons = common_reasons(
        prediction, quote, evidence, probability, market_probability, books, policy, now
    )
    economic, category_a = economic_reasons(
        probability, odds, lower, conservative, market_probability, policy
    )
    reasons.extend(economic)
    return candidate_payload(
        prediction,
        side,
        quote,
        evidence,
        policy,
        now,
        probability,
        odds,
        net_odds,
        conservative,
        market_probability,
        reasons,
        category_a,
    )


def economic_reasons(
    probability: float,
    odds: float | None,
    lower: float | None,
    conservative: float | None,
    market_probability: float | None,
    policy: ValuePolicy,
) -> tuple[list[str], list[str]]:
    """Keep uncertainty-adjusted value and the separate win-rate objective distinct."""
    reasons = []
    if conservative is None or conservative <= 0:
        reasons.append("Uncertainty-adjusted net EV is not established positive")
    if (
        lower is None
        or market_probability is None
        or lower - market_probability < policy.minimum_conservative_edge
    ):
        reasons.append("Conservative probability edge is below the declared threshold")
    category_a = []
    if probability < policy.minimum_high_confidence:
        category_a.append("Calibrated win probability is below 80%")
    if odds is None or odds < policy.minimum_decimal_odds_a:
        category_a.append(
            "Sportsbook odds are shorter than the Category A price filter"
        )
    return reasons, category_a


def net_price(quote: MarketQuote | None, odds: float | None) -> float | None:
    """Unknown exchange fees cannot be assumed zero for selection."""
    return (
        1 + (odds - 1) * (1 - quote.commission)
        if odds and quote and quote.commission is not None
        else None
    )
