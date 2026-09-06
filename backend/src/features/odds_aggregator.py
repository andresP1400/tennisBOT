"""Multi-source live odds aggregator.

Aggregates pre-match and live odds from four free API sources:
- Betfair Exchange (sharp P2P market, free Developer API)
- Pinnacle Lines API (legacy public lines, no account required)
- TheOddsAPI (aggregator of 8+ bookmakers, 500 req/month free tier)
- SofaScore (public API, no key, bet365 odds)

All sources are normalized to a common schema (see odds_common.py).

Module layout (each file under the 300-line budget):
  - odds_common.py     -> MatchOdds + matching/implied helpers
  - odds_cache.py      -> TtlCache (quota protection)
  - odds_betfair.py    -> BetfairAdapter
  - odds_pinnacle.py   -> PinnacleAdapter
  - odds_theoddsapi.py -> TheOddsApiAdapter
  - odds_sofascore.py  -> SofaScoreAdapter
  - this file          -> OddsAggregator + public re-exports

A TTL in-memory cache prevents re-fetching the same endpoint within
the configured window (default 60 s) to avoid burning TheOddsAPI quota.
"""

from __future__ import annotations

import logging
from typing import Any

from features.odds_betfair import BetfairAdapter
from features.odds_cache import TtlCache
from features.odds_common import (
    MatchOdds,
    _compute_implied,
    _normalize_player,
    _player_matches,
)
from features.odds_pinnacle import PinnacleAdapter
from features.odds_sofascore import SofaScoreAdapter
from features.odds_theoddsapi import TheOddsApiAdapter

logger = logging.getLogger(__name__)


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
        self.adapters: list[Any] = []
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

    def get_today_matches(self, tour: str = "atp") -> list[dict[str, Any]]:
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
    ) -> dict[str, Any]:
        """Return aggregated odds for a specific match.

        Returns dict with sources, best_odds, implied_prob, margin.
        Empty dict if not found in any source.
        """
        matches = self.get_today_matches(tour)
        for m in matches:
            if _player_matches(
                player1, [m["player1"], m["player2"]]
            ) and _player_matches(player2, [m["player1"], m["player2"]]):
                return m
        return {}

    def _aggregate(self, all_odds: list[MatchOdds], tour: str) -> list[dict[str, Any]]:
        """Group by (player1, player2) and compute best odds across sources."""
        groups: dict[tuple[str, str], list[MatchOdds]] = {}
        for o in all_odds:
            key = (
                _normalize_player(o.player1),
                _normalize_player(o.player2),
            )
            groups.setdefault(key, []).append(o)

        out: list[dict[str, Any]] = []
        for (p1n, p2n), items in groups.items():
            if tour:
                item_tours = {it.tour for it in items if it.tour}
                item_names = " ".join(it.tournament for it in items).lower()
                match_by_field = item_tours == {tour} or (
                    not item_tours and tour in item_names
                )
                if not match_by_field:
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
                out.append(
                    {
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
                    }
                )
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
    "_normalize_player",
]
