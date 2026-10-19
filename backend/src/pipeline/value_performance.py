"""Separate category accuracy, paper ROI and market benchmarks with explicit missing evidence."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from numpy.typing import NDArray

from pipeline.value_trials import ValueTrial, load_trials, trial_numbers


def return_interval(
    trials: list[ValueTrial], alpha: float = 0.05
) -> dict[str, object] | None:
    """Date blocks retain within-date dependence; sparse samples have no return interval."""
    if len(trials) < 30:
        return None
    frame = pd.DataFrame(
        {
            "date": [
                trial.selection.candidate.fixture.commence_time.date()
                for trial in trials
            ],
            "profit": [trial_numbers(trial)["profit"] for trial in trials],
        }
    )
    groups = frame.groupby("date").profit.agg(["sum", "count"])
    if len(groups) < 20:
        return None
    random = np.random.default_rng(42)
    indices = random.integers(0, len(groups), size=(10000, len(groups)))
    roi = groups["sum"].to_numpy()[indices].sum(axis=1) / groups["count"].to_numpy()[
        indices
    ].sum(axis=1)
    low, high = np.quantile(roi, [alpha / 2, 1 - alpha / 2])
    return {
        "lower": float(low),
        "upper": float(high),
        "confidence": 1 - alpha,
        "resamples": 10000,
        "date_blocks": len(groups),
        "method": "Approximate scheduled-date block bootstrap",
    }


def score_trials(trials: list[ValueTrial]) -> dict[str, object]:
    """Net unit returns use archived prices and exclude pending/void stakes."""
    completed = sorted(
        (
            trial
            for trial in trials
            if trial.outcome and trial.outcome.status == "completed"
        ),
        key=lambda trial: (
            trial.outcome.observed_at if trial.outcome else trial.selection.observed_at
        ),
    )
    values = [trial_numbers(trial) for trial in completed]
    count = len(completed)
    profits = np.asarray([value["profit"] for value in values], dtype=float)
    equity = np.concatenate([[0.0], np.cumsum(profits)])
    result: dict[str, object] = {
        "qualifying_unique_matches": len(trials),
        "completed": count,
        "pending": sum(trial.outcome is None for trial in trials),
        "void": sum(
            trial.outcome is not None and trial.outcome.status == "void"
            for trial in trials
        ),
        "paper_roi": float(profits.mean()) if count else None,
        "profit_units": float(profits.sum()) if count else None,
        "maximum_drawdown_units": (
            float(np.max(np.maximum.accumulate(equity) - equity)) if count else None
        ),
        "roi_interval": return_interval(completed),
        "closing_line": closing_metrics(completed),
        "drawdown_order": "Provider settlement observation time; unit stakes; voids excluded",
    }
    result.update(benchmark_returns(values))
    result.update(probability_scores(values))
    return result


def probability_scores(values: list[dict[str, float]]) -> dict[str, object]:
    """Keep calibrated model, independent Elo and archived no-vig market scores separate."""
    probability = np.asarray([v["probability"] for v in values], dtype=float)
    labels = np.asarray([v["won"] for v in values], dtype=float)
    market = np.asarray([v["market_probability"] for v in values], dtype=float)
    elo = np.asarray(
        [v["elo_probability"] for v in values if "elo_probability" in v], dtype=float
    )
    count = len(values)
    return {
        "accuracy": float(labels.mean()) if count else None,
        "mean_probability": float(probability.mean()) if count else None,
        "brier": float(np.mean((probability - labels) ** 2)) if count else None,
        "log_loss": binary_loss(labels, probability) if count else None,
        "market_brier": float(np.mean((market - labels) ** 2)) if count else None,
        "market_log_loss": binary_loss(labels, market) if count else None,
        "elo_brier": (
            float(np.mean((elo - labels) ** 2)) if count and len(elo) == count else None
        ),
        "elo_log_loss": (
            binary_loss(labels, elo) if count and len(elo) == count else None
        ),
        "calibration_gap": (
            float(abs(probability.mean() - labels.mean())) if count else None
        ),
    }


def binary_loss(
    labels: NDArray[np.float64], probabilities: NDArray[np.float64]
) -> float:
    """Numerical clipping affects scoring only, never the saved model probabilities."""
    clipped = np.clip(probabilities, 1e-12, 1 - 1e-12)
    return float(
        np.mean(-labels * np.log(clipped) - (1 - labels) * np.log(1 - clipped))
    )


def closing_metrics(trials: list[ValueTrial]) -> dict[str, object]:
    """Only explicitly recorded same-book paired closing prices support CLV."""
    values = []
    for trial in trials:
        closing, candidate = trial.closing, trial.selection.candidate
        if closing is None or trial.quote.commission is None:
            continue
        first, second = closing.odds1, closing.odds2
        probability = ((1 / first) if candidate.side == "player1" else (1 / second)) / (
            1 / first + 1 / second
        )
        odds = trial.quote.odds1 if candidate.side == "player1" else trial.quote.odds2
        net_odds = 1 + (odds - 1) * (1 - trial.quote.commission)
        values.append(net_odds * probability - 1)
    return {
        "matches_with_actual_closing": len(values),
        "mean_fair_closing_ev": float(np.mean(values)) if values else None,
        "scope": "Missing explicit closing snapshots remain unavailable; no inferred CLV",
    }


def breakdowns(trials: list[ValueTrial]) -> dict[str, object]:
    """Fixed reporting ranges are descriptive and never optimized using outcome returns."""

    def subset(attribute: str, value: str) -> list[ValueTrial]:
        return [
            trial
            for trial in trials
            if getattr(trial.selection.candidate.fixture, attribute) == value
        ]

    return {
        "by_tour": {
            tour: score_trials(subset("tour", tour)) for tour in ("atp", "wta")
        },
        "by_surface": {
            surface: score_trials(subset("surface", surface))
            for surface in ("Hard", "Clay", "Grass", "Carpet")
        },
        "by_odds": range_scores(trials, "odds"),
        "by_confidence": range_scores(trials, "confidence"),
    }


def range_scores(trials: list[ValueTrial], kind: str) -> dict[str, object]:
    """Keep small and empty buckets visible rather than reporting only favorable ranges."""
    ranges = (
        ((1, 1.4), (1.4, 2), (2, 3), (3, 1001))
        if kind == "odds"
        else ((0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.00001))
    )
    result: dict[str, object] = {}
    for low, high in ranges:
        selected = [
            trial
            for trial in trials
            if low
            <= float(
                (
                    trial.selection.candidate.decimal_odds
                    if kind == "odds"
                    else trial.selection.candidate.probability
                )
                or 0
            )
            < high
        ]
        result[f"{low:g}–{high:g}"] = score_trials(selected)
    return result


def performance_report(
    category: str, path: Path | None = None, policy: str | None = None
) -> dict[str, object]:
    """Preserve all selections and planned 100/250/500/1000-pick looks, including failures."""
    trials = load_trials(category, path, policy)
    milestones = milestone_reports(trials)
    return {
        "category": category,
        "policy_version": policy,
        "summary": score_trials(trials),
        "breakdowns": breakdowns(trials),
        "milestones": milestones,
        "paper_only": True,
        "market_beating_advantage_established": False,
        "scope": "First-ever archived selection per fixture/category; no actual wagers or execution guarantees",
        "sequential_testing": (
            "Eight planned looks (two categories × four milestones); "
            "adjusted intervals use alpha .05/8; bootstrap remains approximate"
        ),
        "public_signal_incremental_performance": None,
    }


def milestone_reports(trials: list[ValueTrial]) -> list[dict[str, object]]:
    """Planned looks wait for all first eligible picks, including losses and voids."""
    milestones: list[dict[str, object]] = []
    for target in (100, 250, 500, 1000):
        first = trials[:target]
        complete = len(first) == target and all(
            trial.outcome is not None for trial in first
        )
        settled = [
            trial
            for trial in first
            if trial.outcome and trial.outcome.status == "completed"
        ]
        milestones.append(
            {
                "target_eligible_picks": target,
                "resolved": complete,
                "metrics": score_trials(first) if complete else None,
                "adjusted_roi_interval": (
                    return_interval(settled, 0.05 / 8) if complete else None
                ),
            }
        )
    return milestones


def benchmark_returns(values: list[dict[str, float]]) -> dict[str, object]:
    """Fair comparison uses the same archived two-sided sportsbook prices."""
    count = len(values)
    return {
        "favorite_baseline_roi": (
            float(np.mean([v["market_favorite_profit"] for v in values]))
            if count
            else None
        ),
        "favorite_baseline_accuracy": (
            float(np.mean([v["market_favorite_won"] for v in values]))
            if count
            else None
        ),
        "random_price_aware_expected_roi": (
            float(np.mean([v["price_aware_random_expected_profit"] for v in values]))
            if count
            else None
        ),
    }
