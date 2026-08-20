"""OddsPortal (centroquote.it) HTTP fetch + event/market parsing.

The tennis home page embeds up to ~100 events (scheduled AND finished) in
the RSC payload under ``initialRows``, with the page-level ``xHash``. Each
event's odds come from the encrypted backend feed::

    https://backend.oddsportal.com/match-event/1-2-{encodeEventId}-{bt}-{sc}-{xhash}.dat?geo=it&lang=it

``d.oddsdata.back`` is keyed by market ``E-{bt}-{sc}-{handicapTypeId}-{handicapValue}-{mixedParamId}``.
For tennis match winner: bt=3, sc=2 (Full Time), market ``E-3-2-0-0-0``
with per-bookmaker ``odds`` (current) and ``openingOdd`` (open price).
"""
from __future__ import annotations

import json
import re
import time
import urllib.request

from logging_config import get_logger
from features.oddsportal_crypto import decrypt_payload

logger = get_logger(__name__)

_HOME_URL = "https://www.centroquote.it/it/tennis/"
_BACKEND = "https://backend.oddsportal.com"
_PROXY = "https://www.centroquote.it/proxy"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Betting type / scope ids for tennis (from ajax-event-page-metadata)
BETTING_TYPE_MATCH_WINNER = 3  # Home/Away
SCOPE_FULL_TIME = 2
VERSION_ID = 1
SPORT_ID_TENNIS = 2


def _fetch(url: str, tries: int = 4, timeout: int = 20, referer: str | None = None) -> bytes:
    last = None
    for attempt in range(tries):
        try:
            headers = {"User-Agent": _USER_AGENT, "Accept": "*/*"}
            if referer:
                headers["Referer"] = referer
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"fetch failed after {tries} tries: {url}: {last}")


def fetch_tennis_events(
    home_url: str | None = None,
    statuses: set[int] | None = None,
) -> tuple[list[dict], str | None]:
    """Fetch the tennis home page and return (initialRows events, page xHash).

    ``statuses`` filters the returned events (1=scheduled, 3=finished).
    """
    url = home_url or _HOME_URL
    raw = _fetch(url, referer=url).decode("utf-8", errors="ignore")
    events, xhash = parse_tennis_home(raw)
    if statuses is not None:
        events = [e for e in events if e.get("status-id") in statuses]
    return events, xhash


def parse_tennis_home(html: str) -> tuple[list[dict], str | None]:
    """Parse the RSC payload of the tennis home page.

    The ``initialRows`` array lives inside a ``self.__next_f.push([1,"..."])``
    call with double-escaped JSON.
    """
    idx = html.find("initialRows")
    if idx < 0:
        return [], None
    start = html.rfind("self.__next_f.push", 0, idx)
    if start < 0:
        return [], None
    end_marker = '"])'
    end = html.find(end_marker, idx)
    if end < 0:
        return [], None
    push_text = html[start:end + len(end_marker) + 1].strip()
    if not push_text.startswith("self.__next_f.push("):
        return [], None
    inner = push_text[len("self.__next_f.push("):]
    inner = inner[: inner.rfind(")")]
    try:
        arr = json.loads(inner)
    except json.JSONDecodeError:
        return [], None
    payload = arr[1] if isinstance(arr, list) and len(arr) > 1 else ""
    rows = _extract_json_array(payload, '"initialRows":')
    if rows is None:
        return [], None
    xhash = None
    xm = re.search(r'"xHash":"([^"]+)"', payload)
    if xm:
        xhash = xm.group(1)
    return rows, xhash


def _extract_json_array(text: str, key: str) -> list[dict] | None:
    """Return the JSON array that follows ``key`` in ``text`` (bracket aware)."""
    i = text.find(key)
    if i < 0:
        return None
    sub = text[i + len(key):]
    depth = 0
    in_str = False
    esc = False
    end = None
    for k, ch in enumerate(sub):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = k
                break
    if end is None:
        return None
    try:
        return json.loads(sub[: end + 1])
    except json.JSONDecodeError:
        return None


def fetch_match_event(
    encode_event_id: str,
    xhash: str,
    betting_type: int = BETTING_TYPE_MATCH_WINNER,
    scope: int = SCOPE_FULL_TIME,
    use_backend: bool = True,
) -> dict:
    """Fetch + decrypt one match-event payload (live odds for one match)."""
    prefix = _BACKEND if use_backend else _PROXY
    url = (
        f"{prefix}/match-event/{VERSION_ID}-{SPORT_ID_TENNIS}-{encode_event_id}"
        f"-{betting_type}-{scope}-{xhash}.dat?geo=it&lang=it"
    )
    resp = _fetch(url, referer=_HOME_URL)
    return decrypt_payload(resp)


def extract_market_odds(payload: dict, betting_type: int = BETTING_TYPE_MATCH_WINNER,
                        scope: int = SCOPE_FULL_TIME) -> dict:
    """Extract the match-winner market into {bookie_id: {home, away, opening_home, opening_away}}.

    Returns an empty dict when the market has no bookmakers with odds.
    """
    back = (payload.get("d", {}).get("oddsdata", {}) or {}).get("back", {})
    if not isinstance(back, dict):
        return {}
    market = back.get(f"E-{betting_type}-{scope}-0-0-0")
    if not market or not isinstance(market, dict):
        return {}
    odds = market.get("odds", {}) or {}
    opening = market.get("openingOdd", {}) or {}
    out: dict[int, dict] = {}
    for bid, vals in odds.items():
        if not isinstance(vals, list) or len(vals) < 2:
            continue
        try:
            bid_i = int(bid)
            h, a = float(vals[0]), float(vals[1])
        except (TypeError, ValueError):
            continue
        if h <= 1.0 or a <= 1.0:
            continue
        open_vals = opening.get(bid, [])
        try:
            oh = float(open_vals[0]) if isinstance(open_vals, list) and open_vals else float("nan")
            oa = float(open_vals[1]) if isinstance(open_vals, list) and len(open_vals) > 1 else float("nan")
        except (TypeError, ValueError, IndexError):
            oh = oa = float("nan")
        out[bid_i] = {
            "home": h, "away": a,
            "opening_home": oh, "opening_away": oa,
        }
    return out
