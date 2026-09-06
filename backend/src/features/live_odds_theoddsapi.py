"""TheOddsAPI data-source methods for LiveOddsScraper (mixin).

The API key must be sent as ``?apiKey=`` query param (TheOddsAPI
rejects every auth header -- verified live 2026-08-14).

The regression test test_theoddsapi_uses_api_key_query_param() resolves
these methods via ``live_odds.LiveOddsScraper`` (MRO attribute lookup),
so moving them here does not break the contract.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from logging_config import get_logger
from features.live_odds_util import (
    _fuzzy_match_player,
    _normalize_player_name,
)

logger = get_logger(__name__)


class TheOddsApiMixin:
    """Mixin: TheOddsAPI sport list, per-match odds and today's matches."""

    _available_sports: list[str] | None

    def _get_api_key(self) -> str:
        """Provided by the orchestrating LiveOddsScraper."""
        raise NotImplementedError

    def _fetch_available_tennis_sports(self) -> list[str]:
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
            tennis_sports = [
                s for s in all_sports if s.get("key", "").startswith("tennis_")
            ]
            self._available_sports = [str(s["key"]) for s in tennis_sports]
            return self._available_sports
        except Exception as exc:
            logger.warning("theoddsapi sports listing failed: %s", exc)
            self._available_sports = []
            return []

    def _scrape_theoddsapi(self, player1: str, player2: str) -> dict[str, Any]:
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

        all_odds: dict[str, Any] = {}
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
                    if not (
                        _fuzzy_match_player(player1, [home, away])
                        and _fuzzy_match_player(player2, [home, away])
                    ):
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
                                elif _normalize_player_name(
                                    name
                                ) == _normalize_player_name(home):
                                    odds_p1 = float(price)
                                elif _normalize_player_name(
                                    name
                                ) == _normalize_player_name(away):
                                    odds_p2 = float(price)
                            if odds_p1 and odds_p2:
                                all_odds[f"theoddsapi_{bm_name}"] = {
                                    "player1": odds_p1,
                                    "player2": odds_p2,
                                }
                time.sleep(0.5)
            except Exception as exc:
                logger.warning(
                    "theoddsapi odds fetch failed for %s: %s", sport_key, exc
                )
                continue
        return all_odds

    def _get_todays_matches_api(self, tour: str) -> list[dict[str, Any]]:
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
        matches: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        day_after = (
            (now + timedelta(days=2))
            .replace(hour=23, minute=59, second=59, microsecond=0)
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        )
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
                    odds_by_bookmaker: dict[str, Any] = {}
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
                    matches.append(
                        {
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
                        }
                    )
                time.sleep(0.5)
            except Exception as exc:
                logger.warning(
                    "theoddsapi today-matches fetch failed for %s: %s", sport_key, exc
                )
                continue
        return matches
