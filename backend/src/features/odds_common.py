"""Shared types + helpers for the multi-source odds aggregator.

Normalized schema for every source::

    {
        "match_id": str,
        "player1": str,
        "player2": str,
        "tournament": str,
        "commence_time": str (ISO 8601 UTC),
        "is_live": bool,
        "sources": {...},
        "best_odds": {"player1": float, "player2": float},
        "implied_prob1": float,
        "implied_prob2": float,
        "margin": float,
        "num_sources": int,
    }
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class MatchOdds:
    """Normalized odds for a single match from one source."""
    source: str
    player1: str
    player2: str
    tournament: str
    commence_time: str
    is_live: bool
    odds_p1: float
    odds_p2: float
    bookmaker: str = ""
    tour: str = ""


def _normalize_player(name: str) -> str:
    """Lowercase, strip, collapse spaces, drop diacritics."""
    if not isinstance(name, str):
        return ""
    s = " ".join(name.lower().strip().split())
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)
    )


def _player_matches(query: str, candidates: list[str]) -> bool:
    """Fuzzy match: query is substring of any candidate or vice-versa."""
    q = _normalize_player(query)
    if not q:
        return False
    for c in candidates:
        cn = _normalize_player(c)
        if not cn:
            continue
        if q in cn or cn in q:
            return True
    return False


def _is_live(commence_time: str) -> bool:
    """A match is LIVE if commence_time is within +/- 3h of now."""
    try:
        ct = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return abs((ct - now).total_seconds()) < 3 * 3600
    except (ValueError, AttributeError):
        return False


def _compute_implied(o1: float, o2: float) -> tuple[float, float, float]:
    """Return (implied_prob1, implied_prob2, margin) after vig-free normalization."""
    if o1 <= 1 or o2 <= 1:
        return float("nan"), float("nan"), float("nan")
    raw1 = 1.0 / o1
    raw2 = 1.0 / o2
    total = raw1 + raw2
    return raw1 / total, raw2 / total, total - 1.0
