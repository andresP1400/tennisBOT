"""Pinnacle Lines API adapter (legacy public endpoint).

Public legacy endpoint: https://api.pinnacle.com/en/v1/lines
Returns JSON lines for most tennis events. No API key required
for the public lines endpoint (rate-limited server-side).

Note: Pinnacle has deprecated this in favor of the official API
(which requires a real-money account), but the legacy lines endpoint
is still functional and free.
"""

from __future__ import annotations

import logging

from features.odds_cache import TtlCache
from features.odds_common import MatchOdds, _is_live

logger = logging.getLogger(__name__)


class PinnacleAdapter:
    """Pinnacle Lines API adapter."""

    BASE_URL = "https://api.pinnacle.com/en/v1/leagues/19/matchups"
    NAME = "pinnacle"
    TENNIS_SPORT_ID = 19  # Pinnacle tennis sport ID

    def __init__(self) -> None:
        pass

    def is_configured(self) -> bool:
        return True  # public endpoint, no key needed

    def list_tennis_matches(self, cache: TtlCache) -> list[MatchOdds]:
        """List today's tennis matches from Pinnacle lines."""
        try:
            import requests

            url = self.BASE_URL
            cached = cache.get(self.NAME, url)
            if cached is not None and isinstance(cached, list):
                return cached
            headers = {"User-Agent": "Mozilla/5.0 tennisBOT/2.1"}
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                cache.set(self.NAME, url, [])
                return []
            data = resp.json()
            if not isinstance(data, dict) and not isinstance(data, list):
                cache.set(self.NAME, url, [])
                return []
            matchups = data.get("matchups", []) if isinstance(data, dict) else data
            out: list[MatchOdds] = []
            for m in matchups:
                participants = m.get("participants", [])
                if len(participants) != 2:
                    continue
                p1 = participants[0].get("name", "")
                p2 = participants[1].get("name", "")
                if not p1 or not p2:
                    continue
                ct = m.get("startTime", "")
                tournament = m.get("leagueName", "")
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
            logger.warning("Pinnacle adapter error: %s", e)
            return []
