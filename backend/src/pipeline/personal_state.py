"""Small forward-only global/surface Elo and historical player summaries."""

from __future__ import annotations

import math
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from datetime import date

import numpy as np

SURFACES = ("Hard", "Clay", "Grass", "Carpet")
FEATURES = (
    "elo",
    "surface_elo",
    "rank",
    "points",
    "age",
    "height",
    "form",
    "serve",
    "return",
    "experience",
)


def normalize_name(name: str) -> str:
    """Match exact names across accent/punctuation variants without fuzzy guesses."""
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKD", name).casefold()
            if not unicodedata.combining(c) and (c.isalnum() or c.isspace())
        ).split()
    )


@dataclass
class Player:
    """Statistics known before the next tournament-date batch."""

    name: str
    elo: float = 1500.0
    surface_elo: dict[str, float] = field(default_factory=dict)
    surface_count: dict[str, int] = field(default_factory=dict)
    count: int = 0
    rank: float = 2000.0
    points: float = 0.0
    age: float = 27.0
    height: float = 180.0
    last_date: date | None = None
    results: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    serve: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=20))
    returns: deque[tuple[float, float]] = field(
        default_factory=lambda: deque(maxlen=20)
    )
    adjusted_results: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    adjusted_serve: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    adjusted_return: deque[float] = field(default_factory=lambda: deque(maxlen=20))

    def values(self, surface: str) -> list[float]:
        """Return predictors derived entirely from already-observed matches."""
        count = self.surface_count.get(surface, 0)
        weight = count / (count + 20.0)
        blended = (
            weight * self.surface_elo.get(surface, 1500.0) + (1 - weight) * self.elo
        )
        return [
            self.elo / 400,
            blended / 400,
            math.log1p(self.rank),
            math.log1p(self.points),
            self.age / 10,
            self.height / 100,
            float(np.mean(self.results)) if self.results else 0.5,
            ratio(self.serve, 0.6),
            ratio(self.returns, 0.4),
            math.log1p(self.count),
        ]


def ratio(values: deque[tuple[float, float]], default: float) -> float:
    """Pool historical counts rather than averaging tiny-match percentages."""
    total = sum(pair[1] for pair in values)
    return sum(pair[0] for pair in values) / total if total else default


def match_vector(
    first: Player,
    second: Player,
    surface: str,
    best_of: int = 3,
    *,
    feature_schema: int = 1,
    use_recent_form: bool = True,
) -> list[float]:
    """Signed differences invert when player order reverses; context stays fixed."""
    vector = (
        [a - b for a, b in zip(first.values(surface), second.values(surface))]
        + [float(surface == item) for item in SURFACES]
        + [float(best_of == 5)]
    )
    if not use_recent_form:
        vector[6] = 0.0
    if feature_schema >= 2:
        for key in ("adjusted_results", "adjusted_serve", "adjusted_return"):
            left, right = getattr(first, key, []), getattr(second, key, [])
            difference = (float(np.mean(left)) if left else 0) - (
                float(np.mean(right)) if right else 0
            )
            vector.append(
                difference if key != "adjusted_results" or use_recent_form else 0.0
            )
    return vector


def elo_probability(first: Player, second: Player, surface: str) -> float:
    """Surface Elo shrinks toward global Elo for players with little surface history."""
    difference = first.values(surface)[1] - second.values(surface)[1]
    return 1 / (1 + 10 ** (-difference))


def update_ratings(winner: Player, loser: Player, surface: str) -> None:
    """Update only after the whole tournament-date feature batch is frozen."""
    expected = 1 / (1 + 10 ** ((loser.elo - winner.elo) / 400))
    change = 24 * (1 - expected)
    winner.elo += change
    loser.elo -= change
    win_surface = winner.surface_elo.get(surface, 1500.0)
    lose_surface = loser.surface_elo.get(surface, 1500.0)
    change = 24 * (1 - 1 / (1 + 10 ** ((lose_surface - win_surface) / 400)))
    winner.surface_elo[surface] = win_surface + change
    loser.surface_elo[surface] = lose_surface - change
    for player, outcome in [(winner, 1.0), (loser, 0.0)]:
        player.count += 1
        player.surface_count[surface] = player.surface_count.get(surface, 0) + 1
        player.results.append(outcome)
