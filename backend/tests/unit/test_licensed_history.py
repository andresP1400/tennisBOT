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
