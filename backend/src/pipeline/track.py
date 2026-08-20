"""
Certified, append-only prediction track record (myfxbook-style).

Design goals
------------
* **Immutable predictions.** Every prediction is written once, as a single
  line, and never modified. Each line carries a SHA-256 hash of its content,
  so any later edit is detectable (tamper-evident).
* **Settlements as separate events.** When a match resolves, we APPEND a
  settlement event to a second file — we never rewrite the predictions file.
* **State is folded, not stored.** The "current" view (settled? correct?) is
  reconstructed by joining predictions + settlements at read time.

This is what makes the record certifiable: the prediction provably existed,
unchanged, before its outcome was appended.

Files (committed under reports/, so the history is public & verifiable):
  reports/{tour}/predictions_log.jsonl   -- append-only, immutable
  reports/{tour}/settlements_log.jsonl   -- append-only settlement events
"""

import os
import sys
import uuid
import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from pipeline.track_io import (
    append as _append,
    content_hash as _content_hash,
    pred_path as _pred_path,
    read_jsonl as _read_jsonl,
    settle_path as _settle_path,
    settlement_index as _settlement_index,
)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def log_prediction(
    tour: str,
    model: str,
    player1: str,
    player2: str,
    surface: str,
    best_of: int,
    prob1: float,
    predicted_winner: str,
    reliability: Optional[str] = None,
    odds1: Optional[float] = None,
    odds2: Optional[float] = None,
) -> str:
    """Append one immutable prediction. Returns its id.

    odds1/odds2: decimal market odds for player1/player2 at prediction time
    (if known). They are hashed into the record so they are tamper-evident,
    and can later be compared with closing odds to compute realized CLV.
    """
    rec = {
        "id": uuid.uuid4().hex[:12],
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "tour": tour,
        "model": model,
        "player1": player1,
        "player2": player2,
        "surface": surface,
        "best_of": best_of,
        "prob1": round(float(prob1), 4),
        "predicted_winner": predicted_winner,
        "reliability": reliability,
        "odds1": round(float(odds1), 3) if odds1 else None,
        "odds2": round(float(odds2), 3) if odds2 else None,
    }
    rec["hash"] = _content_hash(rec)
    _append(_pred_path(tour), rec)
    return rec["id"]


def read_log(tour: str = "atp") -> list[dict]:
    """Folded view: each prediction merged with its settlement (if any).

    Predictions remain immutable on disk; this join happens in memory.
    """
    settlements = _settlement_index(tour)
    folded = []
    for p in _read_jsonl(_pred_path(tour)):
        s = settlements.get(p["id"])
        rec = dict(p)
        if s:
            rec["settled"] = True
            rec["actual_winner"] = s.get("actual_winner")
            rec["correct"] = s.get("correct")
            rec["match_date"] = s.get("match_date")
            rec["settled_ts"] = s.get("settled_ts")
        else:
            rec["settled"] = False
            rec["actual_winner"] = None
            rec["correct"] = None
            rec["match_date"] = None
            rec["settled_ts"] = None
        folded.append(rec)
    return folded


def settle_predictions(tour: str = "atp") -> dict:
    """Find unsettled predictions and APPEND settlement events for those whose
    match now appears in the feature dataset. Never rewrites predictions."""
    import pandas as pd

    preds = _read_jsonl(_pred_path(tour))
    if not preds:
        return {"settled": 0, "open": 0, "total": 0, "newly_settled": 0}

    already = set(_settlement_index(tour).keys())

    data_path = os.path.join(config.PROCESSED_DIR, f"{tour}_features.parquet")
    if not os.path.exists(data_path):
        return {"error": "feature dataset not found", "total": len(preds)}

    df = pd.read_parquet(data_path)
    won = df[df["label"] == 1].copy()
    date_col = "match_date_est" if "match_date_est" in won.columns else "tourney_date"
    won["_p1"] = won["p1_name"].str.lower()
    won["_p2"] = won["p2_name"].str.lower()
    won[date_col] = pd.to_datetime(won[date_col], errors="coerce")

    newly = 0
    for rec in preds:
        if rec["id"] in already:
            continue
        a, b = rec["player1"].lower(), rec["player2"].lower()
        pred_day = pd.to_datetime(rec["ts"], errors="coerce")
        if pred_day is not None and not pd.isna(pred_day):
            pred_day = pred_day.tz_localize(None) if pred_day.tzinfo else pred_day

        mask = (
            ((won["_p1"] == a) & (won["_p2"] == b))
            | ((won["_p1"] == b) & (won["_p2"] == a))
        )
        if rec.get("surface"):
            mask &= won["surface"] == rec["surface"]
        if pred_day is not None and not pd.isna(pred_day):
            mask &= won[date_col] >= pred_day.normalize()

        hits = won[mask].sort_values(date_col)
        if hits.empty:
            continue

        row = hits.iloc[0]
        actual_winner = row["p1_name"]  # label==1 -> p1 is the true winner
        event = {
            "pred_id": rec["id"],
            "pred_hash": rec.get("hash"),
            "actual_winner": actual_winner,
            "correct": bool(actual_winner.lower() == rec["predicted_winner"].lower()),
            "match_date": str(pd.to_datetime(row[date_col]).date()),
            "settled_ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        }
        _append(_settle_path(tour), event)
        newly += 1

    return summary(tour) | {"newly_settled": newly}


def summary(tour: str = "atp") -> dict:
    """Aggregate realized accuracy / Brier over settled predictions."""
    records = read_log(tour)
    settled = [r for r in records if r.get("settled")]
    correct = sum(1 for r in settled if r.get("correct"))
    n = len(settled)
    brier = None
    if n > 0:
        sq = 0.0
        for r in settled:
            p_pred = (
                r["prob1"]
                if r["predicted_winner"].lower() == r["player1"].lower()
                else 1 - r["prob1"]
            )
            sq += (1.0 - p_pred) ** 2 if r.get("correct") else p_pred ** 2
        brier = round(sq / n, 4)
    return {
        "total": len(records),
        "settled": n,
        "open": len(records) - n,
        "correct": correct,
        "accuracy": round(correct / n, 4) if n else None,
        "brier": brier,
        "avg_odds_edge": _avg_odds_edge(records),
    }


def _avg_odds_edge(records: list[dict]) -> Optional[float]:
    """Mean expected edge (p_pred * taken_odds - 1) over predictions that
    carry market odds for the predicted winner. Positive = positive-EV at
    the logged price; zero = no odds data."""
    edges = []
    for r in records:
        odds = r.get("odds1") if r["predicted_winner"].lower() == r["player1"].lower() else r.get("odds2")
        if not odds or odds <= 1.0:
            continue
        p = r["prob1"] if r["predicted_winner"].lower() == r["player1"].lower() else 1 - r["prob1"]
        edges.append(p * odds - 1.0)
    return round(float(sum(edges) / len(edges)), 4) if edges else None


def verify_integrity(tour: str = "atp") -> dict:
    """Recompute every prediction's hash and flag any tampering.

    A clean result certifies the log hasn't been altered since each line was
    written. Also checks settlements reference an existing, matching prediction.
    """
    preds = _read_jsonl(_pred_path(tour))
    pred_by_id = {p["id"]: p for p in preds}
    tampered = []
    for p in preds:
        stored = p.get("hash")
        if stored != _content_hash(p):
            tampered.append(p.get("id"))

    orphan_settlements = []
    hash_mismatch = []
    for s in _read_jsonl(_settle_path(tour)):
        pid = s.get("pred_id")
        if pid not in pred_by_id:
            orphan_settlements.append(pid)
        elif s.get("pred_hash") and s["pred_hash"] != pred_by_id[pid].get("hash"):
            hash_mismatch.append(pid)

    ok = not tampered and not orphan_settlements and not hash_mismatch
    return {
        "ok": ok,
        "predictions": len(preds),
        "tampered_predictions": tampered,
        "orphan_settlements": orphan_settlements,
        "settlement_hash_mismatch": hash_mismatch,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Certified prediction track record")
    parser.add_argument("--tour", default="atp")
    parser.add_argument("--settle", action="store_true", help="Settle open predictions")
    parser.add_argument("--verify", action="store_true", help="Verify log integrity")
    args = parser.parse_args()

    if args.settle:
        print(settle_predictions(args.tour))
    elif args.verify:
        print(verify_integrity(args.tour))
    else:
        print(summary(args.tour))
