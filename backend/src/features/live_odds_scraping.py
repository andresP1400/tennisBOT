"""Disabled live-odds scraping fallbacks (dev/debug only).

These paths are geo-blocked from Italy and unreliable in production, so
LiveOddsScraper only invokes them when enable_scraping=True. Kept as
pure functions so the main module stays under the line budget.
"""

from __future__ import annotations

import re
import time
from typing import Any

from logging_config import get_logger

logger = get_logger(__name__)


def scrape_oddsportal(
    fetcher: Any, use_stealth: bool, player1: str, player2: str
) -> dict[str, Any]:
    """Scrape today's tennis odds from OddsPortal.

    Disabled by default. Enable with `enable_scraping=True`.
    """
    from features.live_odds_util import _normalize_player_name

    p1_key = _normalize_player_name(player1)
    p2_key = _normalize_player_name(player2)
    all_odds: dict[str, Any] = {}
    urls = [
        "https://www.oddsportal.com/tennis/atp/",
        "https://www.oddsportal.com/tennis/wta/",
    ]
    for url in urls:
        try:
            page = fetcher.fetch(url) if use_stealth else fetcher.get(url)
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


def scrape_pinnacle(player1: str, player2: str) -> dict[str, Any]:
    """DISABLED: Pinnacle geo-blocks Italy. Use TheOddsAPI instead."""
    return {}


def scrape_tennis_explorer(player1: str, player2: str) -> dict[str, Any]:
    """DISABLED: Tennis Explorer scraper no longer matches the live DOM."""
    return {}
