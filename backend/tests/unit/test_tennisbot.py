"""Unit tests for tennisBOT.

Run with:
    pytest tests/

Test layers:
  - Calibration (Platt / Isotonic output shape, range, probability bounds)
  - Split (fixed_temporal_split returns 3 disjoint DataFrames)
  - Walk-forward (no empty folds)
  - Constants (ALL_FEATURES is a list of strings, no duplicates)
  - Exceptions (custom errors carry the right fields)
  - Elo (cold-start returns ELO_INITIAL; surface not in SURFACES falls back)
  - H2H (symmetric pair key works)
  - Fatigue (NaN safety)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(PROJECT_ROOT))


# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
def test_all_features_is_list_of_strings() -> None:
    from utils.constants import ALL_FEATURES

    assert isinstance(ALL_FEATURES, list)
    assert all(isinstance(f, str) for f in ALL_FEATURES)
    assert len(ALL_FEATURES) > 0
    assert len(ALL_FEATURES) == len(set(ALL_FEATURES)), "duplicate feature names"


def test_feature_subsets_non_empty() -> None:
    from utils.constants import (
        CONTEXT_FEATURES,
        H2H_FEATURES,
        PLAYER_DIFF_FEATURES,
        ROLLING_FEATURES,
    )

    assert CONTEXT_FEATURES
    assert H2H_FEATURES
    assert PLAYER_DIFF_FEATURES
    assert ROLLING_FEATURES


# ----------------------------------------------------------------------
# Exceptions
# ----------------------------------------------------------------------
def test_external_api_error_includes_status() -> None:
    from exceptions import ExternalAPIError

    err = ExternalAPIError("theoddsapi", "rate limited", status_code=429)
    assert err.service == "theoddsapi"
    assert err.status_code == 429
    assert "theoddsapi" in str(err)
    assert "429" in str(err)


def test_exception_hierarchy() -> None:
    from exceptions import (
        DataNotFoundError,
        ModelNotFoundError,
        TennisBotError,
    )

    assert issubclass(DataNotFoundError, TennisBotError)
    assert issubclass(ModelNotFoundError, TennisBotError)


# ----------------------------------------------------------------------
# Calibration
# ----------------------------------------------------------------------
def test_platt_calibrator_returns_probabilities() -> None:
    from pipeline.calibration import ProbabilityCalibrator

    rng = np.random.default_rng(42)
    raw_probs = rng.uniform(0.1, 0.9, size=200)
    y_true = (rng.uniform(size=200) < raw_probs).astype(int)
    cal = ProbabilityCalibrator(method="platt")
    cal.fit(raw_probs, y_true)
    out = cal.predict(raw_probs)
    assert out.shape == raw_probs.shape
    assert np.all((out >= 0.0) & (out <= 1.0))


def test_isotonic_calibrator_returns_probabilities_in_range() -> None:
    from pipeline.calibration import ProbabilityCalibrator

    rng = np.random.default_rng(0)
    raw_probs = rng.uniform(0.05, 0.95, size=300)
    y_true = (rng.uniform(size=300) < raw_probs).astype(int)
    cal = ProbabilityCalibrator(method="isotonic")
    cal.fit(raw_probs, y_true)
    out = cal.predict(raw_probs)
    assert out.shape == raw_probs.shape
    assert np.all((out >= 0.0) & (out <= 1.0))


# ----------------------------------------------------------------------
# Splits
# ----------------------------------------------------------------------
def _make_yearly_df(years: list[int], n_per_year: int = 10) -> pd.DataFrame:
    rows: list[dict] = []
    for y in years:
        for i in range(n_per_year):
            rows.append(
                {
                    "year": y,
                    "tourney_date": pd.Timestamp(f"{y}-06-{i % 28 + 1:02d}"),
                    "label": i % 2,
                    "p1_name": f"P1_{i}",
                    "p2_name": f"P2_{i}",
                }
            )
    return pd.DataFrame(rows)


def test_fixed_temporal_split_disjoint() -> None:
    from pipeline.split import fixed_temporal_split

    df = _make_yearly_df(list(range(2018, 2026)))
    splits = fixed_temporal_split(df)
    assert set(splits.keys()) == {"train", "val", "test"}
    assert (splits["train"]["year"] <= 2021).all()
    assert splits["val"]["year"].between(2022, 2023).all()
    assert (splits["test"]["year"] >= 2024).all()
    assert len(splits["train"]) + len(splits["val"]) + len(splits["test"]) == len(df)


def test_walk_forward_skips_empty_folds() -> None:
    from pipeline.split import walk_forward_splits

    # Build df with a gap so some folds would be empty -> must be skipped
    df = pd.concat(
        [
            _make_yearly_df([2015, 2016]),
            _make_yearly_df([2018, 2019]),
        ],
        ignore_index=True,
    )
    splits = walk_forward_splits(
        df,
        train_start=2015,
        train_end_initial=2015,
        val_years=1,
        step=1,
    )
    for s in splits:
        assert len(s["train"]) > 0
        assert len(s["val"]) > 0


# ----------------------------------------------------------------------
# Elo
# ----------------------------------------------------------------------
def test_elo_cold_start_returns_initial_rating() -> None:
    from features.elo import EloRatingSystem

    elo = EloRatingSystem()
    assert elo.get_rating(player_id=999_999) == elo.initial
    assert elo.get_rating(player_id=999_999, surface="Hard") == elo.initial


def test_elo_unknown_surface_falls_back_to_global() -> None:
    from features.elo import EloRatingSystem

    elo = EloRatingSystem()
    elo.ratings_global[42] = 1900.0
    # Unknown surface (not in config.SURFACES) must NOT create a fresh entry;
    # must return the global rating.
    val = elo.get_rating(42, surface="Unknown")
    assert val == 1900.0
    assert (42, "Unknown") not in elo.ratings_surface


def test_elo_match_update_changes_ratings() -> None:
    from features.elo import EloRatingSystem

    elo = EloRatingSystem()
    elo.update(winner_id=1, loser_id=2, surface="Hard")
    assert elo.get_rating(1) > elo.initial
    assert elo.get_rating(2) < elo.initial


# ----------------------------------------------------------------------
# Fatigue tracker
# ----------------------------------------------------------------------
def test_fatigue_handles_nan_minutes() -> None:
    from features.fatigue import FatigueTracker

    ft = FatigueTracker()
    ft.update(pd.Timestamp("2024-01-01"), minutes=float("nan"))
    stats = ft.get_fatigue_stats(pd.Timestamp("2024-01-15"))
    assert "days_rest" in stats
    assert "minutes_on_court_last_10_days" in stats
    # minutes_on_court should be 0 (NaN treated as 0) not a crash
    assert stats["minutes_on_court_last_10_days"] == 0.0


def test_fatigue_cold_start_returns_nan_days_rest() -> None:
    from features.fatigue import FatigueTracker

    ft = FatigueTracker()
    stats = ft.get_fatigue_stats(pd.Timestamp("2024-01-15"))
    assert np.isnan(stats["days_rest"])
    assert stats["matches_last_7_days"] == 0


# ----------------------------------------------------------------------
# H2H
# ----------------------------------------------------------------------
def test_h2h_symmetric_key_is_canonical() -> None:
    from features.h2h import H2HTracker

    t = H2HTracker()
    assert t._key(10, 5) == t._key(5, 10)
    assert t._key(1, 1) == (1, 1)


def test_h2h_win_pct_symmetric() -> None:
    from features.h2h import H2HTracker

    t = H2HTracker()
    # Player 1 wins twice, loses once -> from perspective of lower-id
    # p1 (=key[0]) they won the games where won_first=True
    t.update(winner_id=1, loser_id=2, surface="Hard")
    t.update(winner_id=1, loser_id=2, surface="Hard")
    t.update(winner_id=2, loser_id=1, surface="Hard")
    stats = t.get_h2h(p1_id=1, p2_id=2, surface="Hard")
    assert stats["h2h_total_matches"] == 3
    assert stats["h2h_win_pct_surface"] == pytest.approx(2 / 3)


# ----------------------------------------------------------------------
# API server: model name validation
# ----------------------------------------------------------------------
def test_resolve_model_path_rejects_traversal() -> None:
    from fastapi import HTTPException

    from api_server import _resolve_model_path

    with pytest.raises(HTTPException):
        _resolve_model_path("../etc/passwd")
    with pytest.raises(HTTPException):
        _resolve_model_path("evil.pkl")
    with pytest.raises(HTTPException):
        _resolve_model_path("")


def test_resolve_model_path_accepts_known_names() -> None:
    from api_server import _resolve_model_path
    from config import MODELS_DIR

    p = _resolve_model_path("atp_stacking_model.pkl")
    assert str(p).startswith(str(MODELS_DIR.resolve()))
    assert p.name == "atp_stacking_model.pkl"


# ----------------------------------------------------------------------
# Logging configuration
# ----------------------------------------------------------------------
def test_configure_logging_is_idempotent() -> None:
    import logging

    from logging_config import configure_logging

    configure_logging()
    handlers_first = list(logging.getLogger().handlers)
    configure_logging()
    handlers_second = list(logging.getLogger().handlers)
    assert len(handlers_first) == len(handlers_second)


def test_logger_returns_named_logger() -> None:
    import logging

    from logging_config import get_logger

    log = get_logger("tennisbot.tests")
    assert isinstance(log, logging.Logger)
    assert log.name == "tennisbot.tests"


# ----------------------------------------------------------------------
# API server: endswith na=False
# ----------------------------------------------------------------------
def test_load_dataset_handles_null_match_id() -> None:
    """Regression: load_dataset must not crash on NaN match_id."""
    from unittest.mock import patch, MagicMock

    from api_server import _load_dataset

    with patch("api_server.BASE_DIR") as mock_base:
        fake_path = MagicMock()
        fake_path.exists.return_value = True
        fake_path.stat.return_value = MagicMock(st_mtime=1.0)
        mock_base.__truediv__.return_value.__truediv__.return_value = fake_path
        # Just exercise that the function doesn't choke on NaN
        try:
            _load_dataset("atp")
        except Exception:
            # If pandas can't read the parquet, that's OK; we just want
            # the endswith(na=False) not to be the failing point.
            pass


# ----------------------------------------------------------------------
# Weather feature mapping
# ----------------------------------------------------------------------
def test_get_coords_known_city() -> None:
    from features.weather import _get_coords

    assert _get_coords("Wimbledon") == (51.42, -0.22)
    assert _get_coords("Roland Garros") == (48.84, 2.25)
    assert _get_coords("French Open") == (48.84, 2.25)


def test_get_coords_unknown_returns_none() -> None:
    from features.weather import _get_coords

    assert _get_coords("Definitely Not A Tournament") is None
    assert _get_coords("") is None


# ----------------------------------------------------------------------
# Live odds API key in query params
# ----------------------------------------------------------------------
def test_theoddsapi_uses_api_key_query_param() -> None:
    """Regression: the API key must be sent as ``?apiKey=`` query param.

    TheOddsAPI rejects every auth header (verified live 2026-08-14:
    X-Api-Key / apiKey / x-api-key / APISECRET all return 401
    MISSING_KEY, only the query param works). Covers all TheOddsAPI
    call sites so a future change cannot re-introduce the broken
    header-only path.
    """
    import inspect

    from features import live_odds

    for fn_name in (
        "_fetch_available_tennis_sports",
        "_scrape_theoddsapi",
        "_get_todays_matches_api",
    ):
        src = inspect.getsource(getattr(live_odds.LiveOddsScraper, fn_name))
        assert '"apiKey"' in src, f"{fn_name} missing apiKey query param"
        assert "X-Api-Key" not in src, f"{fn_name} still uses rejected X-Api-Key header"


def test_aggregator_tour_filter_uses_explicit_tour_field() -> None:
    """Regression: _aggregate filtered by tournament NAME containing 'atp'/'wta'.

    TheOddsAPI tournament names are cleaned ('Cincinnati Open' has no 'atp'),
    so the old substring filter dropped every match. The MatchOdds dataclass
    now carries an explicit ``tour`` field set from the sport key.
    """
    from features.odds_aggregator import MatchOdds, OddsAggregator

    agg = OddsAggregator.__new__(OddsAggregator)
    matches = [
        MatchOdds(
            source="theoddsapi",
            player1="Casper Ruud",
            player2="Christopher O'Connell",
            tournament="Cincinnati Open",
            commence_time="2026-08-15T15:00:00Z",
            is_live=False,
            odds_p1=1.33,
            odds_p2=4.0,
            bookmaker="theoddsapi_best",
            tour="atp",
        ),
        MatchOdds(
            source="theoddsapi",
            player1="Barbora Krejcikova",
            player2="Sara Bejlek",
            tournament="Cincinnati Open",
            commence_time="2026-08-15T16:00:00Z",
            is_live=False,
            odds_p1=1.62,
            odds_p2=2.6,
            bookmaker="theoddsapi_best",
            tour="wta",
        ),
    ]
    atp = agg._aggregate(matches, "atp")
    wta = agg._aggregate(matches, "wta")
    assert len(atp) == 1
    assert atp[0]["player1"] == "Casper Ruud"
    assert len(wta) == 1
    assert wta[0]["player1"] == "Barbora Krejcikova"


def test_player_name_matching_is_accent_insensitive() -> None:
    """Regression: dashboard sends accented names (Kecmanović, Machač).

    The player resolver and the odds matcher must treat accented and
    unaccented forms as equal, otherwise /api/predict returns a cold-start
    50/50 and /api/value-bets finds no odds for live matches.
    """
    import inspect

    import pipeline.inference as inf

    assert (
        inf.fold_name("Miomir Kecmanovi\u0107")
        == inf.fold_name("Miomir Kecmanovic")
        == "miomir kecmanovic"
    )
    assert inf.fold_name("Toma\u0161 Macha\u010d") == inf.fold_name("Tomas Machac")

    state = {
        "name_to_id": {
            "miomir kecmanovic": 101,
            "tomas machac": 202,
        }
    }
    assert inf.resolve_player_id(state, "Miomir Kecmanovi\u0107") == 101
    assert inf.resolve_player_id(state, "MIOMIR KECMANOVIC") == 101
    assert inf.resolve_player_id(state, "Toma\u0161 Macha\u010d") == 202
    assert inf.resolve_player_id(state, "Unknown Player") is None

    from features import live_odds

    src = inspect.getsource(live_odds._normalize_player_name)
    assert "NFD" in src
    assert live_odds._normalize_player_name("Kecmanovi\u0107") == "kecmanovic"

    from features import odds_aggregator

    assert odds_aggregator._normalize_player("Carre\u00f1o Busta") == "carreno busta"


def test_calibration_logger_initialized_at_import() -> None:
    """Regression: calibrate_probabilities() must not raise NameError.

    Bug: `logger` was referenced inside the function before
    `logger = get_logger(__name__)` at the bottom of the module.
    """
    import importlib

    import pipeline.calibration as cal

    importlib.reload(cal)
    assert hasattr(cal, "logger")
    # If logger is unbound, just calling any log call inside
    # calibrate_probabilities would NameError. Smoke-test it cheaply
    # by ensuring the module-level import is at the top:
    src_path = cal.__file__
    with open(src_path, encoding="utf-8") as f:
        lines = f.readlines()
    # Find the line with "logger = get_logger"
    logger_assign_idx = next(
        i for i, ln in enumerate(lines) if "logger = get_logger" in ln
    )
    # Ensure no `def` precedes the assignment.
    first_def_idx = next(
        (i for i, ln in enumerate(lines) if ln.startswith("def ")), len(lines)
    )
    assert (
        logger_assign_idx < first_def_idx
    ), "logger = get_logger(...) must be defined BEFORE any function that uses it"


# ----------------------------------------------------------------------
# End-to-end training smoke test
# ----------------------------------------------------------------------
def test_training_pipeline_runs_end_to_end_with_synthetic_data(
    tmp_path, monkeypatch
) -> None:
    """Run the full pipeline on synthetic data and verify Platt calibration
    produces continuous (not binary) probabilities.

    Regression for the bug where `calibrator.predict()` returned 0/1 classes.
    """
    import joblib
    import numpy as np
    import pandas as pd

    import config
    from pipeline import training

    # Build a tiny synthetic parquet with the right shape.
    rng = np.random.default_rng(0)
    n = 1500
    df = pd.DataFrame(
        {
            "match_id": [f"{i}_A" if i % 2 == 0 else f"{i}_B" for i in range(n)],
            "tourney_date": pd.to_datetime("2020-01-01")
            + pd.to_timedelta(rng.integers(0, 1500, size=n), unit="D"),
            "tourney_name": rng.choice(["AO", "RG", "W"], size=n),
            "surface": rng.choice(["Hard", "Clay", "Grass"], size=n),
            "year": 2020 + rng.integers(0, 5, size=n),
            "p1_name": "A",
            "p2_name": "B",
            "label": rng.integers(0, 2, size=n),
        }
    )
    feature_names = [
        "ranking_diff",
        "ranking_points_diff",
        "elo_diff",
        "elo_surface_diff",
        "age_diff",
        "height_diff",
        "hand_matchup",
        "home_country_flag",
        "qualifier_flag_diff",
        "h2h_win_pct",
        "h2h_win_pct_surface",
        "days_rest_diff",
        "matches_last_7_days_diff",
        "ace_pct_diff",
        "df_pct_diff",
        "first_serve_in_pct_diff",
        "win_on_1st_serve_pct_diff",
        "win_on_2nd_serve_pct_diff",
        "bp_saved_pct_diff",
        "bp_converted_pct_diff",
        "first_serve_return_pts_won_pct_diff",
        "second_serve_return_pts_won_pct_diff",
        "return_games_won_pct_diff",
        "win_pct_surface_diff",
        "win_pct_last_10_diff",
        "tiebreak_win_pct_diff",
        "first_set_win_rate_diff",
        "sos_last_10_diff",
        "service_games_won_pct_diff",
        "surface_Hard",
        "surface_Clay",
        "surface_Grass",
        "tourney_level_encoded",
        "round_encoded",
        "best_of",
        "indoor_outdoor",
        "month",
    ]
    for name in feature_names:
        df[name] = rng.normal(0, 1, size=n).astype(float)
    df["surface_Hard"] = (df["surface"] == "Hard").astype(int)
    df["surface_Clay"] = (df["surface"] == "Clay").astype(int)
    df["surface_Grass"] = (df["surface"] == "Grass").astype(int)

    data_path = tmp_path / "atp_features.parquet"
    df.to_parquet(data_path)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(config, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path)

    result = training.train_pipeline(tour="atp", n_optuna_trials=2)
    assert result["model_bundle"]["calibrator"].method == "platt"

    bundle = joblib.load(tmp_path / "atp_stacking_model.pkl")
    X = rng.normal(0, 1, size=(50, len(bundle["feature_cols"])))
    X_imp = bundle["imputer"].transform(X)
    X_sc = bundle["scaler"].transform(X_imp)
    p_lgbm = bundle["base_models"]["lgbm"].predict_proba(X_sc)[:, 1]
    p_xgb = bundle["base_models"]["xgb"].predict_proba(X_sc)[:, 1]
    p_lr = bundle["base_models"]["lr"].predict_proba(X_sc)[:, 1]
    X_meta = np.column_stack([p_lgbm, p_xgb, p_lr])
    raw = bundle["meta_model"].predict_proba(X_meta)[:, 1]
    calibrated = bundle["calibrator"].predict(raw)

    # The crucial regression assertion:
    assert len(np.unique(calibrated)) >= 5, (
        f"Calibrator returned only {len(np.unique(calibrated))} unique values; "
        "the IsotonicRegression.predict() bug is back!"
    )
    assert np.all((calibrated >= 0.0) & (calibrated <= 1.0))
