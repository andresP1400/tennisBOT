"""Betfair exchange live volume exploitation (no login required).

Betfair's public chart endpoint serves price/volume history per runner
without any authentication::

    https://graphs.betfair.com/loadRunnerChart?marketId=1.XXXXXX&selectionId=NNN&handicap=0&alt=json

Response format::

    {"points": [[epoch_ms, price, amount], ...], "factor": n}

Each point is a bar of the runner's price chart: timestamp (ms), price and
traded volume at that price. Polling the endpoint lets us compute:

  * last traded price per runner
  * volume build-up per runner (relative share of the market)
  * volume velocity (delta between polls) — the classic exchange "steam" signal

Limitations (from this network):
  * www.betfair.com / facet search are geo-blocked (SSL interception) — the
    marketId must be provided (e.g. from the web UI or the Betfair API).
  * graphs.betfair.com works from most networks but can 403 without a valid
    marketId/selectionId.
  * From an Italian IP, www.betfair.com geo-redirects to www.betfair.it,
    which is sportsbook-only (no exchange). find_tennis_events() therefore
    resolves current events + runner selectionIds from betfair.it — the
    selectionIds are global PPB ids shared with the UK exchange, so the
    exchange marketId (1.xxxx) for the same match can be supplied manually
    or looked up from a non-Italian network.

The module never fails hard on a single poll: it returns the last good
snapshot plus error details, so callers can degrade gracefully.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from typing import Any

from logging_config import get_logger
from features.betfair_chart import get_runner_snapshot

logger = get_logger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_BFAIR_IT_TENNIS = "https://www.betfair.it/sport/tennis"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


# --------------------------------------------------------------------------- #
# Event resolution (betfair.it sportsbook — reachable from IT)
# --------------------------------------------------------------------------- #
def find_tennis_events(timeout: int = 30) -> list[dict[str, Any]]:
    """Scrape the current tennis events from www.betfair.it.

    Returns one dict per event::

        {"event_id": int, "home": str, "away": str,
         "selection_home": int, "selection_away": int,
         "sportsbook_market_id": "924.xxxxxx", "event_url": str}

    The selectionIds are the global PPB runner ids, shared with the UK
    exchange market of the same match — pair them with a manual
    ``market_id`` (1.xxxx) to poll exchange volume via loadRunnerChart.
    Player names are derived from the URL slug (first half of the player
    slug = home, second half = away); the numeric ids are always exact.
    """
    req = urllib.request.Request(
        _BFAIR_IT_TENNIS,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    # one block per event card; extract slug + market suffix + runner URNs
    for block in html.split('"typename":"EventMarketCard"'):
        url_m = re.search(r'"viewUrl":"(tennis/[^"]*?/e-(\d+))"', block)
        if not url_m:
            continue
        url, event_id = url_m.group(1), url_m.group(2)
        if event_id in seen:
            continue
        mk = re.search(r"ppb:sbkMarket:924\.(\d+)", block)
        rns = re.findall(r"ppb:sbkRunner:924\.\d+/(\d+)", block)
        if not mk or len(rns) < 2:
            continue
        seen.add(event_id)
        slug = url.split("/")[-2]
        tokens = slug.split("-")
        # slug = {home first+last}{-compound surname}-{away first+last}{-compound}
        # odd token count -> the home player has the compound surname first.
        half = len(tokens) // 2 + (len(tokens) % 2)
        home = " ".join(t.split(".")[0] for t in tokens[:half]).title()
        away = " ".join(t.split(".")[0] for t in tokens[half:]).title()
        events.append(
            {
                "event_id": int(event_id),
                "home": home,
                "away": away,
                "selection_home": int(rns[0]),
                "selection_away": int(rns[1]),
                "sportsbook_market_id": f"924.{mk.group(1)}",
                "event_url": url,
            }
        )
    return events


# --------------------------------------------------------------------------- #
# Match-level volume (both runners)
# --------------------------------------------------------------------------- #
def get_match_volume(
    market_id: str,
    selection_home: int,
    selection_away: int,
    handicap: float = 0.0,
    tries: int = 3,
) -> dict[str, Any]:
    """Snapshot the exchange volume for both runners of a match.

    Returns per-runner snapshots plus the home share of total volume and a
    naive steam flag (home or away volume accelerating vs. the other).
    """
    home = get_runner_snapshot(market_id, selection_home, handicap, tries=tries)
    away = get_runner_snapshot(market_id, selection_away, handicap, tries=tries)
    ok = home.get("ok") and away.get("ok")
    total = (home.get("total_volume", 0.0) or 0.0) + (
        away.get("total_volume", 0.0) or 0.0
    )
    home_share = None
    if ok and total > 0:
        home_share = round(home["total_volume"] / total, 4)
    return {
        "ok": ok,
        "market_id": market_id,
        "home_selection_id": selection_home,
        "away_selection_id": selection_away,
        "home": home,
        "away": away,
        "total_volume": round(total, 2) if ok else None,
        "home_volume_share": home_share,
        "timestamp": time.time(),
    }


def poll_volume(
    market_id: str,
    selection_home: int,
    selection_away: int,
    polls: int = 12,
    interval: float = 5.0,
    handicap: float = 0.0,
) -> list[dict[str, Any]]:
    """Poll match volume every ``interval`` seconds, ``polls`` times.

    Each snapshot includes per-runner volumes; the caller can compute volume
    velocity by differencing consecutive ``total_volume`` values.
    """
    out: list[dict[str, Any]] = []
    for i in range(polls):
        snap = get_match_volume(market_id, selection_home, selection_away, handicap)
        snap["poll"] = i + 1
        out.append(snap)
        logger.info(
            f"  poll {i + 1}/{polls}: home={snap['home'].get('total_volume')} "
            f"away={snap['away'].get('total_volume')} "
            f"share={snap.get('home_volume_share')}"
        )
        if i < polls - 1:
            time.sleep(interval)
    return out


def summarize_polls(polls: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute volume velocity + final state from a poll series."""
    vols = []
    for p in polls:
        if p.get("ok"):
            vols.append(
                (p["poll"], p["home"]["total_volume"], p["away"]["total_volume"])
            )
    if not vols:
        return {"ok": False, "reason": "no successful polls"}
    first = vols[0]
    last = vols[-1]
    delta_home = last[1] - first[1]
    delta_away = last[2] - first[2]
    return {
        "ok": True,
        "polls": len(vols),
        "home_volume_start": first[1],
        "home_volume_end": last[1],
        "away_volume_start": first[2],
        "away_volume_end": last[2],
        "home_volume_delta": round(delta_home, 2),
        "away_volume_delta": round(delta_away, 2),
        "steam": (
            "home"
            if delta_home > delta_away > 0
            else (
                "away"
                if delta_away > delta_home > 0
                else "flat" if delta_home == delta_away == 0 else "mixed"
            )
        ),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Betfair exchange live volume (no auth)"
    )
    parser.add_argument(
        "--market", required=False, help="Betfair marketId, e.g. 1.235476617"
    )
    parser.add_argument(
        "--home", type=int, required=False, help="home runner selectionId"
    )
    parser.add_argument(
        "--away", type=int, required=False, help="away runner selectionId"
    )
    parser.add_argument(
        "--find", action="store_true", help="list current tennis events from betfair.it"
    )
    parser.add_argument("--polls", type=int, default=12)
    parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()

    if args.find:
        evs = find_tennis_events()
        print(json.dumps(evs, indent=1))
        sys.exit(0)
    if not args.market or args.home is None or args.away is None:
        parser.error("--market/--home/--away required unless --find is used")

    polls = poll_volume(
        args.market, args.home, args.away, polls=args.polls, interval=args.interval
    )
    print(json.dumps(summarize_polls(polls), indent=2))
