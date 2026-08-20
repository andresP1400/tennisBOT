"""SofaScore public API adapter (bet365 + 250 bookmakers, no key).

The web JSON backend at api.sofascore.com is open (no auth). It is
protected by Akamai TLS fingerprinting, so we use curl_cffi with a
Chrome impersonation profile (same approach as the popular
sofascore-api community libraries).

Endpoints used:
  - /api/v1/sport/tennis/odds/1/{date}   -> pre-match odds, provider 1
  - /api/v1/sport/tennis/events/live     -> live tennis events
  - /api/v1/event/{id}                   -> event detail (player names)

Odds are returned as fractional strings ("11/10") and converted to
decimal. No registration, no API key, no rate-limit weight beyond
a sensible TTL cache.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from features.odds_cache import TtlCache
from features.odds_common import MatchOdds

logger = logging.getLogger(__name__)


class SofaScoreAdapter:
    """SofaScore public API adapter."""

    BASE_URL = "https://api.sofascore.com/api/v1"
    NAME = "sofascore"

    def __init__(self) -> None:
        try:
            from curl_cffi import requests as cr
            self._http = cr
            self._impersonate = "chrome"
        except ImportError:
            # Fallback: plain requests (may be blocked by Akamai).
            import requests
            self._http = requests
            self._impersonate = None
        self._user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )

    def is_configured(self) -> bool:
        return True  # always available, no key needed

    def _get(self, url: str, timeout: float = 15.0) -> dict | None:
        kwargs: dict = {"timeout": timeout}
        if self._impersonate:
            kwargs["impersonate"] = self._impersonate
        else:
            kwargs["headers"] = {"User-Agent": self._user_agent}
        resp = self._http.get(url, **kwargs)
        if resp.status_code != 200:
            return None
        return resp.json()

    @staticmethod
    def _fractional_to_decimal(value: str) -> float:
        """'11/10' -> 2.1 ; '4/6' -> 1.6667. Returns 0.0 on failure."""
        try:
            num, _, den = value.strip().partition("/")
            if not den:
                return float(num)
            return 1.0 + float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            return 0.0

    def list_tennis_matches(self, cache: TtlCache) -> list[MatchOdds]:
        """Today's pre-match odds + live events from SofaScore."""
        out: list[MatchOdds] = []
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            odds_url = f"{self.BASE_URL}/sport/tennis/odds/1/{today}"
            cached = cache.get(self.NAME, odds_url)
            if cached is None:
                data = self._get(odds_url)
                cached = data or {}
                cache.set(self.NAME, odds_url, cached)
            if isinstance(cached, dict) and isinstance(cached.get("odds"), dict):
                for event_id, market in cached["odds"].items():
                    if not isinstance(market, dict):
                        continue
                    choices = market.get("choices", [])
                    if len(choices) != 2:
                        continue
                    o1 = self._fractional_to_decimal(
                        (choices[0].get("fractionalValue") or "")
                    )
                    o2 = self._fractional_to_decimal(
                        (choices[1].get("fractionalValue") or "")
                    )
                    if o1 <= 1 or o2 <= 1:
                        continue
                    detail = self._event_detail(event_id, cache)
                    if detail is None:
                        continue
                    p1, p2, tournament, start_epoch, _ = detail
                    out.append(
                        MatchOdds(
                            source=self.NAME,
                            player1=p1,
                            player2=p2,
                            tournament=tournament,
                            commence_time=self._epoch_to_iso(start_epoch),
                            is_live=bool(market.get("isLive")),
                            odds_p1=o1,
                            odds_p2=o2,
                            bookmaker="bet365 (via sofascore)",
                        )
                    )
        except Exception as e:
            logger.warning("SofaScore adapter error: %s", e)

        try:
            live_url = f"{self.BASE_URL}/sport/tennis/events/live"
            cached_live = cache.get(self.NAME, live_url)
            if cached_live is None:
                data = self._get(live_url)
                cached_live = data or {}
                cache.set(self.NAME, live_url, cached_live)
            if isinstance(cached_live, dict):
                for ev in cached_live.get("events", []):
                    p1 = (ev.get("homeTeam") or {}).get("name", "")
                    p2 = (ev.get("awayTeam") or {}).get("name", "")
                    tournament = self._tournament_label(ev.get("tournament") or {})
                    if not p1 or not p2:
                        continue
                    detail_id = ev.get("id")
                    detail = self._event_detail(detail_id, cache) if detail_id else None
                    o1 = o2 = 0.0
                    if detail is not None:
                        _, _, _, _, (o1, o2) = detail
                    out.append(
                        MatchOdds(
                            source=self.NAME,
                            player1=p1,
                            player2=p2,
                            tournament=tournament,
                            commence_time=self._epoch_to_iso(ev.get("startTimestamp")),
                            is_live=True,
                            odds_p1=o1,
                            odds_p2=o2,
                            bookmaker="bet365 (via sofascore)",
                        )
                    )
        except Exception as e:
            logger.warning("SofaScore live adapter error: %s", e)
        return out

    def _event_detail(
        self, event_id: object, cache: TtlCache
    ) -> tuple[str, str, str, int, tuple[float, float]] | None:
        """Fetch /event/{id} -> (p1, p2, tournament, start_epoch, (o1, o2)).

        Returns None if the event cannot be resolved. Live odds for live
        events are pulled from the event's odds/1/all endpoint.
        """
        if event_id is None:
            return None
        url = f"{self.BASE_URL}/event/{event_id}"
        cached = cache.get(self.NAME, url)
        if cached is None:
            data = self._get(url)
            cached = data if isinstance(data, dict) else {}
            cache.set(self.NAME, url, cached)
        ev = cached.get("event") or cached
        p1 = (ev.get("homeTeam") or {}).get("name", "")
        p2 = (ev.get("awayTeam") or {}).get("name", "")
        tournament = self._tournament_label(ev.get("tournament") or {})
        start_epoch = ev.get("startTimestamp") or 0
        if not p1 or not p2:
            return None

        o1 = o2 = 0.0
        odds_url = f"{self.BASE_URL}/event/{event_id}/odds/1/all"
        cached_odds = cache.get(self.NAME, odds_url)
        if cached_odds is None:
            data = self._get(odds_url)
            cached_odds = data if isinstance(data, dict) else {}
            cache.set(self.NAME, odds_url, cached_odds)
        if isinstance(cached_odds, dict):
            for m in cached_odds.get("markets", []):
                name = m.get("marketName") or m.get("name") or ""
                if "full time" in name.lower() or not name:
                    choices = m.get("choices", [])
                    if len(choices) >= 2:
                        c1 = self._fractional_to_decimal(
                            (choices[0].get("fractionalValue") or "")
                        )
                        c2 = self._fractional_to_decimal(
                            (choices[1].get("fractionalValue") or "")
                        )
                        if c1 > 1 and c2 > 1:
                            o1, o2 = c1, c2
                    break
        return p1, p2, tournament, start_epoch, (o1, o2)

    @staticmethod
    def _epoch_to_iso(epoch: object) -> str:
        try:
            dt = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
            return dt.isoformat()
        except (ValueError, TypeError, OSError):
            return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _tournament_label(tournament: dict) -> str:
        """'ATP Montreal', 'WTA Toronto', 'Hamburg, Germany' (Challenger)."""
        name = tournament.get("name", "")
        category = (
            (tournament.get("category") or {}).get("name", "") or ""
        )
        if category in ("ATP", "WTA"):
            return f"{category} {name}"
        return name or category or "Tennis"
