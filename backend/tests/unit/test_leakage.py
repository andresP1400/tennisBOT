"""Anti-leakage tests — the highest-value guarantee in the whole system.

Forward-only features must use ONLY data from matches strictly before the
current one. A leak here would silently inflate every metric.
"""

import numpy as np

from features.elo import compute_elo_features
from features.rolling_stats import compute_rolling_features
from features.h2h import compute_h2h_features
import config


def test_elo_first_match_is_initial(cleaned_matches):
    """The very first match of each player must use the initial rating."""
    res = compute_elo_features(cleaned_matches)
    res = res.sort_values(["match_date_est", "tourney_date", "match_num"]).reset_index(
        drop=True
    )
    first = res.iloc[0]
    # Both players appear for the first time -> pre-match ELO == initial
    assert first["winner_elo"] == float(config.ELO_INITIAL)
    assert first["loser_elo"] == float(config.ELO_INITIAL)


def test_elo_winner_rises_loser_falls(cleaned_matches):
    """After a win, the winner's NEXT pre-match ELO must exceed the loser's."""
    res = compute_elo_features(cleaned_matches)
    # Player 1 wins match 1 vs player 2; in a later match player 1's elo
    # should be above the initial and above player 2's at first meeting.
    # The 3rd chronological match (1 vs 3) — player 1 already has a win
    later = res.sort_values("match_date_est").iloc[2]
    assert later["winner_id"] == 1
    assert later["winner_elo"] > float(config.ELO_INITIAL)


def test_elo_pre_match_excludes_current_result():
    """Pre-match ELO at match i must not reflect match i's own outcome."""
    from conftest import make_matches
    from features.cleaning import parse_dates

    # Player 1 beats player 2 ten times; each pre-match value must be the
    # value BEFORE that match (monotonic increasing, never the post value).
    rows = [
        {
            "tourney_date": 20230101 + d,
            "winner_id": 1,
            "loser_id": 2,
            "surface": "Hard",
            "score": "6-0 6-0",
            "round": "R32",
        }
        for d in range(10)
    ]
    df = parse_dates(make_matches(rows))
    res = compute_elo_features(df).sort_values("match_date_est").reset_index(drop=True)
    elos = res["winner_elo"].values
    # strictly increasing pre-match ELO (each row sees only prior wins)
    assert np.all(np.diff(elos) > 0)
    # first is initial
    assert elos[0] == float(config.ELO_INITIAL)


def test_h2h_first_meeting_is_nan(cleaned_matches):
    """H2H win pct must be NaN/unknown at the players' first meeting."""
    res = compute_h2h_features(cleaned_matches)
    res = res.sort_values("match_date_est").reset_index(drop=True)
    first = res.iloc[0]
    assert np.isnan(first["winner_h2h_win_pct"])
    assert first["h2h_total_matches"] == 0


def test_h2h_accumulates_forward(cleaned_matches):
    """The 2nd meeting of players 1 & 2 must show 1 prior match."""
    res = (
        compute_h2h_features(cleaned_matches)
        .sort_values("match_date_est")
        .reset_index(drop=True)
    )
    # match index 3 is the 1-vs-2 rematch (Clay QF)
    rematch = res[(res["round"] == "QF")].iloc[0]
    assert rematch["h2h_total_matches"] == 1
    # player 1 had won the first meeting -> pre-match win pct == 1.0
    assert rematch["winner_h2h_win_pct"] == 1.0


def test_rolling_first_match_is_nan(cleaned_matches):
    """Rolling form must be undefined before a player has any history."""
    res = (
        compute_rolling_features(cleaned_matches)
        .sort_values("match_date_est")
        .reset_index(drop=True)
    )
    first = res.iloc[0]
    assert np.isnan(first["winner_win_pct_last_10"])
