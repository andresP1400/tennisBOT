"""Player roster and today's-matches routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from api.predict_core import sanitize_nan
from api.state import load_state

router = APIRouter()


@router.get("/api/players")
def list_players(q: str = "", limit: int = 100, tour: str = "atp") -> dict[str, Any]:
    if tour not in ("atp", "wta"):
        raise HTTPException(status_code=400, detail="Invalid tour")
    state = load_state(tour)
    if state is None:
        return {"players": [], "total": 0}
    names = [
        row.get("name")
        for row in state.get("players", {}).values()
        if isinstance(row.get("name"), str)
    ]
    ql = q.strip().lower()
    if ql:
        names = [n for n in names if ql in n.lower()]
    names = sorted(set(names))
    # No hard product cap — return up to what the client asked (min 1)
    cap = max(1, limit) if limit > 0 else len(names)
    return {"players": names[:cap], "total": len(names)}


@router.get("/api/todays-matches")
def get_todays_matches(tour: str = "atp") -> dict[str, Any]:
    """Return today's matches, cached with stale-while-revalidate.

    Fetching from SofaScore/TheOddsAPI can take 30-60s, which blows past
    the Next.js proxy timeout (~30s). A background thread re-fetches in
    the background so callers always get a fast cached response.
    """
    from features.live_odds import LiveOddsScraper

    scraper = LiveOddsScraper()
    result = scraper.get_todays_matches_cached(tour)
    return sanitize_nan({"tour": tour, "count": len(result), "matches": result})  # type: ignore[no-any-return]
