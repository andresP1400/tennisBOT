"""Versioned category policy, immutable decision shape and display calculations."""

from __future__ import annotations
from datetime import datetime
import hashlib
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from features.personal_schedule import Fixture
from features.market_contracts import MarketQuote, ProbabilityEvidence
from pipeline.personal_tracking import Prediction


class ValuePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    minimum_high_confidence: float = Field(default=0.80, ge=0.80, le=1)
    minimum_decimal_odds_a: float = Field(default=1.40, gt=1, le=1000)
    minimum_conservative_edge: float = 0.02
    maximum_probability_disagreement: float = 0.20
    maximum_history_age_days: int = 30
    maximum_quote_age_seconds: int = 300

    def version(self) -> str:
        """Changing filters creates a separately auditable prospective policy."""
        return (
            "value-v1-"
            + hashlib.sha256(
                json.dumps(self.model_dump(), sort_keys=True).encode()
            ).hexdigest()[:16]
        )


class ValueCandidate(BaseModel):
    fixture: Fixture
    prediction_id: str
    model_version: str
    policy_version: str
    side: Literal["player1", "player2"]
    player: str
    probability: float
    fair_decimal_odds: float | None
    quote_id: str | None
    bookmaker: str | None
    quote_time: datetime | None = None
    quote_observed_at: datetime | None = None
    decimal_odds: float | None
    raw_market_probability: float | None
    no_vig_market_probability: float | None
    probability_edge: float | None
    estimated_ev: float | None
    net_estimated_ev: float | None
    conservative_ev: float | None
    lower_probability: float | None
    uncertainty_method: str | None
    uncertainty_source_digest: str | None
    qualifies_a: bool
    qualifies_b: bool
    evaluated_at: datetime
    reasons: list[str]
    category_a_reasons: list[str]
    supporting_reasons: list[str]
    risks: list[str]


class ValueSelection(BaseModel):
    category: Literal["A", "B"]
    candidate: ValueCandidate
    observed_at: datetime
    id: str | None = None


def candidate_payload(
    prediction: Prediction,
    side: Literal["player1", "player2"],
    quote: MarketQuote | None,
    evidence: ProbabilityEvidence | None,
    policy: ValuePolicy,
    now: datetime,
    probability: float,
    odds: float | None,
    net_odds: float | None,
    conservative: float | None,
    market: float | None,
    reasons: list[str],
    category_a: list[str],
) -> ValueCandidate:
    """Persist both the identity and computed value without implying proven profit."""
    payload = candidate_identity(prediction, side, quote, policy, now)
    payload.update(
        {
            "probability": probability,
            "fair_decimal_odds": 1 / probability if probability else None,
            "decimal_odds": odds,
            "raw_market_probability": 1 / odds if odds else None,
            "no_vig_market_probability": market,
            "probability_edge": probability - market if market is not None else None,
            "estimated_ev": probability * odds - 1 if odds else None,
            "net_estimated_ev": probability * net_odds - 1 if net_odds else None,
            "conservative_ev": conservative,
            "lower_probability": evidence.lower_probability if evidence else None,
            "uncertainty_method": evidence.method if evidence else None,
            "uncertainty_source_digest": evidence.source_digest if evidence else None,
            "qualifies_a": not reasons and (not category_a),
            "qualifies_b": not reasons,
            "reasons": reasons,
            "category_a_reasons": category_a,
        }
    )
    return ValueCandidate.model_validate(payload)


def candidate_identity(
    prediction: Prediction,
    side: Literal["player1", "player2"],
    quote: MarketQuote | None,
    policy: ValuePolicy,
    now: datetime,
) -> dict[str, object]:
    """All displayed quantities remain linked to archived model/price/policy identities."""
    return {
        "fixture": prediction.fixture,
        "prediction_id": prediction.tracking_id or "",
        "model_version": prediction.model_version,
        "policy_version": policy.version(),
        "side": side,
        "player": (
            prediction.fixture.player1
            if side == "player1"
            else prediction.fixture.player2
        ),
        "quote_id": quote.id if quote else None,
        "bookmaker": quote.bookmaker if quote else None,
        "quote_time": quote.quoted_at if quote else None,
        "quote_observed_at": quote.observed_at if quote else None,
        "evaluated_at": now,
        "supporting_reasons": [
            "Independent historical Elo/serve/return statistical model",
            "Calibrated symmetric win probability",
        ],
        "risks": [prediction.warning] if prediction.warning else [],
    }
