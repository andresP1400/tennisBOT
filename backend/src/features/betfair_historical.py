"""Betfair exchange CLV historical client — CLI entry point.

All the logic (fetch, archive, CLV computation) lives in
features/betfair_clv.py; this module is a thin argparse wrapper.

CLI::

    python -m features.betfair_historical --snapshot
    python -m features.betfair_historical --snapshot --loop --interval-hours 6
    python -m features.betfair_historical --report
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone

from features.betfair_clv import (
    append_snapshot,
    build_clv_report,
    fetch_exchange_snapshot,
    load_snapshots,
)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Betfair exchange CLV historical client")
    parser.add_argument("--snapshot", action="store_true", help="fetch + append one snapshot")
    parser.add_argument("--loop", action="store_true", help="loop snapshots")
    parser.add_argument("--interval-hours", type=float, default=6.0)
    parser.add_argument("--report", action="store_true", help="print CLV coverage report")
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()

    if args.report:
        data = load_snapshots(days=args.days)
        print(json.dumps(build_clv_report(data, days=args.days), indent=2))
        sys.exit(0)

    if not args.snapshot and not args.loop:
        parser.error("use --snapshot, --loop or --report")

    while True:
        evs = fetch_exchange_snapshot()
        print(f"[{datetime.now(timezone.utc).isoformat()}] {len(evs)} events")
        if evs:
            path = append_snapshot(evs)
            print(f"  -> {path}")
        if not args.loop:
            break
        time.sleep(args.interval_hours * 3600)
