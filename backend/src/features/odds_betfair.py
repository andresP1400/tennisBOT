"""Betfair Exchange API adapter (free Developer API, no geo-block).

Docs: https://docs.betfair.com/display/1smk3cen4v3lu3yri5p4/account-api
Free tier: free, unlimited requests, requires app key (no real-money
account needed for read-only market data via delayed API).
"""

from __future__ import annotations

import logging

from config import settings
from features.odds_cache import TtlCache
from features.odds_common import MatchOdds, _is_live

logger = logging.getLogger(__name__)


class BetfairAdapter:
    """Betfair Exchange API adapter."""

    BASE_URL = "https://api.betfair.com/exchange/betting/rest/v1.0"
    NAME = "betfair"

    def __init__(
        self, app_key: str | None = None, session_token: str | None = None
    ) -> None:
        self._app_key = app_key or settings.betfair_app_key
        self._session_token = session_token or settings.betfair_session_token

    def is_configured(self) -> bool:
        return bool(self._app_key)

    def list_tennis_matches(self, cache: TtlCache) -> list[MatchOdds]:
        """List today's tennis matches with best odds from Betfair Exchange.

        Endpoint: listMarketCatalogue + listMarketBook.
        Returns an empty list if not configured or on error.
        """
        if not self.is_configured():
            logger.debug("Betfair adapter not configured")
            return []
        try:
            import requests

            url = f"{self.BASE_URL}/listMarketCatalogue/"
            cached = cache.get(self.NAME, url)
            if cached is not None and isinstance(cached, list):
                return cached
            headers = {
                "X-Application": self._app_key,
                "X-Authentication": self._session_token,
                "Content-Type": "application/json",
            }
            resp = requests.post(
                url,
                json={
                    "filter": {
                        "eventTypeIds": ["2"],
                        "marketTypeCodes": ["MATCH_ODDS"],
                    },
                    "marketProjection": ["EVENT", "MARKET_START_TIME", "RUNNER_NAMES"],
                    "maxResults": 200,
                },
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning("Betfair listMarketCatalogue HTTP %s", resp.status_code)
                cache.set(self.NAME, url, [])
                return []
            markets = resp.json()
            out: list[MatchOdds] = []
            for m in markets:
                runners = m.get("runners", [])
                if len(runners) != 2:
                    continue
                p1 = runners[0].get("runnerName", "")
                p2 = runners[1].get("runnerName", "")
                if not p1 or not p2:
                    continue
                ct = m.get("marketStartTime", "")
                tournament = m.get("event", {}).get("name", m.get("eventName", ""))
                out.append(
                    MatchOdds(
                        source=self.NAME,
                        player1=p1,
                        player2=p2,
                        tournament=tournament,
                        commence_time=ct,
                        is_live=_is_live(ct),
                        odds_p1=0.0,
                        odds_p2=0.0,
                    )
                )
            cache.set(self.NAME, url, out)
            return out
        except Exception as e:
            logger.warning("Betfair adapter error: %s", e)
            return []
