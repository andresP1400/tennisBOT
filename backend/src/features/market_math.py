"""Paired bookmaker consensus is distinct from executable best-price shopping."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Consensus:
    prob1: float
    prob2: float
    mean_margin: float
    books: int


def valid_price(value: float | None) -> bool:
    """Only finite decimal prices above one represent usable quotes."""
    return value is not None and math.isfinite(value) and value > 1


def bookmaker_consensus(sources: dict[str, dict[str, float]]) -> Consensus:
    """Remove each book's margin before averaging; never normalize cross-book maxima."""
    # A bookmaker relayed by multiple providers is still one market opinion.
    books = {
        name.rsplit(":", 1)[-1].strip().casefold(): pair
        for name, pair in sources.items()
    }
    pairs = [
        (pair.get("player1", 0), pair.get("player2", 0)) for pair in books.values()
    ]
    pairs = [
        (first, second)
        for first, second in pairs
        if valid_price(first) and valid_price(second)
    ]
    if not pairs:
        raise ValueError("No complete finite paired bookmaker quotes")
    totals = [1 / first + 1 / second for first, second in pairs]
    first = sum((1 / pair[0]) / total for pair, total in zip(pairs, totals)) / len(
        pairs
    )
    return Consensus(
        first, 1 - first, sum(total - 1 for total in totals) / len(pairs), len(pairs)
    )
