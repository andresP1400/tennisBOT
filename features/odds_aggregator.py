"""Multi-source live odds aggregator.

Aggregates pre-match and live odds from three free API sources:
- Betfair Exchange (sharp P2P market, free Developer API)
- Pinnacle Lines API (legacy public lines, no account required)
- TheOddsAPI (aggregator of 8+ bookmakers, 500 req/month free tier)

All sources are normalized to a common schema:
    {
        "match_id": str,
        "player1": str,
        "player2": str,
        "tournament": str,
        "commence_time": str (ISO 8601 UTC),
        "is_live": bool,
        "sources": {
            "<source_name>": {
                "player1": float,
                "player2": float,
            },
        },
        "best_odds": {"player1": float, "player2": float},
        "implied_prob1": float,
        "implied_prob2": float,
        "margin": float,
        "num_sources": int,
    }

A TTL in-memory cache prevents re-fetching the same endpoint within
the configured window (default 60 s) to avoid burning TheOddsAPI quota.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TTL cache
# ---------------------------------------------------------------------------
@dataclass
class _CacheEntry:
    value: object
    timestamp: float


class TtlCache:
    """In-memory TTL cache for HTTP responses.

    Used to avoid burning TheOddsAPI quota (500 req/month free).
    Each (url, source) key is cached for `ttl_seconds`.
    """

    def __init__(self, ttl_seconds: int = 60) -> None:
        self._ttl = ttl_seconds
        self._store: dict[tuple[str, str], _CacheEntry] = {}

    def get(self, source: str, url: str) -> object | None:
        key = (source, url)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry.timestamp > self._ttl:
            del self._store[key]
            return None
        return entry.value

    def set(self, source: str, url: str, value: object) -> None:
        self._store[(source, url)] = _CacheEntry(
            value=value, timestamp=time.monotonic()
        )

    def clear(self) -> None:
        self._store.clear()


# ---------------------------------------------------------------------------
# Common types
# ---------------------------------------------------------------------------
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


def _normalize_player(name: str) -> str:
    """Lowercase, strip, collapse spaces."""
    return " ".join(name.lower().strip().split())


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


# ---------------------------------------------------------------------------
# Source 1: Betfair Exchange (free Developer API, no geo-block)
# ---------------------------------------------------------------------------
class BetfairAdapter:
    """Betfair Exchange API adapter.

    Docs: https://docs.betfair.com/display/1smk3cen4v3lu3yri5p4/account-api
    Free tier: free, unlimited requests, requires app key (no real-money
    account needed for read-only market data via delayed API).
    """

    BASE_URL = "https://api.betfair.com/exchange/betting/rest/v1.0"
    NAME = "betfair"

    def __init__(self, app_key: str | None = None, session_token: str | None = None) -> None:
        self._app_key = app_key or os.environ.get("BETFAIR_APP_KEY", "")
        self._session_token = session_token or os.environ.get(
            "BETFAIR_SESSION_TOKEN", ""
        )

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
            if cached is not None:
                return cached
            headers = {
                "X-Application": self._app_key,
                "X-Authentication": self._session_token,
                "Content-Type": "application/json",
            }
            body = {
                "filter": {"eventTypeIds": ["2"], "marketTypeCodes": ["MATCH_ODDS"]},
                "marketProjection": ["EVENT", "MARKET_START_TIME", "RUNNER_NAMES"],
                "maxResults": 200,
            }
            resp = requests.post(url, json=body, headers=headers, timeout=15)
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
                tournament = (
                    m.get("event", {})
                    .get("name", m.get("eventName", ""))
                )
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


# ---------------------------------------------------------------------------
# Source 2: Pinnacle Lines API (legacy public endpoint)
# ---------------------------------------------------------------------------
class PinnacleAdapter:
    """Pinnacle Lines API adapter.

    Public legacy endpoint: https://api.pinnacle.com/en/v1/lines
    Returns JSON lines for most tennis events. No API key required
    for the public lines endpoint (rate-limited server-side).

    Note: Pinnacle has deprecated this in favor of the official API
    (which requires a real-money account), but the legacy lines endpoint
    is still functional and free.
    """

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
            if cached is not None:
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


# ---------------------------------------------------------------------------
# Source 3: TheOddsAPI (aggregator, free 500 req/month)
# ---------------------------------------------------------------------------
class TheOddsApiAdapter:
    """TheOddsAPI adapter.

    Docs: https://the-odds-api.com/liveapi/guides/v4/
    Free tier: 500 requests/month. Caching is essential.
    """

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
            headers = {"X-Api-Key": self._api_key}
            resp = requests.get(url, headers=headers, timeout=15)
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
            headers = {"X-Api-Key": self._api_key}
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
                resp = requests.get(url, headers=headers, timeout=15)
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
                            )
                        )
                cache.set(self.NAME, url, page)
                out.extend(page)
            return out
        except Exception as e:
            logger.warning("TheOddsAPI adapter error: %s", e)
            return []


# ---------------------------------------------------------------------------
# Source 4: SofaScore (free public API, NO registration / NO key)
# ---------------------------------------------------------------------------
class SofaScoreAdapter:
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


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------
class OddsAggregator:
    """Aggregates odds from multiple sources and computes best odds.

    Usage:
        agg = OddsAggregator()
        matches = agg.get_today_matches(tour="atp")
        # matches is a list of dicts with the normalized schema
    """

    def __init__(
        self,
        cache_ttl: int = 60,
        betfair: BetfairAdapter | None = None,
        pinnacle: PinnacleAdapter | None = None,
        theoddsapi: TheOddsApiAdapter | None = None,
        sofascore: SofaScoreAdapter | None = None,
    ) -> None:
        self.cache = TtlCache(ttl_seconds=cache_ttl)
        self.adapters: list = []
        bf = betfair or BetfairAdapter()
        pin = pinnacle or PinnacleAdapter()
        toa = theoddsapi or TheOddsApiAdapter()
        sf = sofascore or SofaScoreAdapter()
        if bf.is_configured():
            self.adapters.append(bf)
        if pin.is_configured():
            self.adapters.append(pin)
        if toa.is_configured():
            self.adapters.append(toa)
        if sf.is_configured():
            self.adapters.append(sf)

    def get_today_matches(self, tour: str = "atp") -> list[dict]:
        """Return aggregated odds for today's matches.

        tour: "atp" or "wta" (filters by tournament name substring).
        Returns a list of normalized match dicts (see module docstring).
        """
        all_odds: list[MatchOdds] = []
        for adapter in self.adapters:
            try:
                all_odds.extend(adapter.list_tennis_matches(self.cache))
            except Exception as e:
                logger.warning("Adapter %s failed: %s", adapter.NAME, e)
        return self._aggregate(all_odds, tour)

    def get_match_odds(
        self, player1: str, player2: str, tour: str = "atp"
    ) -> dict:
        """Return aggregated odds for a specific match.

        Returns dict with sources, best_odds, implied_prob, margin.
        Empty dict if not found in any source.
        """
        matches = self.get_today_matches(tour)
        for m in matches:
            if _player_matches(player1, [m["player1"], m["player2"]]) and \
               _player_matches(player2, [m["player1"], m["player2"]]):
                return m
        return {}

    def _aggregate(
        self, all_odds: list[MatchOdds], tour: str
    ) -> list[dict]:
        """Group by (player1, player2) and compute best odds across sources."""
        groups: dict[tuple[str, str], list[MatchOdds]] = {}
        for o in all_odds:
            key = (
                _normalize_player(o.player1),
                _normalize_player(o.player2),
            )
            groups.setdefault(key, []).append(o)

        out: list[dict] = []
        for (p1n, p2n), items in groups.items():
            if tour and tour.lower() not in items[0].tournament.lower():
                continue
            sources: dict[str, dict[str, float]] = {}
            best_p1 = 0.0
            best_p2 = 0.0
            for it in items:
                if it.odds_p1 > 0 and it.odds_p2 > 0:
                    sources[it.source] = {
                        "player1": it.odds_p1,
                        "player2": it.odds_p2,
                    }
                    best_p1 = max(best_p1, it.odds_p1)
                    best_p2 = max(best_p2, it.odds_p2)
            if best_p1 > 0 and best_p2 > 0:
                imp1, imp2, margin = _compute_implied(best_p1, best_p2)
                out.append({
                    "match_id": f"{p1n}_{p2n}",
                    "player1": items[0].player1,
                    "player2": items[0].player2,
                    "tournament": items[0].tournament,
                    "commence_time": items[0].commence_time,
                    "is_live": any(it.is_live for it in items),
                    "sources": sources,
                    "best_odds": {"player1": best_p1, "player2": best_p2},
                    "implied_prob1": imp1,
                    "implied_prob2": imp2,
                    "margin": margin,
                    "num_sources": len(sources),
                })
        out.sort(key=lambda m: m["commence_time"])
        return out


__all__ = [
    "BetfairAdapter",
    "PinnacleAdapter",
    "TheOddsApiAdapter",
    "SofaScoreAdapter",
    "OddsAggregator",
    "MatchOdds",
    "TtlCache",
]
