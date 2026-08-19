"""Tests for features.player_context (rank, form, ret, age from local CSVs)."""
from __future__ import annotations

import pytest

from features import player_context
from features.player_context import player_context as ctx_for

PLAYERS_CSV = "player_id,name_first,name_last,hand,dob,ioc,height,wikidata_id\n"
RANK_CSV = "ranking_date,rank,player,points\n"
MATCH_CSV = "tourney_date,tourney_name,surface,score,winner_id,loser_id\n"


def _make_raw(tmp_path, tour):
    """Create minimal raw CSVs for a tour under tmp_path."""
    raw = tmp_path / tour
    raw.mkdir(parents=True)
    (raw / f"{tour}_players.csv").write_text(
        PLAYERS_CSV
        + "1,Test,Alpha,R,19950115,USA,185,Q1\n"
        + "2,Test,Beta,R,19981201,GBR,190,Q2\n",
        encoding="utf-8",
    )
    (raw / f"{tour}_rankings_current.csv").write_text(
        RANK_CSV
        + "20260525,1,1,5000\n"
        + "20260525,2,2,4000\n"
        + "20260105,1,1,4800\n"
        + "20260105,2,2,3900\n",
        encoding="utf-8",
    )
    (raw / f"{tour}_matches_2026.csv").write_text(
        MATCH_CSV
        + "20260510,Test Open,Hard,6-3 6-4,1,2\n"
        + "20260511,Test Open,Clay,6-4 3-6 0-2 RET,2,1\n"
        + "20260512,Test Open,Grass,6-2 6-2,1,2\n"
        + "20260513,Test Open,Hard,6-1 6-1,1,2\n"
        + "20260514,Test Open,Clay,7-5 6-4,2,1\n",
        encoding="utf-8",
    )
    return raw


@pytest.fixture(autouse=True)
def _isolated_context(tmp_path, monkeypatch):
    """Point RAW_DIR at tmp CSVs and reset module caches."""
    monkeypatch.setattr(player_context, "RAW_DIR", tmp_path)
    for cache in (
        player_context._rankings_cache,
        player_context._players_cache,
        player_context._recent_cache,
        player_context._form_cache,
        player_context._latest_rank_date,
    ):
        cache.clear()
    yield


def test_context_rank_form_age_ret(tmp_path):
    _make_raw(tmp_path, "atp")
    ctx = ctx_for("atp", "Test Alpha")
    assert ctx["rank"] == 1
    assert ctx["rank_points"] == 5000
    assert ctx["form"] == "WLWWL"
    assert ctx["ret"] is True
    assert ctx["last_match_date"] == "20260514"
    assert ctx["surface"] == "Clay"
    assert ctx["age"] is not None


def test_context_unknown_player_returns_empty(tmp_path):
    _make_raw(tmp_path, "atp")
    assert ctx_for("atp", "Unknown Player") == {}


def test_context_accent_insensitive(tmp_path):
    _make_raw(tmp_path, "wta")
    (tmp_path / "wta" / "wta_players.csv").write_text(
        PLAYERS_CSV + "9,Nadia,Caffre,R,20000101,ITA,170,Q9\n",
        encoding="utf-8",
    )
    (tmp_path / "wta" / "wta_rankings_current.csv").write_text(
        RANK_CSV + "20260525,9,9,1000\n",
        encoding="utf-8",
    )
    (tmp_path / "wta" / "wta_matches_2026.csv").write_text(
        MATCH_CSV + "20260510,Test Open,Hard,6-3 6-4,9,10\n",
        encoding="utf-8",
    )
    for cache in (
        player_context._rankings_cache,
        player_context._players_cache,
        player_context._recent_cache,
        player_context._form_cache,
        player_context._latest_rank_date,
    ):
        cache.clear()
    ctx = ctx_for("wta", "Nadia Caffré")
    assert ctx["rank"] == 9
    assert ctx["form"] == "W"


def test_context_prefers_most_active_duplicate_id(tmp_path):
    """Sackmann duplicate IDs: the candidate with more matches must win."""
    _make_raw(tmp_path, "atp")
    # duplicate player 3 with same name but 2 matches
    (tmp_path / "atp" / "atp_players.csv").write_text(
        PLAYERS_CSV
        + "1,Test,Alpha,R,19950115,USA,185,Q1\n"
        + "2,Test,Beta,R,19981201,GBR,190,Q2\n"
        + "3,Test,Alpha,R,19950115,USA,185,Q3\n",
        encoding="utf-8",
    )
    with open(tmp_path / "atp" / "atp_matches_2026.csv", "a", encoding="utf-8") as f:
        f.write("20260515,Test Open,Hard,6-3 6-4,3,2\n")
        f.write("20260516,Test Open,Clay,6-3 6-4,3,2\n")
        f.write("20260517,Test Open,Hard,6-3 6-4,3,2\n")
        f.write("20260518,Test Open,Clay,6-3 6-4,3,2\n")
        f.write("20260519,Test Open,Hard,6-3 6-4,3,2\n")
        f.write("20260520,Test Open,Clay,6-3 6-4,3,2\n")
    for cache in (
        player_context._players_cache,
        player_context._recent_cache,
        player_context._form_cache,
    ):
        cache.clear()
    ctx = ctx_for("atp", "Test Alpha")
    assert ctx["last_match_date"] == "20260520"


def test_context_missing_files_returns_empty(tmp_path):
    assert ctx_for("atp", "Test Alpha") == {}
