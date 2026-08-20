"""get_match_odds endpoint for LiveOddsScraper (mixin).

Collects odds from TheOddsAPI (+ optional dev scrapers), computes best
odds / implied probabilities / margin, and caches the result in the
shared module-level cache (features.live_odds_util).
"""
from __future__ import annotations

import math
import time
from typing import Any

from logging_config import get_logger
from features.live_odds_util import (
    CACHE_TTL_SECONDS,
    _now_iso,
    _odds_cache,
    _odds_cache_timestamp,
)

logger = get_logger(__name__)


class MatchOddsMixin:
    """Mixin: get_match_odds with module-level TTL cache."""

    def get_match_odds(
        self,
        player1: str,
        player2: str,
        surface: str | None = None,
        force_refresh: bool = False,
    ) -> dict:
        """Get live odds for a tennis match from TheOddsAPI.

        Returns dict with sources, best odds, implied probabilities,
        bookmaker margin, and a timestamp.
        """
        cache_key = f"{player1}|{player2}|{surface}"
        if not force_refresh and cache_key in _odds_cache:
            age = time.time() - _odds_cache_timestamp.get(cache_key, 0)
            if age < CACHE_TTL_SECONDS:
                return _odds_cache[cache_key]

        all_odds: dict = {}
        api_key = self._get_api_key()
        has_valid_key = bool(api_key) and api_key != "your_api_key_here"

        if has_valid_key:
            try:
                api_odds = self._scrape_theoddsapi(player1, player2)
                if api_odds:
                    all_odds.update(api_odds)
                    logger.info(f" [OK] TheOddsAPI: {len(api_odds)} bookmaker(s)")
            except Exception:
                pass
        else:
            print(
                " [INFO] ODDS_API_KEY not configured - skipping scraping. "
                "Configure .env for live odds."
            )

        # Scraping fallbacks are disabled by default.
        if self.enable_scraping and not all_odds and has_valid_key:
            import concurrent.futures
            scraping_tasks = [
                ("pinnacle", self._scrape_pinnacle, player1, player2),
                ("oddsportal", self._scrape_oddsportal, player1, player2),
                ("tennis_explorer", self._scrape_tennis_explorer, player1, player2),
            ]
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures_map = {
                    executor.submit(fn, p1, p2): name
                    for name, fn, p1, p2 in scraping_tasks
                }
                for future in concurrent.futures.as_completed(futures_map, timeout=30):
                    try:
                        scrape_result = future.result(timeout=10)
                        if scrape_result:
                            all_odds.update(scrape_result)
                            logger.info(f" [OK] {futures_map[future]}: {len(scrape_result)} source(s)")
                    except Exception:
                        pass

        if not all_odds:
            if not has_valid_key:
                logger.info(" [INFO] No odds: set ODDS_API_KEY in .env for live market data")
            else:
                logger.warning(f" [WARN] No odds found for {player1} vs {player2}")
        result: dict[str, Any] = {
            "sources": all_odds,
            "best_odds": {"player1": float("nan"), "player2": float("nan")},
            "implied_prob1": float("nan"),
            "implied_prob2": float("nan"),
            "margin": float("nan"),
            "needs_api_key": not has_valid_key,
            "timestamp": _now_iso(),
        }
        if all_odds:
            p1_odds = [
                v["player1"] for v in all_odds.values()
                if not (isinstance(v.get("player1"), float) and math.isnan(v.get("player1")))
            ]
            p2_odds = [
                v["player2"] for v in all_odds.values()
                if not (isinstance(v.get("player2"), float) and math.isnan(v.get("player2")))
            ]
            if p1_odds:
                result["best_odds"]["player1"] = max(p1_odds)
            if p2_odds:
                result["best_odds"]["player2"] = max(p2_odds)
            best_p1 = result["best_odds"]["player1"]
            best_p2 = result["best_odds"]["player2"]
            if (
                not (isinstance(best_p1, float) and math.isnan(best_p1))
                and not (isinstance(best_p2, float) and math.isnan(best_p2))
                and best_p1 > 1 and best_p2 > 1
            ):
                raw_imp1 = 1.0 / best_p1
                raw_imp2 = 1.0 / best_p2
                total = raw_imp1 + raw_imp2
                result["implied_prob1"] = raw_imp1 / total
                result["implied_prob2"] = raw_imp2 / total
                result["margin"] = total - 1.0

        _odds_cache[cache_key] = result
        _odds_cache_timestamp[cache_key] = time.time()
        return result
