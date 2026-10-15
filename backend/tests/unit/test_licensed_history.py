"""Integrity and preservation guarantees for historical data restoration."""

import hashlib

import pytest
import requests

from data.licensed_history import preserve_download, validate_match_csv


@pytest.mark.parametrize(
    "content",
    [b"<html>error</html>", b"tourney_date,score\n", b"tourney_date\n20250101\n"],
)
def test_invalid_history_is_rejected(content):
    with pytest.raises(ValueError):
        validate_match_csv(content)


def test_existing_history_is_preserved_without_network(tmp_path, monkeypatch):
    destination = tmp_path / "matches.csv"
    destination.write_bytes(b"original")
    original_time = destination.stat().st_mtime_ns
    monkeypatch.setattr(
        requests, "get", lambda *args, **kwargs: pytest.fail("Network was unnecessary")
    )
    assert (
        preserve_download(
            "https://example.com", destination, hashlib.sha256(b"original").hexdigest()
        )
        == b"original"
    )
    assert destination.stat().st_mtime_ns == original_time
    with pytest.raises(ValueError, match="Checksum mismatch"):
        preserve_download("https://example.com", destination, "wrong")
    assert destination.read_bytes() == b"original"


def test_corrupt_download_is_never_saved(tmp_path, monkeypatch):
    response = requests.Response()
    response.status_code = 200
    response._content = b"corrupt"
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)
    destination = tmp_path / "matches.csv"
    with pytest.raises(ValueError, match="Checksum mismatch"):
        preserve_download("https://example.com", destination, "wrong")
    assert not destination.exists()


@pytest.fixture
def reviewed_manifest(tmp_path):
    import json

    metadata = tmp_path / "manifests"
    metadata.mkdir()
    readme = b"unit-test source license metadata"
    files = []
    responses = {
        "https://raw.githubusercontent.com/unit/atp/revision/README.md": readme
    }
    for year in [2025, 2026]:
        content = (
            "tourney_date,winner_id,loser_id,winner_name,loser_name,score\n"
            f"{year}0101,1,2,One,Two,6-2 6-4\n"
        ).encode()
        name = f"atp_matches_{year}.csv"
        url = f"https://raw.githubusercontent.com/unit/atp/revision/{name}"
        responses[url] = content
        files.append(
            dict(file=name, url=url, rows=1, sha256=hashlib.sha256(content).hexdigest())
        )
    manifest = dict(
        author="unit",
        license="unit",
        repository="unit/atp",
        revision="revision",
        readme_sha256=hashlib.sha256(readme).hexdigest(),
        files=files,
    )
    (metadata / "atp-manifest.json").write_text(json.dumps(manifest))
    return metadata, responses


def test_reviewed_manifest_extension_downloads_2026_and_preserves_existing_metadata(
    tmp_path, monkeypatch, reviewed_manifest
):
    import data.licensed_history as module

    metadata, responses = reviewed_manifest
    raw = tmp_path / "raw"
    directory = raw / "atp"
    directory.mkdir(parents=True)
    (directory / "source_manifest.json").write_text("original acquisition manifest")

    def response(url, **kwargs):
        result = requests.Response()
        result.status_code = 200
        result._content = responses[url]
        return result

    monkeypatch.setattr(module, "MANIFEST_DIR", metadata)
    monkeypatch.setattr(module, "RAW_DIR", raw)
    monkeypatch.setattr(requests, "get", response)
    module.download_history("atp", start=2025)
    assert (directory / "atp_matches_2026.csv").exists()
    assert (
        directory / "source_manifest.json"
    ).read_text() == "original acquisition manifest"
    assert len(list(directory.glob("source_manifest-*.json"))) == 1
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: pytest.fail("No repeat download expected"),
    )
    module.download_history("atp", start=2025)
    with pytest.raises(ValueError, match="reviewed manifest"):
        module.download_history("atp", start=2025, end=2027)
