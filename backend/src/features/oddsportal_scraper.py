"""OddsPortal (centroquote.it) odds scraper — orchestration + persistence.

Crypto lives in features/oddsportal_crypto.py and HTTP/event parsing in
features/oddsportal_parse.py; this module owns the scrape loop, CSV/JSONL
output and the bookmaker id -> name resolution.

This gives free opening + current odds for ~12 bookmakers on every listed
tennis event, including already-finished matches — enough to build a CLV
dataset and live value detection without paid APIs.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import time

from logging_config import get_logger
from features.oddsportal_crypto import decrypt_payload
from features.oddsportal_parse import (
    _fetch,
    _HOME_URL,
    extract_market_odds,
    fetch_match_event,
    fetch_tennis_events,
)

logger = get_logger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

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
        prefix = "https://backend.oddsportal.com" if use_backend else "https://www.centroquote.it/proxy"
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
