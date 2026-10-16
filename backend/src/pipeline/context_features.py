"""Research-only surface summaries from matured observed matches."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from pipeline.personal_data import serve_counts

CONTEXT_NAMES = (
    "surface_serve",
    "surface_return",
    "surface_recent_results",
    "log_surface_matches",
    "log_days_since_known_tournament",
)


@dataclass
class SurfaceHistory:
    count: int = 0
    serve: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=20))
    returns: deque[tuple[float, float]] = field(
        default_factory=lambda: deque(maxlen=20)
    )
    results: deque[float] = field(default_factory=lambda: deque(maxlen=20))


@dataclass
class ContextPlayer:
    count: int = 0
    last_date: date | None = None
    surfaces: dict[str, SurfaceHistory] = field(default_factory=dict)

    def values(self, surface: str, day: date) -> list[float]:
        history = self.surfaces.get(surface, SurfaceHistory())
        return [
            observed_ratio(history.serve),
            observed_ratio(history.returns),
            float(np.mean(history.results)) if history.results else float("nan"),
            float(np.log1p(history.count)),
            (
                float(np.log1p((day - self.last_date).days))
                if self.last_date
                else float("nan")
            ),
        ]


def observed_ratio(values: deque[tuple[float, float]]) -> float:
    """Missing point counts stay missing rather than becoming neutral observed rates."""
    total = sum(item[1] for item in values)
    return sum(item[0] for item in values) / total if total else float("nan")


def observe_context(row: pd.Series, players: dict[int, ContextPlayer]) -> None:
    """Surface counts can mature even when point statistics are genuinely missing."""
    surface = str(row.surface)
    for side, prefix, opposite in (("w", "winner", "l"), ("l", "loser", "w")):
        player = players.setdefault(int(row[f"{prefix}_id"]), ContextPlayer())
        history = player.surfaces.setdefault(surface, SurfaceHistory())
        history.count += 1
        player.count += 1
        player.last_date = row.date.date()
        history.results.append(float(side == "w"))
        won, total = serve_counts(row, side)
        other_won, other_total = serve_counts(row, opposite)
        if total > 0:
            history.serve.append((won, total))
        if other_total > 0:
            history.returns.append((other_total - other_won, other_total))


def context_record(
    row: pd.Series, players: dict[int, ContextPlayer]
) -> dict[str, object]:
    """Read the exact same canonical player order and chronology as the frozen baseline."""
    first, second = sorted((int(row.winner_id), int(row.loser_id)))
    left = players.get(first, ContextPlayer())
    right = players.get(second, ContextPlayer())
    features = [
        a - b
        for a, b in zip(
            left.values(str(row.surface), row.date.date()),
            right.values(str(row.surface), row.date.date()),
        )
    ]
    return {
        "date": row.date,
        "label": int(first == int(row.winner_id)),
        "surface": row.surface,
        "player1_matches": left.count,
        "player2_matches": right.count,
        "context_features": features,
    }


def context_rows(history: pd.DataFrame) -> pd.DataFrame:
    """Never release current or future outcomes into pre-event context features."""
    players: dict[int, ContextPlayer] = {}
    pending: deque[tuple[pd.Timestamp, pd.DataFrame]] = deque()
    records: list[dict[str, object]] = []
    for day, batch in history.groupby("date", sort=True):
        while pending and pending[0][0] <= day:
            _, matured = pending.popleft()
            for _, row in matured.iterrows():
                observe_context(row, players)
        records.extend(context_record(row, players) for _, row in batch.iterrows())
        pending.append((day + pd.Timedelta(days=21), batch))
    return pd.DataFrame(records)


def attach_context(history: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    """Alignment failures must stop training instead of assigning another match's summaries."""
    context = context_rows(history)
    keys = ("date", "label", "surface", "player1_matches", "player2_matches")
    if len(context) != len(baseline) or any(
        not np.array_equal(context[key].to_numpy(), baseline[key].to_numpy())
        for key in keys
    ):
        raise ValueError(
            "Surface context does not align with canonical baseline matches"
        )
    result = baseline.copy()
    result["context_features"] = context.context_features.to_list()
    return result
