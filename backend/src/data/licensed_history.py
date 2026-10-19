"""Restore pinned, attributed CC BY-NC-SA singles data without overwriting files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
from pathlib import Path
from datetime import datetime

import requests
from pydantic import BaseModel

from config import BASE_DIR, RAW_DIR
from logging_config import get_logger

logger = get_logger(__name__)
MANIFEST_DIR = BASE_DIR / "docs" / "data-sources"


class HistoricalFile(BaseModel):
    """Expected bytes and provenance of one historical CSV."""

    file: str
    url: str
    rows: int
    sha256: str


class SourceManifest(BaseModel):
    """Reviewed source revision and original attribution."""

    author: str
    license: str
    repository: str
    revision: str
    readme_sha256: str
    files: list[HistoricalFile]


def validate_match_csv(content: bytes) -> int:
    """Reject HTML, incomplete rows, and files outside the expected schema."""
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    required = {
        "tourney_date",
        "winner_id",
        "loser_id",
        "winner_name",
        "loser_name",
        "score",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError("Historical CSV is empty or missing required columns")
    for row in rows:
        datetime_value = row.get("tourney_date", "")
        datetime.strptime(datetime_value, "%Y%m%d")
        if any(not row.get(key) for key in required - {"score"}) or None in row:
            raise ValueError("Historical CSV contains an incomplete match row")
    return len(rows)


def preserve_download(url: str, destination: Path, checksum: str) -> bytes:
    """Reuse verified files; refuse to replace anything with different contents."""
    content = destination.read_bytes() if destination.exists() else None
    if content is None:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        content = response.content
    if hashlib.sha256(content).hexdigest() != checksum:
        raise ValueError(
            f"Checksum mismatch for {destination}; existing files were preserved"
        )
    if not destination.exists():
        with destination.open("xb") as output:
            output.write(content)
    return content


def reviewed_files(manifest: SourceManifest, tour: str) -> dict[int, HistoricalFile]:
    """Only explicitly reviewed annual files may extend the historical horizon."""
    files: dict[int, HistoricalFile] = {}
    for entry in manifest.files:
        match = re.fullmatch(rf"{tour}_matches_(\d{{4}})\.csv", entry.file)
        if match is None or int(match[1]) in files:
            raise ValueError("Manifest contains an invalid or duplicate annual file")
        files[int(match[1])] = entry
    if not files:
        raise ValueError("No reviewed historical files")
    return files


def retain_manifest(directory: Path, content: bytes) -> None:
    """Extended reviews get new snapshots; the original local manifest survives."""
    digest = hashlib.sha256(content).hexdigest()
    for target in (
        directory / f"source_manifest-{digest}.json",
        directory / "source_manifest.json",
    ):
        if target.exists():
            if target.name != "source_manifest.json" and target.read_bytes() != content:
                raise ValueError("Conflicting versioned acquisition manifest")
            continue
        with target.open("xb") as output:
            output.write(content)


def download_history(tour: str, start: int = 2005, end: int | None = None) -> None:
    """Restore singles results only; odds and paid APIs are independent."""
    if tour not in ("atp", "wta"):
        raise ValueError("Expected ATP/WTA")
    manifest_path = MANIFEST_DIR / f"{tour}-manifest.json"
    manifest = SourceManifest.model_validate_json(manifest_path.read_text())
    files = reviewed_files(manifest, tour)
    end = max(files) if end is None else end
    if start > end or any(year not in files for year in range(start, end + 1)):
        raise ValueError("Requested years must all be present in the reviewed manifest")
    directory = RAW_DIR / tour
    directory.mkdir(parents=True, exist_ok=True)
    base_url = (
        f"https://raw.githubusercontent.com/{manifest.repository}/{manifest.revision}"
    )
    preserve_download(
        f"{base_url}/README.md", directory / "SOURCE_README.md", manifest.readme_sha256
    )
    for year in range(start, end + 1):
        entry = files[year]
        if entry.url != f"{base_url}/{entry.file}":
            raise ValueError("Manifest URL does not match its pinned revision")
        content = preserve_download(entry.url, directory / entry.file, entry.sha256)
        if validate_match_csv(content) != entry.rows:
            raise ValueError(f"Unexpected row count in {entry.file}")
        logger.info("Verified %s: %s matches", entry.file, entry.rows)
    retain_manifest(directory, manifest_path.read_bytes())


def main() -> None:
    """Fetch the licensed dataset without sportsbook dependencies."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tour", choices=["atp", "wta", "both"], default="both")
    parser.add_argument("--start", type=int, default=2005)
    parser.add_argument("--end", type=int)
    args = parser.parse_args()
    for tour in (["atp", "wta"] if args.tour == "both" else [args.tour]):
        download_history(tour, args.start, args.end)


if __name__ == "__main__":
    main()
