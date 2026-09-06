"""Todays-matches endpoints for LiveOddsScraper (mixin).

Provides the OddsAggregator-based match list with stale-while-revalidate
caching. The mixin relies on the base class methods
``_get_todays_matches_api`` / ``_fetch_available_tennis_sports``.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from logging_config import get_logger

logger = get_logger(__name__)


class TodaysMatchesMixin:
    """Mixin: today's match list with stale-while-revalidate cache."""

    def _get_todays_matches_api(self, tour: str) -> list[dict[str, Any]]:
        """Provided by the orchestrating LiveOddsScraper."""
        raise NotImplementedError

    # Cache for todays-matches: stale-while-revalidate. Fetching all
    # sources (SofaScore etc.) can take 30-60s which exceeds the Next.js
    # proxy timeout, so callers always get a fast cached response while a
    # background thread refreshes the data.
    _matches_cache: dict[str, Any] = {}
    _matches_cache_time: dict[str, Any] = {}
    _matches_refreshing: set[str] = set()
    MATCHES_CACHE_TTL = 300  # 5 minutes
    MATCHES_STALE_TTL = 3600  # serve stale data up to 1h

    def get_todays_matches(self, tour: str = "atp") -> list[dict[str, Any]]:
        """Get list of today's tennis matches with odds.

        Uses the multi-source OddsAggregator (Betfair + Pinnacle +
        TheOddsAPI) when available. Falls back to legacy
        TheOddsAPI-only path when the aggregator module is not importable.
        """
        try:
            from features.odds_aggregator import OddsAggregator

            agg = OddsAggregator()
            if not agg.adapters:
                return self._get_todays_matches_api(tour)
            return agg.get_today_matches(tour)
        except ImportError:
            return self._get_todays_matches_api_legacy(tour)

    def get_todays_matches_cached(self, tour: str = "atp") -> list[dict[str, Any]]:
        cache_key = f"todays|{tour}"
        now = time.time()
        cached = self._matches_cache.get(cache_key)
        fresh = (
            cached is not None
            and now - self._matches_cache_time.get(cache_key, 0)
            < self.MATCHES_CACHE_TTL
        )
        stale = cached is not None
        if fresh:
            return cached or []
        if stale and cache_key in self._matches_refreshing:
            return cached or []
        self._matches_refreshing.add(cache_key)

        def _refetch() -> None:
            try:
                try:
                    result = self.get_todays_matches(tour)
                except Exception as e:
                    logger.warning(f" [WARN] todays-matches refresh failed: {e}")
                    result = []
                self._matches_cache[cache_key] = result
                self._matches_cache_time[cache_key] = time.time()
            finally:
                self._matches_refreshing.discard(cache_key)

        if not stale:
            _refetch()  # no stale data yet: must wait for the first fetch
        else:
            threading.Thread(
                target=_refetch, name=f"matches-refresh-{tour}", daemon=True
            ).start()
        return cached or []

    def _get_todays_matches_api_legacy(self, tour: str) -> list[dict[str, Any]]:
        """Legacy: TheOddsAPI-only fallback path."""
        return self._get_todays_matches_api(tour)
