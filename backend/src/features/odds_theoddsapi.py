"""TheOddsAPI adapter (aggregator, free 500 req/month).

Docs: https://the-odds-api.com/liveapi/guides/v4/
Free tier: 500 requests/month. Caching is essential.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta

from features.odds_cache import TtlCache
from features.odds_common import MatchOdds, _is_live, _player_matches

logger = logging.getLogger(__name__)


class TheOddsApiAdapter:
    """TheOddsAPI adapter."""

    BASE_URL = "https://api.the-odds-api.com/v4"
    NAME = "theoddsapi"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("ODDS_API_KEY", "")
        self._available_sports: list[str] | None = None

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _fetch_available_sports(self, cache: TtlCache) -> list[str]:
        if self._available_sports is not None:
            return self._available_sports
        if not self._api_key:
            return []
        try:
            import requests
            url = f"{self.BASE_URL}/sports/"
            cached = cache.get(self.NAME, url)
            if cached is not None:
                self._available_sports = cached
                return cached
            headers = {}
            resp = requests.get(url, params={"apiKey": self._api_key}, headers=headers, timeout=15)
            if resp.status_code != 200:
                self._available_sports = []
                cache.set(self.NAME, url, [])
                return []
            sports = resp.json()
            tennis = [
                s["key"] for s in sports if s.get("key", "").startswith("tennis_")
            ]
            self._available_sports = tennis
            cache.set(self.NAME, url, tennis)
            return tennis
        except Exception as e:
            logger.warning("TheOddsAPI sports list error: %s", e)
            self._available_sports = []
            return []

    def list_tennis_matches(self, cache: TtlCache) -> list[MatchOdds]:
        """List today's tennis matches from TheOddsAPI with full odds."""
        sport_keys = self._fetch_available_sports(cache)
        if not sport_keys:
            return []
        out: list[MatchOdds] = []
        try:
            import requests
            now = datetime.now(timezone.utc)
            today_start = now.replace(
                hour=0, minute=0, second=0, microsecond=0
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            day_after = (now + timedelta(days=2)).replace(
                hour=23, minute=59, second=59, microsecond=0
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            headers = {}
            for sport in sport_keys:
                url = (
                    f"{self.BASE_URL}/sports/{sport}/odds/"
                    f"?regions=eu,us&markets=h2h&oddsFormat=decimal"
                    f"&commenceTimeFrom={today_start}&commenceTimeTo={day_after}"
                )
                cached = cache.get(self.NAME, url)
                if cached is not None:
                    if isinstance(cached, list):
                        out.extend(cached)
                    continue
                resp = requests.get(url, params={"apiKey": self._api_key}, headers=headers, timeout=15)
                if resp.status_code != 200:
                    cache.set(self.NAME, url, [])
                    continue
                events = resp.json()
                if not isinstance(events, list):
                    cache.set(self.NAME, url, [])
                    continue
                page: list[MatchOdds] = []
                for ev in events:
                    home = ev.get("home_team", "")
                    away = ev.get("away_team", "")
                    best_p1 = 0.0
                    best_p2 = 0.0
                    for bm in ev.get("bookmakers", []):
                        for mk in bm.get("markets", []):
                            if mk.get("key") != "h2h":
                                continue
                            for o in mk.get("outcomes", []):
                                price = float(o.get("price", 0))
                                if price <= 1:
                                    continue
                                if _player_matches(home, [o.get("name", "")]):
                                    best_p1 = max(best_p1, price)
                                elif _player_matches(away, [o.get("name", "")]):
                                    best_p2 = max(best_p2, price)
                    if best_p1 > 0 and best_p2 > 0:
                        page.append(
                            MatchOdds(
                                source=self.NAME,
                                player1=home,
                                player2=away,
                                tournament=sport.replace("tennis_atp_", "")
                                                .replace("tennis_wta_", "")
                                                .replace("_", " ").title(),
                                commence_time=ev.get("commence_time", ""),
                                is_live=_is_live(ev.get("commence_time", "")),
                                odds_p1=best_p1,
                                odds_p2=best_p2,
                                bookmaker="theoddsapi_best",
                                tour="atp" if "tennis_atp_" in sport else "wta",
                            )
                        )
                cache.set(self.NAME, url, page)
                out.extend(page)
            return out
        except Exception as e:
            logger.warning("TheOddsAPI adapter error: %s", e)
            return []
