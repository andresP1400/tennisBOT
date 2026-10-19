"""Completeness reports must expose missing data rather than impute it silently."""

import numpy as np
import pandas as pd

from data.history_quality import coverage


def test_quality_audit_separates_partial_invalid_and_complete_point_data():
    frame = pd.DataFrame(
        {
            "winner_id": [1, 1, np.nan],
            "loser_id": [2, 2, 2],
            "w_1stWon": [40, 40, 400],
            "w_2ndWon": [20, np.nan, 20],
            "w_svpt": [100, 100, 100],
            "l_1stWon": [30, 30, 30],
            "l_2ndWon": [20, 20, 20],
            "l_svpt": [100, 100, 100],
        }
    )
    report = coverage(frame)
    assert report["matches"] == 3
    assert report["w_complete_serve_counts"] == 1
    assert report["w_partial_serve_counts"] == 1
    assert report["l_complete_serve_counts"] == 3
    assert report["both_complete_serve_counts"] == 1
    assert report["missing_player_ids"] == 1
    assert report["identical_player_ids"] == 0
    assert report["missing_demographics"] == 3
