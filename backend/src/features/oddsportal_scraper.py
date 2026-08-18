"""OddsPortal (centroquote.it) odds scraper via the encrypted match-event feed.

Reverse-engineered from the OddsPortal/centroquote Next.js front-end:

* The tennis home page embeds up to ~100 events (scheduled AND finished) in
  the RSC payload under ``initialRows``, with the page-level ``xHash``.
* Each event's odds come from the encrypted backend feed::

      https://backend.oddsportal.com/match-event/1-2-{encodeEventId}-{bt}-{sc}-{xhash}.dat?geo=it&lang=it

* The payload decrypts as: outer base64 -> split(':', 1) -> AES-CBC(PKCS7)
  with PBKDF2-HMAC-SHA256(1000 iters, fixed salt) -> gzip -> JSON.
* ``d.oddsdata.back`` is keyed by market ``E-{bt}-{sc}-{handicapTypeId}-{handicapValue}-{mixedParamId}``.
  For tennis match winner: bt=3, sc=2 (Full Time), market ``E-3-2-0-0-0``
  with per-bookmaker ``odds`` (current) and ``openingOdd`` (open price).

This gives free opening + current odds for ~12 bookmakers on every listed
tennis event, including already-finished matches — enough to build a CLV
dataset and live value detection without paid APIs.
"""
from __future__ import annotations

import base64
import datetime as _dt
import gzip
import json
import os
import re
import sys
import time
import urllib.request

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from logging_config import get_logger
logger = get_logger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# --------------------------------------------------------------------------- #
# OddsPortal crypto (fixed site-wide keys, embedded in the front-end bundle)
# --------------------------------------------------------------------------- #
_PASS_B64 = "Sio4c1EhcCQ3YURfZlIyeVdAZ0huKjNiVnAjc0FkTGRfaw=="
_SALT_B64 = "NWI5YThmMmMzZTZkMWE0YjdjOGU5ZDBmMWEyYjNjNGQ="

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

# Known bookmaker ids (decoded from the providers bonus-data endpoint).
# The full map is served dynamically by /ajax-providers-bonus-data/0/ and
# cached to data/raw/{tour}/odds_portal/providers.json when scraping.
BOOKMAKER_IDS: dict[int, str] = {
    27: "888sport",
    53: "bwin.it",
    159: "Sisal",
    188: "GoldBet",
    199: "SNAI",
    322: "Eurobet.it",
    335: "Lottomatica",
    372: "WilliamHill.it",
    419: "bet365.it",
    467: "Planetwin365",
    773: "BetssonIT",
    823: "BetflagIT",
    897: "Netwin",
}
UNKNOWN_BOOKIE_IDS: set[int] = set()


# --------------------------------------------------------------------------- #
# Decryption
# --------------------------------------------------------------------------- #
def decrypt_payload(raw: bytes | str) -> dict:
    """Decrypt an OddsPortal .dat payload into its JSON dict."""
    if isinstance(raw, str):
        raw = raw.encode("latin-1")
    inner = base64.b64decode(raw).decode("latin-1")
    cipher_b64, iv_hex = inner.split(":", 1)
    ct = base64.b64decode(cipher_b64)
    iv = bytes.fromhex(iv_hex)
    passwd = base64.b64decode(_PASS_B64)
    salt = base64.b64decode(_SALT_B64)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt,
        iterations=1000, backend=default_backend(),
    )
    key = kdf.derive(passwd)
    dec = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).decryptor()
    pt = dec.update(ct) + dec.finalize()
    pad = pt[-1]
    if pad and pt[-pad:] == bytes([pad]) * pad:
        pt = pt[:-pad]
    if pt[:2] == b"\x1f\x8b":
        pt = gzip.decompress(pt)
    return json.loads(pt.decode("utf-8"))


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Home page parsing (event list + page xHash)
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Match-event feed
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Orchestration + persistence
# --------------------------------------------------------------------------- #
def event_row(event: dict, odds_by_bookie: dict, names: dict[int, str] | None = None) -> dict:
    """Flatten one event + its bookmaker odds into a CSV-friendly row.

    Per-bookie columns keep the numeric id (h_27/oh_27/...); a ``bookies``
    list maps ids to resolved names for readability.
    """
    names = names or {}
    row: dict = {
        "match_date": _dt.datetime.fromtimestamp(
            int(event.get("date-start-timestamp") or 0), tz=_dt.timezone.utc
        ).date().isoformat() if event.get("date-start-timestamp") else None,
        "home": event.get("home-name"),
        "away": event.get("away-name"),
        "tour": (event.get("superTemplate") or {}).get("name"),
        "status": event.get("status-id"),
        "encode_event_id": event.get("encodeEventId"),
        "result": event.get("result"),
        "n_bookies": len(odds_by_bookie),
        "bookies": [names.get(bid, str(bid)) for bid in sorted(odds_by_bookie)],
    }
    for bid, o in odds_by_bookie.items():
        row[f"h_{bid}"] = o["home"]
        row[f"a_{bid}"] = o["away"]
        row[f"oh_{bid}"] = o["opening_home"]
        row[f"oa_{bid}"] = o["opening_away"]
    homes = [o["home"] for o in odds_by_bookie.values()]
    aways = [o["away"] for o in odds_by_bookie.values()]
    opens_h = [o["opening_home"] for o in odds_by_bookie.values() if o["opening_home"] == o["opening_home"]]
    opens_a = [o["opening_away"] for o in odds_by_bookie.values() if o["opening_away"] == o["opening_away"]]
    row["best_home"] = max(homes) if homes else None
    row["best_away"] = max(aways) if aways else None
    row["best_open_home"] = max(opens_h) if opens_h else None
    row["best_open_away"] = max(opens_a) if opens_a else None
    return row


def scrape_tennis(
    tour_filter: str | None = None,
    statuses: set[int] | None = None,
    max_events: int | None = None,
    out_dir: str | None = None,
    use_backend: bool = True,
    sleep_between: float = 0.2,
) -> str:
    """Scrape the tennis home event list + match-winner odds for each event.

    tour_filter: 'atp' | 'wta' | None (filters on superTemplate name).
    Saves a JSONL + CSV under ``out_dir`` (default data/raw/{tour}/odds_portal/)
    and returns the JSONL path.
    """
    events, xhash = fetch_tennis_events(statuses=statuses)
    if not events:
        logger.warning("  [WARN] No events found on tennis home page")
        return ""
    if not xhash:
        # The per-event feed URL embeds the page xHash; without it every
        # match-event request would 404.
        logger.warning("  [WARN] No xHash on tennis home page; cannot fetch events")
        return ""
    if tour_filter:
        tl = tour_filter.lower()
        events = [
            e for e in events
            if tl in ((e.get("superTemplate") or {}).get("name", "")).lower()
        ]
    if max_events:
        events = events[:max_events]
    logger.info(f"  Scraping odds for {len(events)} tennis events (xHash={xhash}) ...")

    names = fetch_providers_names(use_backend=use_backend)
    rows: list[dict] = []
    ok = 0
    fail = 0
    for i, ev in enumerate(events, 1):
        enc = ev.get("encodeEventId")
        if not enc:
            continue
        try:
            payload = fetch_match_event(enc, xhash, use_backend=use_backend)
            market = extract_market_odds(payload)
            rows.append(event_row(ev, market, names))
            ok += 1
            if i % 10 == 0:
                logger.info(f"    {i}/{len(events)} ...")
        except Exception as exc:  # noqa: BLE001
            fail += 1
            if fail <= 5:
                logger.warning(f"    [WARN] {enc}: {exc}")
        time.sleep(sleep_between)

    if not rows:
        logger.warning("  [WARN] No odds scraped")
        return ""

    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d_%H%M")
    tag = f"{tour_filter}_{stamp}" if tour_filter else stamp
    base = out_dir or os.path.join(config.RAW_DIR, (tour_filter or "tennis"), "odds_portal")
    os.makedirs(base, exist_ok=True)
    jsonl_path = os.path.join(base, f"oddsportal_{tag}.jsonl")
    csv_path = os.path.join(base, f"oddsportal_{tag}.csv")

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    try:
        import pandas as pd
        pd.DataFrame(rows).to_csv(csv_path, index=False)
    except Exception:  # noqa: BLE001
        pass

    with open(os.path.join(base, "providers.json"), "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in sorted(names.items())}, f, ensure_ascii=False, indent=1)

    logger.info(
        f"  Saved {len(rows)} events ({ok} ok / {fail} failed) -> {jsonl_path}"
    )
    return jsonl_path


def bookmaker_name(bookie_id: int) -> str:
    return BOOKMAKER_IDS.get(bookie_id, f"bookie_{bookie_id}")


_PROVIDERS_CACHE: dict[int, str] | None = None


def fetch_providers_names(use_backend: bool = True, force_refresh: bool = False) -> dict[int, str]:
    """Fetch the bookmaker id -> name map from /ajax-providers-bonus-data/0/.

    The response is encrypted like every other backend .dat payload and
    contains providersNames + per-bookmaker flags (logo, affiliate links,
    betting-exchange flag). Cached in memory; returns the hardcoded map on
    any failure.
    """
    global _PROVIDERS_CACHE
    if _PROVIDERS_CACHE is not None and not force_refresh:
        return _PROVIDERS_CACHE
    try:
        prefix = _BACKEND if use_backend else _PROXY
        resp = _fetch(f"{prefix}/ajax-providers-bonus-data/0/?geo=it&lang=it", referer=_HOME_URL)
        payload = decrypt_payload(resp)
        names = (payload.get("d") or {}).get("providersNames") or {}
        out: dict[int, str] = {}
        for k, v in names.items():
            try:
                out[int(k)] = str(v)
            except (TypeError, ValueError):
                continue
        if out:
            _PROVIDERS_CACHE = out
            return out
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"  [WARN] providers fetch failed, using static map: {exc}")
    return dict(BOOKMAKER_IDS)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape OddsPortal tennis odds (free, no API)")
    parser.add_argument("--tour", choices=["atp", "wta"], default=None)
    parser.add_argument("--status", choices=["scheduled", "finished", "all"], default="all")
    parser.add_argument("--max-events", type=int, default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--proxy", action="store_true", help="route via centroquote proxy instead of backend")
    args = parser.parse_args()

    status_map = {"scheduled": {1}, "finished": {3}, "all": None}
    scrape_tennis(
        tour_filter=args.tour,
        statuses=status_map[args.status],
        max_events=args.max_events,
        out_dir=args.out,
        use_backend=not args.proxy,
    )
