"""pytest configuration: ensure project root is on sys.path + synthetic fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def make_matches(rows):
    """Build a minimal raw-match DataFrame from a list of dicts.

    Each row needs at least: tourney_date (YYYYMMDD int), winner_id, loser_id,
    surface, score, round. Stats columns default to NaN.
    """
    base_cols = {
        "tourney_id": "T", "tourney_name": "Test Open", "tourney_level": "A",
        "draw_size": 32, "best_of": 3, "match_num": 1, "minutes": 90,
        "winner_seed": np.nan, "winner_entry": np.nan, "winner_hand": "R",
        "winner_ht": 185, "winner_ioc": "ITA", "winner_age": 25,
        "winner_rank": 10, "winner_rank_points": 2000,
        "loser_seed": np.nan, "loser_entry": np.nan, "loser_hand": "R",
        "loser_ht": 185, "loser_ioc": "ESP", "loser_age": 25,
        "loser_rank": 20, "loser_rank_points": 1500,
    }
    stat_cols = [
        "w_ace", "w_df", "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon",
        "w_SvGms", "w_bpSaved", "w_bpFaced",
        "l_ace", "l_df", "l_svpt", "l_1stIn", "l_1stWon", "l_2ndWon",
        "l_SvGms", "l_bpSaved", "l_bpFaced",
    ]
    out = []
    for i, r in enumerate(rows):
        rec = dict(base_cols)
        rec.update({c: np.nan for c in stat_cols})
        rec.update(r)
        rec.setdefault("winner_name", f"Player {rec['winner_id']}")
        rec.setdefault("loser_name", f"Player {rec['loser_id']}")
        rec.setdefault("match_num", i + 1)
        out.append(rec)
    return pd.DataFrame(out)


@pytest.fixture
def cleaned_matches():
    """A small chronologically-ordered, parsed match set ready for features."""
    from features.cleaning import parse_dates

    rows = [
        {"tourney_date": 20230102, "winner_id": 1, "loser_id": 2, "surface": "Hard", "score": "6-3 6-4", "round": "R32"},
        {"tourney_date": 20230102, "winner_id": 3, "loser_id": 4, "surface": "Hard", "score": "7-6(3) 6-4", "round": "R32"},
        {"tourney_date": 20230109, "winner_id": 1, "loser_id": 3, "surface": "Hard", "score": "6-2 6-2", "round": "R16"},
        {"tourney_date": 20230116, "winner_id": 1, "loser_id": 2, "surface": "Clay", "score": "6-4 3-6 6-3", "round": "QF"},
        {"tourney_date": 20230123, "winner_id": 2, "loser_id": 3, "surface": "Clay", "score": "6-1 6-1", "round": "SF"},
    ]
    return parse_dates(make_matches(rows))
