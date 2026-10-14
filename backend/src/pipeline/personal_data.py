"""Audit real licensed matches and construct conservative chronological features."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from config import RAW_DIR
from data.licensed_history import MANIFEST_DIR, SourceManifest, download_history
from pipeline.personal_state import (
    Player,
    SURFACES,
    match_vector,
    normalize_name,
    update_ratings,
)


def load_history(tour: str) -> tuple[pd.DataFrame, dict[str, object]]:
    """Verify source bytes, quantify exclusions, and reject impossible metadata."""
    download_history(tour)
    manifest = SourceManifest.model_validate_json(
        (MANIFEST_DIR / f"{tour}-manifest.json").read_text()
    )
    frame = pd.concat(
        [pd.read_csv(RAW_DIR / tour / entry.file) for entry in manifest.files],
        ignore_index=True,
    )
    frame["date"] = pd.to_datetime(
        frame["tourney_date"].astype(str), format="%Y%m%d", errors="coerce"
    )
    invalid = frame["date"].isna() | (frame["date"] > pd.Timestamp.today())
    incomplete = frame["score"].isna() | frame["score"].astype(str).str.contains(
        "RET|W/O|DEF|ABN", case=False
    )
    missing_surface = ~frame["surface"].isin(SURFACES)
    duplicate = frame.duplicated(["tourney_id", "match_num", "winner_id", "loser_id"])
    excluded = invalid | incomplete | missing_surface | duplicate
    audit: dict[str, object] = {
        "raw_rows": len(frame),
        "invalid_dates": int(invalid.sum()),
        "incomplete_matches": int(incomplete.sum()),
        "missing_surface": int(missing_surface.sum()),
        "duplicates": int(duplicate.sum()),
        "excluded_total": int(excluded.sum()),
        "source_revision": manifest.revision,
        "license": manifest.license,
        "source_digest": hashlib.sha256(
            json.dumps([entry.sha256 for entry in manifest.files]).encode()
        ).hexdigest(),
        "rows_by_year": frame.groupby(frame["date"].dt.year).size().to_dict(),
    }
    return (
        frame.loc[~excluded]
        .sort_values(["date", "tourney_id", "match_num"])
        .reset_index(drop=True),
        audit,
    )


def finite_number(row: pd.Series, key: str, default: float) -> float:
    """Missing statistics remain absent rather than becoming invented outcomes."""
    value = row.get(key, default)
    return float(value) if pd.notna(value) and np.isfinite(float(value)) else default


def observe_match(row: pd.Series, players: dict[int, Player]) -> None:
    """Update ratings and summaries once this date's features have been collected."""
    winner, loser = players[int(row["winner_id"])], players[int(row["loser_id"])]
    update_ratings(winner, loser, str(row["surface"]))
    for prefix, opposite, player in [("winner", "l", winner), ("loser", "w", loser)]:
        player.rank = max(1.0, finite_number(row, f"{prefix}_rank", player.rank))
        player.points = max(
            0.0, finite_number(row, f"{prefix}_rank_points", player.points)
        )
        player.age = finite_number(row, f"{prefix}_age", player.age)
        player.height = finite_number(row, f"{prefix}_ht", player.height)
        player.last_date = row["date"].date()
        side = "w" if prefix == "winner" else "l"
        won = finite_number(row, f"{side}_1stWon", 0) + finite_number(
            row, f"{side}_2ndWon", 0
        )
        total = finite_number(row, f"{side}_svpt", 0)
        other_won = finite_number(row, f"{opposite}_1stWon", 0) + finite_number(
            row, f"{opposite}_2ndWon", 0
        )
        other_total = finite_number(row, f"{opposite}_svpt", 0)
        if 0 <= won <= total and total > 0:
            player.serve.append((won, total))
        if 0 <= other_won <= other_total and other_total > 0:
            player.returns.append((other_total - other_won, other_total))


def build_dataset(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[int, Player]]:
    """Freeze all matches on each tournament date before applying any results."""
    players: dict[int, Player] = {}
    records: list[dict[str, object]] = []
    for day, batch in frame.groupby("date", sort=True):
        for _, row in batch.iterrows():
            winner, loser = int(row["winner_id"]), int(row["loser_id"])
            for player_id, prefix in [(winner, "winner"), (loser, "loser")]:
                if player_id not in players:
                    players[player_id] = Player(name=str(row[f"{prefix}_name"]))
            first, second = sorted([winner, loser])
            vector = match_vector(
                players[first],
                players[second],
                str(row["surface"]),
                int(row["best_of"]),
            )
            records.append(
                {
                    "date": day,
                    "year": day.year,
                    "surface": row["surface"],
                    "label": int(first == winner),
                    "features": vector,
                    "player1": players[first].name,
                    "player2": players[second].name,
                }
            )
        for _, row in batch.iterrows():
            observe_match(row, players)
    return pd.DataFrame(records), players


def player_index(players: dict[int, Player]) -> dict[str, int]:
    """Only unambiguous full names may resolve across schedule providers."""
    names: dict[str, list[int]] = {}
    for player_id, player in players.items():
        names.setdefault(normalize_name(player.name), []).append(player_id)
    return {name: values[0] for name, values in names.items() if len(values) == 1}
