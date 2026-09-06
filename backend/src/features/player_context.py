"""Player context from local Sackmann CSVs (rank, recent form, retirements, age).

Zero-scraping alternative to the ATP/WTA sites: rankings, recent results and
retirement marks are read from the raw CSVs refreshed by the weekly job.
Designed for the automatic daily card: one lookup per player, ~ms each.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any

from config import RAW_DIR
from logging_config import get_logger
from pipeline.inference import fold_name

logger = get_logger(__name__)

_rankings_cache: dict[str, dict[str, dict[str, Any]]] = {}
_players_cache: dict[str, dict[str, dict[str, Any]]] = {}
_recent_cache: dict[str, dict[str, list[dict[str, Any]]]] = {}
_form_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
_latest_rank_date: dict[str, str] = {}

_CONTEXT_FIELDS = [
    "rank",
    "rank_points",
    "age",
    "form",
    "ret",
    "last_match_date",
    "surface",
]


def _load_players(tour: str) -> dict[str, dict[str, Any]]:
    """player_id -> {name, dob} from {tour}_players.csv."""
    if tour in _players_cache:
        return _players_cache[tour]
    path = os.path.join(str(RAW_DIR), tour, f"{tour}_players.csv")
    players: dict[str, dict[str, Any]] = {}
    if not os.path.exists(path):
        _players_cache[tour] = players
        return players
    with open(path, encoding="utf-8", errors="replace") as f:
        import csv

        for row in csv.DictReader(f):
            pid = row.get("player_id", "")
            if not pid:
                continue
            players[pid] = {
                "name": f"{row.get('name_first', '')} {row.get('name_last', '')}".strip(),
                "dob": row.get("dob", ""),
                "hand": row.get("hand", ""),
                "ioc": row.get("ioc", ""),
            }
    _players_cache[tour] = players
    return players


def _load_rankings(tour: str) -> dict[str, dict[str, Any]]:
    """player_id -> {rank, points} from the latest ranking_date."""
    if tour in _rankings_cache:
        return _rankings_cache[tour]
    path = os.path.join(str(RAW_DIR), tour, f"{tour}_rankings_current.csv")
    result: dict[str, dict[str, Any]] = {}
    latest = _latest_rank_date.get(tour, "")
    if not os.path.exists(path):
        _rankings_cache[tour] = result
        return result
    with open(path, encoding="utf-8", errors="replace") as f:
        import csv

        for row in csv.DictReader(f):
            rdate = row.get("ranking_date", "")
            if rdate > latest:
                latest = rdate
    _latest_rank_date[tour] = latest
    with open(path, encoding="utf-8", errors="replace") as f:
        import csv

        for row in csv.DictReader(f):
            if row.get("ranking_date") != latest:
                continue
            pid = row.get("player", "")
            rank = row.get("rank", "")
            if not pid or not rank or not rank.isdigit():
                continue
            result[pid] = {
                "rank": int(rank),
                "rank_points": float(row.get("points", 0) or 0),
            }
    _rankings_cache[tour] = result
    return result


def _iter_match_files(tour: str) -> list[str]:
    """All {tour}_matches_YYYY.csv files in the raw dir."""
    raw_tour = os.path.join(str(RAW_DIR), tour)
    if not os.path.isdir(raw_tour):
        return []
    files = []
    for fn in os.listdir(raw_tour):
        if fn.startswith(f"{tour}_matches_") and fn.endswith(".csv"):
            files.append(os.path.join(raw_tour, fn))
    return sorted(files)


def _load_recent(tour: str) -> dict[str, list[dict[str, Any]]]:
    """player_id -> chronological recent matches {date, result, surface, ret}."""
    if tour in _recent_cache:
        return _recent_cache[tour]
    import csv

    result: dict[str, list[dict[str, Any]]] = {}
    for path in _iter_match_files(tour):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for row in csv.DictReader(f):
                    date_s = row.get("tourney_date", "")
                    score = (row.get("score") or "").upper()
                    surface = row.get("surface", "")
                    w = row.get("winner_id", "")
                    loser_id = row.get("loser_id", "")
                    ret = "RET" in score or "W/O" in score
                    if w:
                        result.setdefault(w, []).append(
                            {
                                "date": date_s,
                                "result": "W",
                                "surface": surface,
                                "ret": ret,
                            }
                        )
                    if loser_id:
                        result.setdefault(loser_id, []).append(
                            {
                                "date": date_s,
                                "result": "L",
                                "surface": surface,
                                "ret": ret,
                            }
                        )
        except Exception as exc:
            logger.warning("player_context: skipping %s: %s", path, exc)
    for matches in result.values():
        matches.sort(key=lambda m: m["date"])
    _recent_cache[tour] = result
    return result


def _age_from_dob(dob: str, ref: str = "") -> float | None:
    """Age in years from YYYYMMDD dob, or None when missing."""
    if not dob or len(dob) < 8:
        return None
    try:
        year, month, day = int(dob[:4]), int(dob[4:6]), int(dob[6:8])
        born = date(year, month, day)
        ref_date = date.today()
        if ref and len(ref) >= 8:
            ref_date = date(int(ref[:4]), int(ref[4:6]), int(ref[6:8]))
        return round((ref_date - born).days / 365.25, 1)
    except ValueError:
        return None


def _fold_map(tour: str) -> dict[str, str]:
    """folded name -> player_id (players csv, case/accent-insensitive).

    Sackmann data can contain duplicate player_ids for the same name; when
    that happens the candidate with the most recorded matches wins (it is the
    active one, e.g. Jakub Mensik appears twice with 11 vs 212 matches).
    """
    result: dict[str, str] = {}
    recent = _load_recent(tour)
    seen: dict[str, list[str]] = {}
    for pid, info in _load_players(tour).items():
        key = fold_name(info["name"])
        if key:
            seen.setdefault(key, []).append(pid)
    for key, pids in seen.items():
        best = max(pids, key=lambda p: len(recent.get(p, [])))
        result[key] = best
    return result


def player_context(
    tour: str,
    player_name: str,
    max_form: int = 5,
) -> dict[str, object]:
    """Best-effort context for one player: rank, age, recent form, ret marks.

    Returns {} when the player is unknown to the local dataset so callers can
    render the card row without context instead of failing.
    """
    key = (tour, fold_name(player_name), max_form)
    if key in _form_cache:
        return _form_cache[key]
    pid = _fold_map(tour).get(key[1])
    if pid is None:
        _form_cache[key] = {}
        return {}
    rankings = _load_rankings(tour)
    recent = _load_recent(tour)
    players = _load_players(tour)
    info = players.get(pid, {})
    rank_info = rankings.get(pid, {})
    matches = recent.get(pid, [])
    form = matches[-max_form:] if matches else []
    ctx: dict[str, Any] = {}
    if rank_info:
        ctx["rank"] = rank_info["rank"]
        ctx["rank_points"] = rank_info["rank_points"]
    age = _age_from_dob(info.get("dob", ""), _latest_rank_date.get(tour, ""))
    if age is not None:
        ctx["age"] = age
    if form:
        ctx["form"] = "".join(m["result"] for m in form)
        ctx["last_match_date"] = form[-1]["date"]
        ctx["ret"] = any(m["ret"] for m in form)
        ctx["surface"] = form[-1].get("surface", "")
    _form_cache[key] = ctx
    return ctx
