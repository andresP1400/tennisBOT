"""Pinned public result snapshots with publisher-declared reuse licenses."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import requests
from pydantic import BaseModel, Field

from config import BASE_DIR, RAW_DIR

MANIFEST = BASE_DIR / "docs/data-sources/result-extensions-20261018.json"


class ResultFile(BaseModel):
    """A separately versioned identity file with its own checksum and license."""

    url: str
    sha256: str
    license: str


class ResultSource(BaseModel):
    """A versioned provider archive and the exact reviewed member bytes."""

    tour: str
    dataset: str
    version: int
    license: str
    kind: str
    url: str
    sha256: str
    members: dict[str, str]
    metadata_sha256: str
    external_members: dict[str, ResultFile] = Field(default_factory=dict)
    active: bool = True


def source_for(tour: str) -> ResultSource:
    """Only a committed review can select a dataset version."""
    sources = json.loads(MANIFEST.read_text())["sources"]
    matches = [
        ResultSource.model_validate(item)
        for item in sources
        if item["tour"] == tour and item.get("active", True)
    ]
    if len(matches) != 1:
        raise ValueError("Exactly one reviewed extension is required per tour")
    return matches[0]


def checked_bytes(path: Path, expected: str) -> bytes:
    """Preserve conflicting local files and fail rather than replacing them."""
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError(f"Result snapshot checksum mismatch: {path}")
    return content


def acquire_source(source: ResultSource) -> Path:
    """Verify archive and members without extracting untrusted archive paths."""
    directory = RAW_DIR / "extensions" / source.tour / str(source.version)
    directory.mkdir(parents=True, exist_ok=True)
    if any(
        Path(name).name != name for name in (*source.members, *source.external_members)
    ):
        raise ValueError("Result member must be a plain filename")
    missing = [name for name in source.members if not (directory / name).exists()]
    if missing:
        response = requests.get(source.url, timeout=90)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != source.sha256:
            raise ValueError("Result archive checksum mismatch")
        retain_members(response.content, directory, source)
    for name, expected in source.members.items():
        checked_bytes(directory / name, expected)
    for name, entry in source.external_members.items():
        path = directory / name
        if not path.exists():
            response = requests.get(entry.url, timeout=60)
            response.raise_for_status()
            if hashlib.sha256(response.content).hexdigest() != entry.sha256:
                raise ValueError("Identity file checksum mismatch")
            with path.open("xb") as output:
                output.write(response.content)
        checked_bytes(path, entry.sha256)
    return directory


def retain_members(content: bytes, directory: Path, source: ResultSource) -> None:
    """Do not overwrite existing files or trust additional archive members."""
    if source.kind == "tml":
        if len(source.members) != 1:
            raise ValueError("Plain result download must have one member")
        name, expected = next(iter(source.members.items()))
        retain_file(content, directory / name, expected)
        return
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for name, expected in source.members.items():
            if Path(name).name != name:
                raise ValueError("Result member must be a plain filename")
            blob = archive.read(name)
            retain_file(blob, directory / name, expected)


def retain_file(blob: bytes, path: Path, expected: str) -> None:
    """Never replace an existing private snapshot."""
    if hashlib.sha256(blob).hexdigest() != expected:
        raise ValueError("Result member checksum mismatch")
    if not path.exists():
        with path.open("xb") as output:
            output.write(blob)
