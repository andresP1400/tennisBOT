"""Recent downloads do not make embargoed or missing statistics usable."""

import pandas as pd

from pipeline.result_freshness import point_statistics_dates


def test_stat_dates_distinguish_observed_from_mature_counts() -> None:
    today = pd.Timestamp.today().normalize()
    history = pd.DataFrame(
        {
            "date": [today - pd.Timedelta(days=40), today - pd.Timedelta(days=1)],
            **{
                f"{side}_{key}": [value, value]
                for side in ["w", "l"]
                for key, value in [("1stWon", 20), ("2ndWon", 10), ("svpt", 60)]
            },
        }
    )
    observed, applied = point_statistics_dates(history)
    assert observed == str((today - pd.Timedelta(days=1)).date())
    assert applied == str((today - pd.Timedelta(days=40)).date())


def test_partial_and_impossible_counts_do_not_claim_freshness() -> None:
    history = pd.DataFrame(
        {
            "date": [pd.Timestamp("2026-01-01")],
            "w_1stWon": [100],
            "w_2ndWon": [100],
            "w_svpt": [10],
            "l_1stWon": [10],
            "l_2ndWon": [5],
            "l_svpt": [30],
        }
    )
    assert point_statistics_dates(history) == (None, None)
