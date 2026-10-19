"""Append audited result-only snapshots while keeping the original history immutable."""

from __future__ import annotations

from collections import Counter
import hashlib

import numpy as np
import pandas as pd

from data.result_adapters import abbreviated_results, official_wta_results
from data.result_identities import identity_aliases
from data.result_sources import acquire_source, source_for
from data.result_statistics import tml_results, retained_statistics
from pipeline.personal_state import SURFACES, normalize_name


def extension_results(
    history: pd.DataFrame, tour: str
) -> tuple[pd.DataFrame, dict[str, object]]:
    """A declared license and pinned bytes precede any provider result conversion."""
    source = source_for(tour)
    directory = acquire_source(source)
    if source.kind == "tml":
        candidates = tml_results(
            directory, tuple(source.members) + tuple(source.external_members)
        )
    else:
        adapter = {
            "abbreviated": abbreviated_results,
            "official_wta": official_wta_results,
        }[source.kind]
        candidates = adapter(directory)
    extra, exclusions = reconcile_results(history, candidates)
    return extra, {
        "dataset": source.dataset,
        "version": source.version,
        "license": source.license,
        "archive_sha256": source.sha256,
        "member_sha256": source.members,
        "external_files": {
            name: entry.model_dump() for name, entry in source.external_members.items()
        },
        "candidate_rows": len(candidates),
        "accepted_rows": len(extra),
        "exclusions": exclusions,
        "latest_accepted_date": (
            str(extra.date.max().date()) if not extra.empty else None
        ),
        "point_statistics_supplied": source.kind == "tml",
        "coverage": "Partial main-tour results; unresolved identities and potential overlaps withheld",
    }


def reconcile_results(
    history: pd.DataFrame, candidates: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Never infer fuzzy player identities or silently double-count overlapping sources."""
    aliases = identity_aliases(history)
    counts: Counter[str] = Counter()
    accepted: dict[tuple[str, int, int], dict[str, object]] = {}
    conflicts: set[tuple[str, int, int]] = set()
    for _, row in candidates.iterrows():
        first, second = aliases.get(normalize_name(str(row["first"]))), aliases.get(
            normalize_name(str(row["second"]))
        )
        reason = rejection_reason(row, first, second, history.date.max())
        if reason:
            counts[reason] += 1
            continue
        assert first is not None and second is not None
        key = str(row["source_id"]), min(first[0], second[0]), max(first[0], second[0])
        value = converted_result(row, first, second)
        if key in accepted:
            counts["duplicate_perspective"] += 1
            if value["winner_id"] != accepted[key]["winner_id"]:
                conflicts.add(key)
        else:
            accepted[key] = value
    counts["conflicting_outcomes"] = len(conflicts)
    frame = pd.DataFrame(
        [value for key, value in accepted.items() if key not in conflicts]
    )
    return remove_overlaps(history, frame, counts), dict(counts)


def rejection_reason(
    row: pd.Series,
    first: tuple[int, str] | None,
    second: tuple[int, str] | None,
    cutoff: pd.Timestamp,
) -> str | None:
    """No new record may change the already evaluated historical prefix."""
    day = row["date"]
    if pd.isna(day) or day > pd.Timestamp.today().normalize():
        return "invalid_or_future_date"
    if day <= cutoff:
        return "existing_historical_prefix"
    if first is None or second is None or first[0] == second[0]:
        return "unresolved_or_ambiguous_identity"
    score = str(row["score"])
    if row["surface"] not in SURFACES or not any(char.isdigit() for char in score):
        return "missing_surface_or_score"
    if any(code in score.upper() for code in ("RET", "W/O", "DEF", "ABN")):
        return "incomplete_result"
    return None


def converted_result(
    row: pd.Series, first: tuple[int, str], second: tuple[int, str]
) -> dict[str, object]:
    """Absent demographics and point counts remain missing; invalid rankings never become rank 1."""
    winner, loser = (first, second) if bool(row["winner_first"]) else (second, first)
    first_side, second_side = (1, 2) if bool(row["winner_first"]) else (2, 1)
    digest = hashlib.sha256(str(row["source_id"]).encode()).hexdigest()[:16]
    result: dict[str, object] = {
        "tourney_id": f"extension-{digest}",
        "tourney_name": str(row["event"]),
        "tourney_level": str(row.get("tourney_level", row.get("Series", "A"))),
        "round": str(row.get("round", row.get("Round", ""))),
        "source_event_id": str(row.get("tourney_id", row["source_id"])),
        "source_winner_id": str(row.get("winner_id", "")),
        "source_loser_id": str(row.get("loser_id", "")),
        "date": row["date"],
        "tourney_date": int(row["date"].strftime("%Y%m%d")),
        "surface": row["surface"],
        "score": str(row["score"]),
        "best_of": int(row["best_of"]),
        "match_num": 1,
        "winner_id": winner[0],
        "winner_name": winner[1],
        "loser_id": loser[0],
        "loser_name": loser[1],
    }
    result.update(retained_statistics(row))
    for prefix, side in (("winner", first_side), ("loser", second_side)):
        for key, minimum in (("rank", 1), ("points", 0)):
            value = pd.to_numeric(row.get(f"{key}{side}"), errors="coerce")
            suffix = "rank_points" if key == "points" else "rank"
            result[f"{prefix}_{suffix}"] = (
                float(value) if pd.notna(value) and value >= minimum else np.nan
            )
    return result


def remove_overlaps(
    history: pd.DataFrame, extra: pd.DataFrame, counts: Counter[str]
) -> pd.DataFrame:
    """Withhold possible same-pair rematches near the tournament-date boundary conservatively."""
    if extra.empty:
        return extra
    recent = history[history.date >= history.date.max() - pd.Timedelta(days=21)]
    keep = []
    for index, row in extra.iterrows():
        pair = (
            (recent.winner_id == row.winner_id) & (recent.loser_id == row.loser_id)
        ) | ((recent.winner_id == row.loser_id) & (recent.loser_id == row.winner_id))
        overlap = pair & ((row.date - recent.date).dt.days.between(0, 21))
        if overlap.any():
            counts["possible_legacy_overlap"] += 1
        else:
            keep.append(index)
    return extra.loc[keep].sort_values(["date", "tourney_id"]).reset_index(drop=True)
