"""Informational expected value with explicit data-quality and staking guards."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BettingAnalysis:
    eligible: bool
    expected_value: float | None
    edge: float | None
    stake_fraction: float
    reasons: list[str] = field(default_factory=list)


def guarded_ev(
    probability: float,
    odds: float | None,
    market_probability: float | None,
    *,
    calibrated: bool = False,
    model_age_days: int = 9999,
    quote_age_seconds: float | None = None,
    independent_books: int = 0,
    min_edge: float = 0.05,
    commission: float = 0.0,
) -> BettingAnalysis:
    """Positive raw EV alone never authorizes a wager or an unconstrained Kelly stake."""
    inputs = [probability, min_edge, commission]
    if not all(math.isfinite(value) for value in inputs) or not 0 <= probability <= 1:
        raise ValueError("Finite model probability in [0,1] is required")
    if not 0 <= min_edge <= 1 or not 0 <= commission < 1:
        raise ValueError("Invalid edge or commission")
    if odds is None or not math.isfinite(odds) or not 1 < odds <= 100:
        return BettingAnalysis(
            False, None, None, 0.0, ["No valid executable decimal price"]
        )
    net_profit = (odds - 1) * (1 - commission)
    ev = probability * net_profit - (1 - probability)
    edge = probability - market_probability if market_probability is not None else None
    reasons = data_guard_reasons(
        calibrated,
        model_age_days,
        quote_age_seconds,
        independent_books,
        market_probability,
        edge,
        min_edge,
    )
    if ev <= 0:
        reasons.append("Expected value after commission is not positive")
    stake = min(0.01, max(0.0, 0.25 * ev / net_profit)) if not reasons else 0.0
    return BettingAnalysis(not reasons, ev, edge, stake, reasons)


def data_guard_reasons(
    calibrated: bool,
    model_age_days: int,
    quote_age_seconds: float | None,
    independent_books: int,
    market_probability: float | None,
    edge: float | None,
    min_edge: float,
) -> list[str]:
    """Keep freshness, calibration, market depth, and consensus admission explicit."""
    reasons = []
    if not calibrated:
        reasons.append("Calibration provenance is unavailable")
    if not 0 <= model_age_days <= 30:
        reasons.append("Historical model inputs are stale")
    if (
        quote_age_seconds is None
        or not math.isfinite(quote_age_seconds)
        or not 0 <= quote_age_seconds <= 300
    ):
        reasons.append("Quote timestamp is missing, stale, or in the future")
    if independent_books < 2:
        reasons.append("At least two independent paired bookmaker quotes are required")
    if (
        market_probability is None
        or edge is None
        or not math.isfinite(edge)
        or not 0 < market_probability < 1
    ):
        reasons.append("No valid bookmaker consensus probability")
    elif edge < min_edge:
        reasons.append("Consensus edge is below the threshold")
    return reasons
