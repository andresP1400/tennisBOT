"""Low-level JSONL persistence + tamper-evident hashing for the Track Record.

Public API (log_prediction/read_log/summary/settle/verify) lives in
pipeline/track.py; this module holds the append-only file helpers and the
content hash so both the API and the tests can share them.
"""
from __future__ import annotations

import os
import sys
import json
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def dir_for(tour: str) -> str:
    d = os.path.join(config.REPORTS_DIR, tour)
    os.makedirs(d, exist_ok=True)
    return d


def pred_path(tour: str = "atp") -> str:
    return os.path.join(dir_for(tour), "predictions_log.jsonl")


def settle_path(tour: str = "atp") -> str:
    return os.path.join(dir_for(tour), "settlements_log.jsonl")


_HASH_FIELDS = (
    "ts", "tour", "model", "player1", "player2",
    "surface", "best_of", "prob1", "predicted_winner",
    "odds1", "odds2",
)


def content_hash(rec: dict) -> str:
    payload = {k: rec.get(k) for k in _HASH_FIELDS}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def append(path: str, rec: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def settlement_index(tour: str) -> dict:
    """pred_id -> latest settlement event."""
    idx = {}
    for s in read_jsonl(settle_path(tour)):
        pid = s.get("pred_id")
        if pid:
            idx[pid] = s
    return idx
