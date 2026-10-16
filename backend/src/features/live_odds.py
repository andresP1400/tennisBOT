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

Module layout (each file under the 300-line budget):
  - features/live_odds_util.py       -> name normalization + shared caches
  - features/live_odds_scraping.py   -> disabled fallback scrapers
  - features/value_bets.py           -> compute_value_bets
  - features/live_odds_theoddsapi.py -> TheOddsApiMixin (API data sources)
  - features/live_odds_matches.py    -> TodaysMatchesMixin (aggregator list)
  - features/live_odds_match_odds.py -> MatchOddsMixin (get_match_odds)
  - this file                        -> LiveOddsScraper orchestrator

The TheOddsAPI methods are resolved by the regression test via
``live_odds.LiveOddsScraper`` (MRO attribute lookup), so the mixin
split preserves the public contract.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from logging_config import get_logger
from features.live_odds_matches import TodaysMatchesMixin
from features.live_odds_match_odds import MatchOddsMixin
from features.live_odds_scraping import (
    scrape_oddsportal,
    scrape_pinnacle,
    scrape_tennis_explorer,
)
from features.live_odds_theoddsapi import TheOddsApiMixin
from features.live_odds_util import (
    _normalize_player_name,
)  # noqa: F401  (public re-export)
from features.value_bets import compute_value_bets  # noqa: F401  (public re-export)

logger = get_logger(__name__)
# backend/src/features/ -> two levels up is backend/src (import root);
# .env files live at the repository root (one more level up).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import config  # noqa: E402

# .env / local.env are loaded centrally by config.Settings (Pydantic
# BaseSettings); no per-module load_dotenv duplication anymore.

__all__ = ["LiveOddsScraper", "compute_value_bets", "_normalize_player_name"]


class LiveOddsScraper(TheOddsApiMixin, TodaysMatchesMixin, MatchOddsMixin):
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
        self._fetcher: Any = None
        self._api_key = api_key or config.settings.odds_api_key
        self._available_sports: list[str] | None = None

    def _get_fetcher(self) -> Any | None:
        """Lazy-initialize the Scrapling fetcher (only when scraping is on)."""
        if not self.enable_scraping:
            return None
        if self._fetcher is not None:
            return self._fetcher
        try:
            from scrapling import Fetcher, StealthyFetcher

            self._fetcher = StealthyFetcher() if self.use_stealth else Fetcher()  # type: ignore[no-untyped-call]
            return self._fetcher
        except ImportError:
            return None

    def _get_api_key(self) -> str:
        """Get TheOddsAPI key from instance or environment."""
        return self._api_key or config.settings.odds_api_key

    # -----------------------------------------------------------------
    # DISABLED scraping paths (kept for dev/debug only)
    # -----------------------------------------------------------------
    def _scrape_oddsportal(self, player1: str, player2: str) -> dict[str, Any]:
        """Scrape today's tennis odds from OddsPortal.

        Disabled by default. Enable with `enable_scraping=True`.
        """
        if not self.enable_scraping:
            return {}
        fetcher = self._get_fetcher()
        if fetcher is None:
            return {}
        return scrape_oddsportal(fetcher, self.use_stealth, player1, player2)

    def _scrape_pinnacle(self, player1: str, player2: str) -> dict[str, Any]:
        """DISABLED: Pinnacle geo-blocks Italy. Use TheOddsAPI instead."""
        return scrape_pinnacle(player1, player2)

    def _scrape_tennis_explorer(self, player1: str, player2: str) -> dict[str, Any]:
        """DISABLED: Tennis Explorer scraper no longer matches the live DOM."""
        return scrape_tennis_explorer(player1, player2)
