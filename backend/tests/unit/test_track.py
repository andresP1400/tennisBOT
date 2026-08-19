"""Certified append-only track-record tests."""

import os

import pandas as pd
import pytest

from pipeline import track


@pytest.fixture
def temp_reports(tmp_path, monkeypatch):
    """Redirect the track files to a temp reports dir."""
    import config
    monkeypatch.setattr(config, "REPORTS_DIR", str(tmp_path))
    return str(tmp_path)


def _append_pred_at(ts: str, p1: str, p2: str, predicted: str | None = None, tour: str = "atp") -> str:
    """Append an immutable prediction with a controlled timestamp (test helper)."""
    import uuid
    rec = {
        "id": uuid.uuid4().hex[:12], "ts": ts, "tour": tour, "model": "m",
        "player1": p1, "player2": p2, "surface": "Hard", "best_of": 3,
        "prob1": 0.7, "predicted_winner": predicted or p1, "reliability": "alta",
    }
    rec["hash"] = track._content_hash(rec)
    track._append(track._pred_path(tour), rec)
    return rec["id"]


def test_log_and_read(temp_reports):
    rid = track.log_prediction(
        "atp", "atp_model.pkl", "A Player", "B Player", "Hard", 3,
        0.7, "A Player", "alta",
    )
    recs = track.read_log("atp")
    assert len(recs) == 1
    assert recs[0]["id"] == rid
    assert recs[0]["settled"] is False
    assert recs[0]["predicted_winner"] == "A Player"
    assert len(recs[0]["hash"]) == 64  # sha256 hex


def test_integrity_ok_and_tamper_detected(temp_reports):
    track.log_prediction("atp", "m", "A", "B", "Hard", 3, 0.7, "A")
    assert track.verify_integrity("atp")["ok"] is True

    # tamper: flip the recorded probability on disk, keep the old hash
    path = track._pred_path("atp")
    import json
    line = json.loads(open(path).read().strip())
    line["prob1"] = 0.01
    open(path, "w").write(json.dumps(line) + "\n")

    res = track.verify_integrity("atp")
    assert res["ok"] is False
    assert line["id"] in res["tampered_predictions"]


def test_summary_counts(temp_reports):
    track.log_prediction("atp", "m", "A", "B", "Hard", 3, 0.7, "A")
    track.log_prediction("atp", "m", "C", "D", "Clay", 3, 0.6, "C")
    s = track.summary("atp")
    assert s["total"] == 2
    assert s["open"] == 2
    assert s["settled"] == 0
    assert s["accuracy"] is None


def test_settlement_is_appended_predictions_immutable(temp_reports, tmp_path, monkeypatch):
    """Settling appends an event; the predictions file is never modified."""
    df = pd.DataFrame([
        {"match_id": "1_A", "label": 1, "p1_name": "A Player", "p2_name": "B Player",
         "surface": "Hard", "match_date_est": pd.Timestamp("2024-05-01")},
        {"match_id": "1_B", "label": 0, "p1_name": "B Player", "p2_name": "A Player",
         "surface": "Hard", "match_date_est": pd.Timestamp("2024-05-01")},
    ])
    import config
    monkeypatch.setattr(config, "PROCESSED_DIR", str(tmp_path))
    df.to_parquet(os.path.join(str(tmp_path), "atp_features.parquet"))

    # prediction dated BEFORE the match (you can only settle later results)
    rid = _append_pred_at("2024-04-01T00:00:00+00:00", "A Player", "B Player")
    pred_bytes_before = open(track._pred_path("atp"), "rb").read()

    res = track.settle_predictions("atp")
    assert res["newly_settled"] == 1

    # predictions file unchanged (immutable)
    assert open(track._pred_path("atp"), "rb").read() == pred_bytes_before
    # settlement event written separately
    assert os.path.exists(track._settle_path("atp"))

    folded = track.read_log("atp")[0]
    assert folded["id"] == rid
    assert folded["settled"] is True
    assert folded["actual_winner"] == "A Player"
    assert folded["correct"] is True
    assert track.summary("atp")["accuracy"] == 1.0
    assert track.verify_integrity("atp")["ok"] is True


def test_settle_is_idempotent(temp_reports, tmp_path, monkeypatch):
    """Running settle twice must not append duplicate settlement events."""
    df = pd.DataFrame([
        {"match_id": "1_A", "label": 1, "p1_name": "A Player", "p2_name": "B Player",
         "surface": "Hard", "match_date_est": pd.Timestamp("2024-05-01")},
    ])
    import config
    monkeypatch.setattr(config, "PROCESSED_DIR", str(tmp_path))
    df.to_parquet(os.path.join(str(tmp_path), "atp_features.parquet"))

    _append_pred_at("2024-04-01T00:00:00+00:00", "A Player", "B Player")
    first = track.settle_predictions("atp")
    second = track.settle_predictions("atp")
    assert first["newly_settled"] == 1
    assert second["newly_settled"] == 0
    assert track.summary("atp")["settled"] == 1
