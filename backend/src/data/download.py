"""Download raw CSV/XLSX tennis data.

Primary source: Artur73737/ATP-WTA_DATA mirror (Sackmann layout).
Odds: mirror first, then tennis-data.co.uk live fallback.

Usage:
    python -m data.download --tour atp
    python -m data.download --tour both --overwrite
    python main.py download --tour atp --overwrite
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

import requests
from tqdm import tqdm

from logging_config import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 TennisBot/2.0"
    )
}


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def download_file(
    url: str,
    dest_path: str,
    overwrite: bool = False,
    retries: int = 4,
) -> bool:
    """Download a single file. Returns True on success."""
    if os.path.exists(dest_path) and not overwrite:
        return True

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=60, headers=_HTTP_HEADERS)
            if resp.status_code == 200 and resp.content:
                # Guard against GitHub HTML error pages
                if resp.content[:15].lower().startswith(b"<!doctype html"):
                    logger.warning(f"  [WARN] HTML response (not data): {url}")
                    return False
                with open(dest_path, "wb") as f:
                    f.write(resp.content)
                return True
            if resp.status_code == 404:
                return False
            if attempt < retries:
                time.sleep(1.5 * attempt)
                continue
            logger.warning(
                f"  [WARN] {url}: HTTP {resp.status_code} after {retries} attempts"
            )
            return False
        except requests.RequestException as exc:
            if attempt < retries:
                time.sleep(1.5 * attempt)
                continue
            logger.error(f"  [ERROR] {url}: {exc}")
            return False
    return False


def download_matches(
    tour: str = "atp",
    start_year: int | None = None,
    end_year: int | None = None,
    overwrite: bool = False,
) -> list[str]:
    """Download yearly main-tour match CSV files (+ ATP qual/chall when available)."""
    start_year = start_year or config.MATCH_YEAR_START
    end_year = end_year or config.MATCH_YEAR_END
    base_url = config.ATP_REPO_BASE if tour == "atp" else config.WTA_REPO_BASE
    dest_dir = os.path.join(config.RAW_DIR, tour)
    _ensure_dir(dest_dir)

    downloaded: list[str] = []
    years = range(start_year, end_year + 1)
    logger.info(
        f"\n--- Downloading {tour.upper()} matches ({start_year}-{end_year}) ---"
    )
    for year in tqdm(years, desc=f"{tour.upper()} matches"):
        filename = f"{tour}_matches_{year}.csv"
        url = f"{base_url}/{filename}"
        dest = os.path.join(dest_dir, filename)
        if download_file(url, dest, overwrite):
            downloaded.append(dest)

    if tour == "atp":
        logger.info(
            f"\n--- Downloading ATP qual/chall ({max(1978, start_year)}-{end_year}) ---"
        )
        for year in tqdm(
            range(max(1978, start_year), end_year + 1), desc="ATP qual/chall"
        ):
            filename = f"atp_matches_qual_chall_{year}.csv"
            url = f"{base_url}/{filename}"
            dest = os.path.join(dest_dir, filename)
            download_file(url, dest, overwrite)

    logger.info(f"  Main-tour match files OK: {len(downloaded)} for {tour.upper()}")
    return downloaded


def download_players(tour: str = "atp", overwrite: bool = False) -> str:
    """Download the player master file."""
    base_url = config.ATP_REPO_BASE if tour == "atp" else config.WTA_REPO_BASE
    dest_dir = os.path.join(config.RAW_DIR, tour)
    _ensure_dir(dest_dir)
    filename = f"{tour}_players.csv"
    url = f"{base_url}/{filename}"
    dest = os.path.join(dest_dir, filename)
    logger.info(f"  Downloading {filename} ...")
    if download_file(url, dest, overwrite):
        logger.info(f"  OK: {dest}")
        return dest
    logger.warning(f"  FAILED: {url}")
    return ""


def download_rankings(tour: str = "atp", overwrite: bool = False) -> list[str]:
    """Download ranking files (decade buckets + current)."""
    base_url = config.ATP_REPO_BASE if tour == "atp" else config.WTA_REPO_BASE
    dest_dir = os.path.join(config.RAW_DIR, tour)
    _ensure_dir(dest_dir)
    suffixes = ["70s", "80s", "90s", "00s", "10s", "20s", "current"]
    downloaded: list[str] = []
    logger.info(f"\n--- Downloading {tour.upper()} rankings ---")
    for suffix in suffixes:
        filename = f"{tour}_rankings_{suffix}.csv"
        url = f"{base_url}/{filename}"
        dest = os.path.join(dest_dir, filename)
        if download_file(url, dest, overwrite):
            downloaded.append(dest)
    logger.info(f"  Ranking files OK: {len(downloaded)} for {tour.upper()}")
    return downloaded


def download_odds(
    tour: str = "atp",
    start_year: int = 2001,
    end_year: int | None = None,
    overwrite: bool = False,
) -> list[str]:
    """Download bookmaker odds: mirror first, then tennis-data.co.uk fallback.

    tennis-data paths:
      ATP:  {base}/{year}/{year}.xlsx
      WTA:  {base}/{year}w/{year}.xlsx   (women's tour, odds from ~2007)
    """
    end_year = end_year or config.MATCH_YEAR_END
    # WTA historical odds on tennis-data start around 2007
    min_odds_year = 2007 if tour == "wta" else 2001
    dest_dir = os.path.join(config.RAW_DIR, tour, "odds")
    _ensure_dir(dest_dir)
    downloaded: list[str] = []
    years = range(max(start_year, min_odds_year), end_year + 1)
    mirror_base = f"{config.DATA_REPO_BASE}/raw/{tour}/odds"
    live_base = getattr(config, "ODDS_LIVE_BASE", "http://www.tennis-data.co.uk")

    logger.info(f"\n--- Downloading {tour.upper()} odds ({start_year}-{end_year}) ---")
    for year in tqdm(years, desc=f"{tour.upper()} odds"):
        dest_xlsx = os.path.join(dest_dir, f"{year}.xlsx")
        dest_xls = os.path.join(dest_dir, f"{year}.xls")

        # Already have a file and not overwriting
        if not overwrite and (os.path.exists(dest_xlsx) or os.path.exists(dest_xls)):
            downloaded.append(dest_xlsx if os.path.exists(dest_xlsx) else dest_xls)
            continue

        # Prefer live tennis-data.co.uk (authoritative free odds source).
        # The GitHub mirror has historically mixed ATP odds into WTA/odds/.
        # WTA paths use the {year}w/ subfolder.
        if tour == "wta":
            live_urls = [
                (f"{live_base}/{year}w/{year}.xlsx", dest_xlsx),
                (f"{live_base}/{year}w/{year}.xls", dest_xls),
            ]
        else:
            live_urls = [
                (f"{live_base}/{year}/{year}.xlsx", dest_xlsx),
                (f"{live_base}/{year}/{year}.xls", dest_xls),
            ]
        got = False
        for url, dest in live_urls:
            if download_file(url, dest, overwrite=True):
                downloaded.append(dest)
                got = True
                break
        if got:
            continue

        # Fallback: mirror (may lag or be wrong for WTA — live preferred)
        if download_file(f"{mirror_base}/{year}.xlsx", dest_xlsx, overwrite=True):
            downloaded.append(dest_xlsx)
            continue
        if download_file(f"{mirror_base}/{year}.xls", dest_xls, overwrite=True):
            downloaded.append(dest_xls)
            continue

    logger.info(f"  Odds files OK: {len(downloaded)} for {tour.upper()}")
    return downloaded


def download_all(
    tour: str = "atp",
    start_year: int | None = None,
    end_year: int | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Download everything for one tour (full history by default)."""
    results: dict[str, Any] = {}
    results["matches"] = download_matches(tour, start_year, end_year, overwrite)
    results["players"] = download_players(tour, overwrite)
    results["rankings"] = download_rankings(tour, overwrite)
    results["odds"] = download_odds(
        tour,
        start_year=max(2001, start_year or 2001),
        end_year=end_year,
        overwrite=overwrite,
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Download tennis data (mirror + odds)")
    parser.add_argument("--tour", choices=["atp", "wta", "both"], default="atp")
    parser.add_argument(
        "--start",
        type=int,
        default=None,
        help=f"Start year (default: {config.MATCH_YEAR_START})",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=None,
        help=f"End year (default: {config.MATCH_YEAR_END})",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Re-download even if files exist"
    )
    args = parser.parse_args()
    tours = ["atp", "wta"] if args.tour == "both" else [args.tour]
    for tour in tours:
        download_all(tour, args.start, args.end, args.overwrite)
    logger.info("\nDownload complete.")


if __name__ == "__main__":
    main()
