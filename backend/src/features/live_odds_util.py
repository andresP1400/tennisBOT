"""Shared helpers for live-odds scraping (name normalization + caches).

These are module-level functions/state used by LiveOddsScraper in
features/live_odds.py; they are re-exported from there so tests that
inspect their source keep working.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime, timezone

CACHE_TTL_SECONDS = 300  # 5 minutes

_odds_cache: dict = {}
_odds_cache_timestamp: dict = {}


def _normalize_player_name(name: str) -> str:
    """Normalize player name for fuzzy matching across sites.

    Lowercase, keep only the last token and strip diacritics so that
    'Kecmanović' matches 'kecmanovic' from other sources.
    """
    if not isinstance(name, str):
        return ""
    parts = name.strip().split()
    if not parts:
        return ""
    last = parts[-1]
    return unicodedata.normalize("NFD", last).encode("ascii", "ignore").decode("ascii").lower()


def _fuzzy_match_player(query: str, candidates: list) -> str:
    """Find the best fuzzy match for a player name.

    Compares last names and handles common variations.
    Returns the best matching candidate or empty string.
    """
    query_last = _normalize_player_name(query)
    if not query_last:
        return ""
    for c in candidates:
        if _normalize_player_name(c) == query_last:
            return c
    for c in candidates:
        c_lower = c.lower()
        if query_last in c_lower or c_lower.split()[-1] in query_last:
            return c
    return ""


def _now_iso() -> str:
    """Current UTC time as ISO 8601 (datetime.utcnow() is deprecated)."""
    return datetime.now(timezone.utc).isoformat()
