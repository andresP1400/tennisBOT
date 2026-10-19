"""Reproducible completeness/suitability audit of the checksum-verified snapshot."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from config import RAW_DIR, REPORTS_DIR
from data.licensed_history import MANIFEST_DIR, SourceManifest
from pipeline.personal_data import load_history


def coverage(frame: pd.DataFrame) -> dict[str, int]:
    """Distinguish complete statistics from partial/missing observations."""
    result = {"matches": len(frame)}
    complete = []
    for side in ("w", "l"):
        values = frame.reindex(
            columns=[f"{side}_1stWon", f"{side}_2ndWon", f"{side}_svpt"]
        )
        first, second, total = (values.iloc[:, index] for index in range(3))
        valid = (
            np.isfinite(values).all(axis=1)
            & (first >= 0)
            & (second >= 0)
            & (total > 0)
            & (first + second <= total)
        )
        complete.append(valid)
        result[f"{side}_complete_serve_counts"] = int(valid.sum())
        result[f"{side}_partial_serve_counts"] = int(
            (values.notna().any(axis=1) & ~values.notna().all(axis=1)).sum()
        )
    result["both_complete_serve_counts"] = int((complete[0] & complete[1]).sum())
    identities = frame.reindex(columns=["winner_id", "loser_id"])
    result["missing_player_ids"] = int(identities.isna().any(axis=1).sum())
    result["identical_player_ids"] = int(
        (identities.winner_id == identities.loser_id).sum()
    )
    demographics = frame.reindex(
        columns=["winner_ht", "loser_ht", "winner_age", "loser_age"]
    )
    result["missing_demographics"] = int(demographics.isna().any(axis=1).sum())
    return result


def audit_tour(tour: str) -> dict[str, object]:
    """Check pinned source bytes before reporting raw and eligible coverage separately."""
    eligible, exclusions = load_history(tour)
    manifest = SourceManifest.model_validate_json(
        (MANIFEST_DIR / f"{tour}-manifest.json").read_text()
    )
    raw = pd.concat(
        [pd.read_csv(RAW_DIR / tour / entry.file) for entry in manifest.files],
        ignore_index=True,
    )
    return {
        "source_audit": exclusions,
        "raw": coverage(raw),
        "eligible": coverage(eligible),
    }


def main() -> None:
    """Write a new audit without overwriting an existing report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    timestamp = datetime.now(timezone.utc)
    report = {
        "checked_at": timestamp.isoformat(),
        "tours": {tour: audit_tour(tour) for tour in ("atp", "wta")},
    }
    output = (
        args.output
        or REPORTS_DIR
        / "personal"
        / f"history-quality-{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as destination:
        destination.write(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
