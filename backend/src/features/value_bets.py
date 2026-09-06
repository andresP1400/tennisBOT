"""Value-bet computation against live market odds.

Computes value bets by comparing the model probability to the best live
market implied probability (from LiveOddsScraper.get_match_odds). Kept
out of features/live_odds.py to respect the 300-line module budget.
"""

from __future__ import annotations

import math
from typing import Any

from config import settings


def compute_value_bets(
    model_prob1: float,
    player1: str,
    player2: str,
    surface: str | None = None,
    min_edge: float = 0.05,
) -> dict[str, Any]:
    """Compute value bets by comparing model probability to market odds.

    A value bet exists when model_prob > market_implied_prob + min_edge.
    """
    from features.live_odds import LiveOddsScraper

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
        odds_api_key = settings.odds_api_key.strip()
        key_missing = not bool(odds_api_key) or odds_api_key == "your_api_key_here"
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
        value_bets.append(
            {
                "side": player1,
                "model_prob": model_prob1,
                "market_prob": market_prob1,
                "edge": edge1,
                "best_odds": best_p1,
                "bookmaker_count": len(odds.get("sources", {})),
            }
        )
    if edge2 >= min_edge:
        value_bets.append(
            {
                "side": player2,
                "model_prob": 1.0 - model_prob1,
                "market_prob": market_prob2,
                "edge": edge2,
                "best_odds": best_p2,
                "bookmaker_count": len(odds.get("sources", {})),
            }
        )
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
