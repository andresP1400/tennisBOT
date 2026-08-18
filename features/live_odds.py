"""Live odds scraping module for tennis matches.

Primary data source:
  - TheOddsAPI (https://the-odds-api.com)
    Free JSON API, 500 req/month. Returns odds from 30+ bookmakers
    (Pinnacle, Bet365, FanDuel, DraftKings, Codere IT, William Hill, ...).
    Covers ATP/WTA Grand Slams and major tournaments.
    Market: h2h (moneyline) with decimal odds.

Scraping fallbacks (DISABLED by default -- geo-blocked from Italy and
unreliable in production):

  - OddsPortal scraping
  - Direct Pinnacle public API
  - Tennis Explorer scraping

Enable them only with `force_refresh=True` and `enable_scraping=True`
for development / debugging.
"""
from __future__ import annotations

import math
import os
import re
import sys
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv

from logging_config import get_logger
logger = get_logger(__name__)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
# .env first, then local.env (personal secrets override)
load_dotenv(os.path.join(_ROOT, ".env"))
load_dotenv(os.path.join(_ROOT, "local.env"), override=True)

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


class LiveOddsScraper:
    """Scrape live tennis odds from TheOddsAPI.

    Scraping paths are intentionally disabled by default. TheOddsAPI is the
    only production-grade source; the scrapers are kept for dev/debug
    because they are geo-blocked from Italy and unstable.
    """

    def __init__(
        self,
        use_stealth: bool = True,
        api_key: str | None = None,
        enable_scraping: bool = False,
    ) -> None:
        self.use_stealth = use_stealth
        self.enable_scraping = enable_scraping
        self._fetcher = None
        self._api_key = api_key or os.environ.get("ODDS_API_KEY", "")
        self._available_sports: list | None = None

    def _get_fetcher(self):
        """Lazy-initialize the Scrapling fetcher (only when scraping is on)."""
        if not self.enable_scraping:
            return None
        if self._fetcher is not None:
            return self._fetcher
        try:
            from scrapling import Fetcher, StealthyFetcher
            self._fetcher = StealthyFetcher() if self.use_stealth else Fetcher()
            return self._fetcher
        except ImportError:
            return None

    def _get_api_key(self) -> str:
        """Get TheOddsAPI key from instance or environment."""
        return self._api_key or os.environ.get("ODDS_API_KEY", "")

    # -----------------------------------------------------------------
    # SOURCE 1: TheOddsAPI (JSON API - most reliable)
    # -----------------------------------------------------------------
    def _fetch_available_tennis_sports(self) -> list:
        """Fetch list of available tennis sport keys from TheOddsAPI."""
        if self._available_sports is not None:
            return self._available_sports
        api_key = self._get_api_key()
        if not api_key:
            self._available_sports = []
            return []
        try:
            import requests
            url = "https://api.the-odds-api.com/v4/sports/"
            resp = requests.get(url, params={"apiKey": api_key}, timeout=15)
            if resp.status_code != 200:
                self._available_sports = []
                return []
            all_sports = resp.json()
            tennis_sports = [s for s in all_sports if s.get("key", "").startswith("tennis_")]
            self._available_sports = [s["key"] for s in tennis_sports]
            return self._available_sports
        except Exception:
            self._available_sports = []
            return []

    def _scrape_theoddsapi(self, player1: str, player2: str) -> dict:
        """Fetch odds from TheOddsAPI.

        Queries all available tennis tournaments and matches player names
        to find the specific match.
        """
        api_key = self._get_api_key()
        if not api_key:
            return {}
        sport_keys = self._fetch_available_tennis_sports()
        if not sport_keys:
            return {}

        import requests
        all_odds: dict = {}
        for sport_key in sport_keys:
            try:
                url = (
                    f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
                    f"?regions=eu,us"
                    f"&markets=h2h"
                    f"&oddsFormat=decimal"
                )
                resp = requests.get(url, params={"apiKey": api_key}, timeout=15)
                if resp.status_code != 200:
                    continue
                events = resp.json()
                if not isinstance(events, list):
                    continue
                for event in events:
                    home = event.get("home_team", "")
                    away = event.get("away_team", "")
                    if not (_fuzzy_match_player(player1, [home, away]) and
                            _fuzzy_match_player(player2, [home, away])):
                        continue
                    for bm in event.get("bookmakers", []):
                        bm_name = bm.get("key", bm.get("title", "unknown"))
                        for market in bm.get("markets", []):
                            if market.get("key") != "h2h":
                                continue
                            outcomes = market.get("outcomes", [])
                            if len(outcomes) < 2:
                                continue
                            odds_p1: float | None = None
                            odds_p2: float | None = None
                            for o in outcomes:
                                name = o.get("name", "")
                                price = o.get("price", 0)
                                if _fuzzy_match_player(player1, [name]):
                                    odds_p1 = float(price)
                                elif _fuzzy_match_player(player2, [name]):
                                    odds_p2 = float(price)
                                elif _normalize_player_name(name) == _normalize_player_name(home):
                                    odds_p1 = float(price)
                                elif _normalize_player_name(name) == _normalize_player_name(away):
                                    odds_p2 = float(price)
                            if odds_p1 and odds_p2:
                                all_odds[f"theoddsapi_{bm_name}"] = {
                                    "player1": odds_p1,
                                    "player2": odds_p2,
                                }
                time.sleep(0.5)
            except Exception:
                continue
        return all_odds

    # -----------------------------------------------------------------
    # DISABLED scraping paths (kept for dev/debug only)
    # -----------------------------------------------------------------
    def _scrape_oddsportal(self, player1: str, player2: str) -> dict:
        """Scrape today's tennis odds from OddsPortal.

        Disabled by default. Enable with `enable_scraping=True`.
        """
        if not self.enable_scraping:
            return {}
        fetcher = self._get_fetcher()
        if fetcher is None:
            return {}
        p1_key = _normalize_player_name(player1)
        p2_key = _normalize_player_name(player2)
        all_odds: dict = {}
        urls = [
            "https://www.oddsportal.com/tennis/atp/",
            "https://www.oddsportal.com/tennis/wta/",
        ]
        for url in urls:
            try:
                page = fetcher.fetch(url) if self.use_stealth else fetcher.get(url)
                text = page.text if hasattr(page, "text") else str(page)
                lines = text.split("\n") if isinstance(text, str) else []
                for line in lines:
                    line_lower = line.lower()
                    if p1_key in line_lower and p2_key in line_lower:
                        odds_pattern = re.compile(r"(\d+\.\d{2,3})")
                        found = odds_pattern.findall(line)
                        if len(found) >= 2:
                            try:
                                o1 = float(found[0])
                                o2 = float(found[1])
                                if 1.01 < o1 < 50 and 1.01 < o2 < 50:
                                    all_odds["oddsportal"] = {
                                        "player1": o1,
                                        "player2": o2,
                                    }
                            except (ValueError, IndexError):
                                pass
                        break
                time.sleep(2)
            except Exception as e:
                logger.warning(f" [WARN] OddsPortal scraping failed: {e}")
        return all_odds

    def _scrape_pinnacle(self, player1: str, player2: str) -> dict:
        """DISABLED: Pinnacle geo-blocks Italy. Use TheOddsAPI instead."""
        return {}

    def _scrape_tennis_explorer(self, player1: str, player2: str) -> dict:
        """DISABLED: Tennis Explorer scraper no longer matches the live DOM."""
        return {}

    # -----------------------------------------------------------------
    # todays-match-list (aggregator for finding matches)
    # -----------------------------------------------------------------
    def get_todays_matches(self, tour: str = "atp") -> list:
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

    # Cache for todays-matches: stale-while-revalidate. Fetching all
    # sources (SofaScore etc.) can take 30-60s which exceeds the Next.js
    # proxy timeout, so callers always get a fast cached response while a
    # background thread refreshes the data.
    _matches_cache: dict = {}
    _matches_cache_time: dict = {}
    _matches_refreshing: set = set()
    MATCHES_CACHE_TTL = 300  # 5 minutes
    MATCHES_STALE_TTL = 3600  # serve stale data up to 1h

    def get_todays_matches_cached(self, tour: str = "atp") -> list:
        cache_key = f"todays|{tour}"
        now = time.time()
        cached = self._matches_cache.get(cache_key)
        fresh = (
            cached is not None
            and now - self._matches_cache_time.get(cache_key, 0) < self.MATCHES_CACHE_TTL
        )
        stale = cached is not None
        if fresh:
            return cached
        if stale and cache_key in self._matches_refreshing:
            return cached
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

    def _get_todays_matches_api_legacy(self, tour: str) -> list:
        """Legacy: TheOddsAPI-only fallback path."""
        return self._get_todays_matches_api(tour)

    def _get_todays_matches_api(self, tour: str) -> list:
        """Get today's matches from TheOddsAPI."""
        import requests
        api_key = self._get_api_key()
        sport_keys = self._fetch_available_tennis_sports()
        if not sport_keys:
            return []
        if tour == "atp":
            sport_keys = [k for k in sport_keys if "atp" in k]
        elif tour == "wta":
            sport_keys = [k for k in sport_keys if "wta" in k]
        if not sport_keys:
            return []
        matches: list = []
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
        day_after = (now + timedelta(days=2)).replace(hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
        for sport_key in sport_keys:
            try:
                url = (
                    f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
                    f"?regions=eu,us"
                    f"&markets=h2h"
                    f"&oddsFormat=decimal"
                    f"&commenceTimeFrom={today_start}"
                    f"&commenceTimeTo={day_after}"
                )
                resp = requests.get(url, params={"apiKey": api_key}, timeout=15)
                if resp.status_code != 200:
                    continue
                events = resp.json()
                if not isinstance(events, list):
                    continue
                for event in events:
                    odds_by_bookmaker: dict = {}
                    for bm in event.get("bookmakers", []):
                        bm_name = bm.get("title", bm.get("key", "unknown"))
                        for market in bm.get("markets", []):
                            if market.get("key") != "h2h":
                                continue
                            outcomes = market.get("outcomes", [])
                            if len(outcomes) >= 2:
                                o1 = outcomes[0].get("price", 0)
                                o2 = outcomes[1].get("price", 0)
                                if o1 > 1 and o2 > 1:
                                    odds_by_bookmaker[bm_name] = {
                                        "player1": float(o1),
                                        "player2": float(o2),
                                    }
                    best_p1 = max(
                        (v["player1"] for v in odds_by_bookmaker.values()), default=0
                    )
                    best_p2 = max(
                        (v["player2"] for v in odds_by_bookmaker.values()), default=0
                    )
                    implied_prob1 = float("nan")
                    implied_prob2 = float("nan")
                    margin = float("nan")
                    if best_p1 > 1 and best_p2 > 1:
                        raw_imp1 = 1.0 / best_p1
                        raw_imp2 = 1.0 / best_p2
                        total = raw_imp1 + raw_imp2
                        implied_prob1 = raw_imp1 / total
                        implied_prob2 = raw_imp2 / total
                        margin = total - 1.0
                    tournament = (
                        sport_key.replace("tennis_atp_", "")
                        .replace("tennis_wta_", "")
                        .replace("_", " ")
                        .title()
                    )
                    matches.append({
                        "player1": event.get("home_team", ""),
                        "player2": event.get("away_team", ""),
                        "tournament": tournament,
                        "surface": "",
                        "commence_time": event.get("commence_time", ""),
                        "sport_key": sport_key,
                        "odds": odds_by_bookmaker,
                        "best_odds": {"player1": best_p1, "player2": best_p2},
                        "implied_prob1": implied_prob1,
                        "implied_prob2": implied_prob2,
                        "margin": margin,
                        "num_bookmakers": len(odds_by_bookmaker),
                    })
                time.sleep(0.5)
            except Exception:
                continue
        return matches

    # -----------------------------------------------------------------
    # MAIN: get_match_odds
    # -----------------------------------------------------------------
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


def compute_value_bets(
    model_prob1: float,
    player1: str,
    player2: str,
    surface: str | None = None,
    min_edge: float = 0.05,
) -> dict:
    """Compute value bets by comparing model probability to market odds.

    A value bet exists when model_prob > market_implied_prob + min_edge.
    """
    scraper = LiveOddsScraper()
    odds = scraper.get_match_odds(player1, player2, surface)
    best_p1 = odds.get("best_odds", {}).get("player1", float("nan"))
    best_p2 = odds.get("best_odds", {}).get("player2", float("nan"))
    no_odds = (
        best_p1 is None
        or best_p2 is None
        or (isinstance(best_p1, float) and math.isnan(best_p1))
        or (isinstance(best_p2, float) and math.isnan(best_p2))
        or (isinstance(best_p1, (int, float)) and best_p1 <= 1)
        or (isinstance(best_p2, (int, float)) and best_p2 <= 1)
    )
    if no_odds:
        key_missing = not bool(os.environ.get("ODDS_API_KEY", "").strip()) or (
            os.environ.get("ODDS_API_KEY", "").strip() == "your_api_key_here"
        )
        return {
            "player1": player1,
            "player2": player2,
            "model_prob1": model_prob1,
            "model_prob2": 1.0 - model_prob1,
            "market_prob1": None,
            "market_prob2": None,
            "edge1": None,
            "edge2": None,
            "best_odds": {"player1": None, "player2": None},
            "value_bets": [],
            "min_edge": min_edge,
            "needs_odds_key": key_missing,
            "message": (
                "ODDS_API_KEY non configurata. Aggiungila al file .env e riavvia l'API "
                "per confrontare modello vs mercato."
                if key_missing
                else "Nessuna quota di mercato disponibile per questo matchup "
                "(nessun evento live trovato o bookmaker non raggiungibili)."
            ),
        }
    raw_imp1 = 1.0 / best_p1
    raw_imp2 = 1.0 / best_p2
    total = raw_imp1 + raw_imp2
    market_prob1 = raw_imp1 / total
    market_prob2 = raw_imp2 / total
    edge1 = model_prob1 - market_prob1
    edge2 = (1.0 - model_prob1) - market_prob2
    value_bets = []
    if edge1 >= min_edge:
        value_bets.append({
            "side": player1,
            "model_prob": model_prob1,
            "market_prob": market_prob1,
            "edge": edge1,
            "best_odds": best_p1,
            "bookmaker_count": len(odds.get("sources", {})),
        })
    if edge2 >= min_edge:
        value_bets.append({
            "side": player2,
            "model_prob": 1.0 - model_prob1,
            "market_prob": market_prob2,
            "edge": edge2,
            "best_odds": best_p2,
            "bookmaker_count": len(odds.get("sources", {})),
        })
    return {
        "player1": player1,
        "player2": player2,
        "model_prob1": model_prob1,
        "model_prob2": 1.0 - model_prob1,
        "market_prob1": market_prob1,
        "market_prob2": market_prob2,
        "edge1": edge1,
        "edge2": edge2,
        "best_odds": odds.get("best_odds", {}),
        "value_bets": value_bets,
        "min_edge": min_edge,
        "sources": odds.get("sources", {}),
    }
