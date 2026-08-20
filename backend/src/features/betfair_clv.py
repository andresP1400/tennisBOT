"""Betfair exchange CLV (closing line value) logic.

The direct Betfair UK endpoints (www.betfair.com, facet search, market
graphs) are geo-blocked from Italian IPs — the site redirects to
betfair.it (sportsbook only) and the exchange marketIds are not
reachable. However, the Betfair Exchange book feed IS accessible through
TheOddsAPI (free tier, 500 req/month) as the ``betfair_ex_eu`` bookmaker,
which shares the same exchange liquidity as the UK market for tennis.

This module snapshots the exchange back/lay prices (plus Matchbook — a
second exchange — and Pinnacle as sportsbook reference) for every tennis
match, appends them to a rolling JSONL archive, and computes CLV:

  CLV(side) = closing_price / taken_price - 1

where the closing price is the last exchange back price observed before
the match starts. Positive CLV means the line moved against the bettor
(worse than closing) — the standard predictor-of-profitability metric.

Design notes:

  * A single TheOddsAPI call returns ALL events of a tournament with all
    requested bookmakers, so one snapshot costs ~1-2 requests total
    (one per active tennis tournament). Default snapshot cadence is
    6 hours (≈120 req/month) to stay inside the free tier.
  * The API key goes in the query string (``?apiKey=``) — the
    ``X-Api-Key`` header is currently rejected by the API with 401.
  * Only matches whose ``commence_time`` is in the future are stored,
    so the archive doubles as a free pre-match odds history.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

from logging_config import get_logger

logger = get_logger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

_BASE_URL = "https://api.the-odds-api.com/v4"
_EXCHANGE_BOOKMAKERS = ["betfair_ex_eu", "matchbook", "pinnacle"]
# Anchored to the repo-root data dir (config.RAW_DIR), not CWD-relative.
_ARCHIVE_DIR = os.path.join(str(config.RAW_DIR), "betfair_exchange")
_MAX_EVENTS_PER_DAY = 2000


def api_key() -> str:
    from dotenv import load_dotenv
    # backend/src/features/ -> two levels up is backend/src; .env files
    # live at the repository root (one more level up).
    _SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _PROJECT_ROOT = os.path.dirname(_SRC_ROOT)
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))
    load_dotenv(os.path.join(_PROJECT_ROOT, "local.env"), override=True)
    return os.environ.get("ODDS_API_KEY", "").strip()


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def list_tennis_sport_keys() -> list[str]:
    """Active tennis tournament keys from TheOddsAPI."""
    key = api_key()
    if not key:
        logger.warning("ODDS_API_KEY not set")
        return []
    import requests
    try:
        resp = requests.get(
            f"{_BASE_URL}/sports/",
            params={"apiKey": key},
            timeout=20,
        )
        if resp.status_code != 200:
            logger.warning("sports list failed: %s", resp.status_code)
            return []
        return [
            s["key"]
            for s in resp.json()
            if s.get("key", "").startswith("tennis_")
        ]
    except Exception as e:
        logger.warning("sports list error: %s", e)
        return []


def fetch_exchange_snapshot(sport_keys: list[str] | None = None) -> list[dict]:
    """Fetch exchange odds for all active tennis tournaments.

    Returns one dict per event::

        {"sport": str, "match_id": str, "home": str, "away": str,
         "commence_time": str, "taken_at": str,
         "bookmakers": {"betfair_ex_eu": {"back_home": .., "lay_home": ..,
                                           "back_away": .., "lay_away": ..},
                        "matchbook": {...}, "pinnacle": {...}}}
    """
    key = api_key()
    if not key:
        return []
    sports = sport_keys if sport_keys is not None else list_tennis_sport_keys()
    out: list[dict] = []
    import requests
    for sport in sports:
        try:
            resp = requests.get(
                f"{_BASE_URL}/sports/{sport}/odds/",
                params={
                    "apiKey": key,
                    "regions": "eu",
                    "markets": "h2h,h2h_lay",
                    "oddsFormat": "decimal",
                    "bookmakers": ",".join(_EXCHANGE_BOOKMAKERS),
                },
                timeout=25,
            )
            if resp.status_code != 200:
                logger.warning("%s odds failed: %s", sport, resp.status_code)
                continue
            taken = datetime.now(timezone.utc).isoformat()
            for ev in resp.json():
                if not isinstance(ev, dict):
                    continue
                bms: dict = {}
                for bm in ev.get("bookmakers", []):
                    bk = bm.get("key", "")
                    entry: dict = {}
                    for m in bm.get("markets", []):
                        outcomes = {o.get("name", ""): o.get("price") for o in m.get("outcomes", [])}
                        names = list(outcomes)
                        if len(names) < 2:
                            continue
                        side_h, side_a = names[0], names[1]
                        if m.get("key") == "h2h":
                            entry["back_home"] = outcomes[side_h]
                            entry["back_away"] = outcomes[side_a]
                        elif m.get("key") == "h2h_lay":
                            entry["lay_home"] = outcomes[side_h]
                            entry["lay_away"] = outcomes[side_a]
                    if entry:
                        bms[bk] = entry
                if not bms:
                    continue
                out.append({
                    "sport": sport,
                    "match_id": ev.get("id", ""),
                    "home": ev.get("home_team", ""),
                    "away": ev.get("away_team", ""),
                    "commence_time": ev.get("commence_time", ""),
                    "taken_at": taken,
                    "bookmakers": bms,
                })
            time.sleep(0.4)
        except Exception as e:
            logger.warning("%s fetch error: %s", sport, e)
    return out


def append_snapshot(events: list[dict], archive_dir: str | None = None) -> str:
    """Append events to the daily JSONL archive. Returns the file path."""
    d = archive_dir or _ARCHIVE_DIR
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"snapshots_{_today_str()}.jsonl")
    count = 0
    with open(path, "a", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
            count += 1
    logger.info("appended %d snapshots to %s", count, path)
    return path


def load_snapshots(days: int = 14, archive_dir: str | None = None) -> list[dict]:
    """Load snapshots from the last N days (JSONL)."""
    d = archive_dir or _ARCHIVE_DIR
    if not os.path.isdir(d):
        return []
    import datetime as dt
    out: list[dict] = []
    cutoff = datetime.now(timezone.utc) - dt.timedelta(days=days)
    for fn in sorted(os.listdir(d)):
        if not fn.startswith("snapshots_"):
            continue
        day = fn.replace("snapshots_", "").replace(".jsonl", "")
        try:
            if datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc) < cutoff:
                continue
        except ValueError:
            continue
        with open(os.path.join(d, fn), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return out


def _match_key(ev: dict) -> str:
    return f"{ev.get('home', '')}|{ev.get('away', '')}|{ev.get('commence_time', '')}"


def closing_odds(events: list[dict]) -> dict:
    """Last exchange back price per match before its start time.

    Returns {match_key: {"home": price, "away": price}} using the
    betfair_ex_eu back prices (fallback matchbook, then pinnacle).
    """
    by_match: dict[str, list[dict]] = {}
    for ev in events:
        by_match.setdefault(_match_key(ev), []).append(ev)
    closing: dict = {}
    now = datetime.now(timezone.utc)
    for key, snaps in by_match.items():
        snaps_sorted = sorted(
            snaps,
            key=lambda e: e.get("taken_at", ""),
        )
        latest = snaps_sorted[-1]
        try:
            start = datetime.fromisoformat(
                latest["commence_time"].replace("Z", "+00:00")
            )
        except (ValueError, KeyError):
            continue
        taken = datetime.fromisoformat(latest["taken_at"].replace("Z", "+00:00"))
        if taken > now or taken >= start:
            continue
        home = away = None
        for bm_key in ("betfair_ex_eu", "matchbook", "pinnacle"):
            bm = latest.get("bookmakers", {}).get(bm_key)
            if not bm:
                continue
            if "back_home" in bm and "back_away" in bm:
                home = bm["back_home"]
                away = bm["back_away"]
                break
        if home and away:
            closing[key] = {"home": float(home), "away": float(away)}
    return closing


def compute_clv(closing: dict, taken_price: float, side: str = "home") -> dict:
    """CLV for a bet taken at ``taken_price`` vs the closing line.

    CLV = closing_price / taken_price - 1 (positive = we beat the market).
    """
    return {
        "clv": closing[side] / taken_price - 1 if side in closing else None,
        "closing_price": closing.get(side),
        "taken_price": taken_price,
    }


def build_clv_report(events: list[dict], days: int = 14) -> dict:
    """Summary of exchange coverage for the last N days."""
    closing = closing_odds(events)
    by_sport: dict[str, int] = {}
    for ev in events:
        by_sport[ev.get("sport", "?")] = by_sport.get(ev.get("sport", "?"), 0) + 1
    return {
        "snapshots": len(events),
        "sport_coverage": by_sport,
        "matches_with_closing": len(closing),
        "sample": list(closing.items())[:5],
    }
