"""Join actual archived selections, prices, forecasts and provider-confirmed outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from features.value_contracts import ValueSelection
from features.market_contracts import MarketQuote
from features.market_comparison import same_fixture
from features.personal_results import MatchOutcome
from pipeline.market_store import records
from pipeline.personal_settlement import initialize_outcomes, matches_outcome
from pipeline.personal_state import normalize_name
from pipeline.personal_tracking import TRACKING_DB, Prediction


@dataclass
class ValueTrial:
    selection: ValueSelection
    quote: MarketQuote
    outcome: MatchOutcome | None
    closing: MarketQuote | None
    elo_probability: float | None = None


def load_trials(
    category: str, path: Path | None = None, policy: str | None = None
) -> list[ValueTrial]:
    """First-ever pick per fixture/category, preserving failures across model/policy versions."""
    selections = records("value_selections", ValueSelection, path=path)
    quotes = records("market_quotes", MarketQuote, path=path)
    prices = {quote.id: quote for quote in quotes}
    forecasts, outcomes = archived_results(path)
    selected: dict[str, ValueTrial] = {}
    for selection in selections:
        candidate = selection.candidate
        if (
            selection.category != category
            or policy is not None
            and candidate.policy_version != policy
        ):
            continue
        quote, forecast = prices.get(candidate.quote_id), forecasts.get(
            candidate.prediction_id
        )
        if quote is None or forecast is None:
            raise ValueError(
                "Archived selection has missing immutable forecast/price evidence"
            )
        result = outcomes.get(candidate.fixture.id)
        if result is not None and not matches_outcome(forecast, result):
            result = None
        selected.setdefault(
            candidate.fixture.id,
            make_trial(selection, quote, forecast, result, quotes),
        )
    return list(selected.values())


def make_trial(
    selection: ValueSelection,
    quote: MarketQuote,
    forecast: Prediction,
    result: MatchOutcome | None,
    quotes: list[MarketQuote],
) -> ValueTrial:
    """Elo benchmark is bound to the same selected side as the archived ML probability."""
    elo = (
        forecast.elo_prob1
        if selection.candidate.side == "player1"
        else 1 - forecast.elo_prob1
    )
    return ValueTrial(selection, quote, result, closing_quote(selection, quotes), elo)


def closing_quote(
    selection: ValueSelection, quotes: list[MarketQuote]
) -> MarketQuote | None:
    """Last observed prices are never relabeled as a closing line."""
    candidate = selection.candidate
    closing = [
        quote
        for quote in quotes
        if quote.kind == "closing"
        and quote.provenance == "theoddsapi"
        and same_fixture(quote.fixture, candidate.fixture)
        and quote.bookmaker == candidate.bookmaker
        and quote.quoted_at is not None
        and quote.observed_at >= selection.observed_at
        and quote.commission is not None
    ]
    return max(closing, key=lambda quote: quote.observed_at) if closing else None


def trial_numbers(trial: ValueTrial) -> dict[str, float]:
    """Unit-stake paper returns at genuine observed prices, net of known commission."""
    candidate, outcome, quote = trial.selection.candidate, trial.outcome, trial.quote
    if outcome is None or outcome.status != "completed" or quote.commission is None:
        raise ValueError("Unsettled/void trials cannot supply staked returns")
    won = float(normalize_name(candidate.player) == normalize_name(str(outcome.winner)))
    odds = quote.odds1 if candidate.side == "player1" else quote.odds2
    opposite = quote.odds2 if candidate.side == "player1" else quote.odds1
    profit = won * (odds - 1) * (1 - quote.commission) - (1 - won)
    other_profit = (1 - won) * (opposite - 1) * (1 - quote.commission) - won
    market = candidate.no_vig_market_probability
    if market is None:
        raise ValueError("Selection is missing its archived consensus benchmark")
    favorite_profit = profit if market >= 0.5 else other_profit
    result = {
        "won": won,
        "profit": profit,
        "probability": candidate.probability,
        "market_probability": market,
        "market_favorite_won": won if market >= 0.5 else 1 - won,
        "market_favorite_profit": favorite_profit,
        "price_aware_random_expected_profit": market * profit
        + (1 - market) * other_profit,
    }
    if trial.elo_probability is not None:
        result["elo_probability"] = trial.elo_probability
    return result


def archived_results(
    path: Path | None,
) -> tuple[dict[str, Prediction], dict[str, MatchOutcome]]:
    """Load immutable prediction/result maps once rather than query per pick."""
    database = initialize_outcomes(path or TRACKING_DB)
    try:
        forecasts = {
            identifier: Prediction.model_validate_json(payload)
            for identifier, payload in database.execute(
                "SELECT id, payload FROM prediction_events"
            )
        }
        outcomes = {
            identifier: MatchOutcome.model_validate_json(payload)
            for identifier, payload in database.execute(
                "SELECT fixture_id, payload FROM outcome_events"
            )
        }
    finally:
        database.close()
    return forecasts, outcomes
