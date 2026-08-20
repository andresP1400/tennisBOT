"""Betfair public runner chart fetch + parse.

Betfair's public chart endpoint serves price/volume history per runner
without any authentication::

    https://graphs.betfair.com/loadRunnerChart?marketId=1.XXXXXX&selectionId=NNN&handicap=0&alt=json

Response format::

    {"points": [[epoch_ms, price, amount], ...], "factor": n}

Each point is a bar of the runner's price chart: timestamp (ms), price and
traded volume at that price.
"""
from __future__ import annotations

import json
import time
import urllib.request

_CHART_URL = "https://graphs.betfair.com/loadRunnerChart"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def fetch_runner_chart(
    market_id: str,
    selection_id: int,
    handicap: float = 0.0,
    timeout: int = 20,
) -> dict:
    """Fetch the raw runner chart JSON from graphs.betfair.com."""
    url = (
        f"{_CHART_URL}?marketId={market_id}&selectionId={selection_id}"
        f"&handicap={handicap}&alt=json"
    )
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_runner_chart(chart: dict) -> dict:
    """Parse a loadRunnerChart payload into a compact runner snapshot.

    Returns::

        {"ok": True, "points": N, "start_ts": ms, "end_ts": ms,
         "last_price": x, "first_price": x, "low": x, "high": x,
         "total_volume": sum(amounts), "peak_volume": max(amount),
         "factor": n}
    """
    points = chart.get("points") or []
    if not points:
        return {"ok": False, "points": 0, "reason": "empty chart (no points)"}
    ts = []
    prices = []
    amounts = []
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) < 3:
            continue
        try:
            ts.append(float(p[0]))
            prices.append(float(p[1]))
            amounts.append(float(p[2]))
        except (TypeError, ValueError):
            continue
    if not prices:
        return {"ok": False, "points": len(points), "reason": "no parseable points"}
    return {
        "ok": True,
        "points": len(prices),
        "start_ts": min(ts),
        "end_ts": max(ts),
        "last_price": prices[-1],
        "first_price": prices[0],
        "low": min(prices),
        "high": max(prices),
        "total_volume": round(sum(amounts), 2),
        "peak_volume": max(amounts),
        "factor": chart.get("factor", 1),
    }


def get_runner_snapshot(
    market_id: str,
    selection_id: int,
    handicap: float = 0.0,
    tries: int = 3,
    timeout: int = 20,
) -> dict:
    """Fetch + parse one runner snapshot with retries."""
    last = None
    for attempt in range(tries):
        try:
            chart = fetch_runner_chart(market_id, selection_id, handicap, timeout)
            return parse_runner_chart(chart)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    return {"ok": False, "points": 0, "reason": f"fetch failed: {last}"}
