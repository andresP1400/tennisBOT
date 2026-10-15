"""Opponent adjustment uses pre-event expectations and survives player reversal."""

import numpy as np
import pandas as pd
import pytest

from pipeline.personal_data import freeze_opponent_expectations, observe_match
from pipeline.personal_model import reversed_features
from pipeline.personal_state import Player, match_vector


def match():
    return pd.DataFrame(
        [
            dict(
                winner_id=1,
                loser_id=2,
                surface="Hard",
                date=pd.Timestamp("2020-01-01"),
                w_1stWon=35,
                w_2ndWon=25,
                w_svpt=100,
                l_1stWon=30,
                l_2ndWon=20,
                l_svpt=100,
            )
        ]
    )


def test_opponent_residuals_use_frozen_baselines_not_post_match_statistics():
    players = {1: Player("One", elo=1700), 2: Player("Two", elo=1300)}
    players[2].serve.append((80, 100))
    players[2].returns.append((30, 100))
    frame = freeze_opponent_expectations(match(), players)
    assert frame.iloc[0].winner_expected > 0.8
    assert frame.iloc[0].winner_expected_serve == pytest.approx(0.7)
    players[2].returns.append((100, 100))
    observe_match(frame.iloc[0], players)
    assert players[1].adjusted_serve[-1] == pytest.approx(-0.1)
    assert players[1].adjusted_return[-1] == pytest.approx(0.3)
    assert players[1].adjusted_results[-1] == pytest.approx(
        1 - frame.iloc[0].winner_expected
    )
    assert players[2].adjusted_results[-1] == -players[1].adjusted_results[-1]


def test_form_switch_preserves_all_other_features_and_extended_symmetry():
    first, second = Player("One"), Player("Two")
    first.results.extend([1, 1, 0])
    first.adjusted_results.extend([0.3, 0.4])
    first.adjusted_serve.extend([0.1, -0.02])
    first.adjusted_return.extend([0.2])
    full = np.asarray(match_vector(first, second, "Hard", feature_schema=2))
    reverse = np.asarray(match_vector(second, first, "Hard", feature_schema=2))
    np.testing.assert_allclose(reversed_features(full[None, :])[0], reverse)
    disabled = np.asarray(
        match_vector(first, second, "Hard", feature_schema=2, use_recent_form=False)
    )
    assert full.shape == disabled.shape == (18,)
    assert disabled[6] == disabled[15] == 0
    np.testing.assert_array_equal(
        np.delete(disabled, [6, 15]), np.delete(full, [6, 15])
    )
    assert len(match_vector(first, second, "Hard")) == 15


def test_unpickled_legacy_players_without_adjusted_fields_still_predict():
    first, second = Player("One"), Player("Two")
    for key in ("adjusted_results", "adjusted_serve", "adjusted_return"):
        delattr(first, key)
        delattr(second, key)
    assert match_vector(first, second, "Clay", feature_schema=2)[15:] == [0, 0, 0]


def test_versioned_artifacts_reload_identical_probabilities_without_erasing_previous(
    tmp_path, monkeypatch
):
    import joblib
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    import pipeline.personal_train as training
    from pipeline.personal_model import raw_probability, calibrate

    monkeypatch.setattr(training, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(training, "REPORTS_DIR", tmp_path / "reports")
    random = np.random.default_rng(42)
    features = random.normal(size=(80, 18))
    labels = (features[:, 0] > 0).astype(int)
    estimator = make_pipeline(LogisticRegression()).fit(features, labels)
    probability = raw_probability(estimator, features)
    calibrator = training.fit_calibrator(probability, labels)
    report = {
        "data_through": "2025-12-01",
        "feature_schema": 2,
        "use_recent_form": False,
        "test_2024_2025": {},
    }
    first = training.save_artifacts(
        "atp", "unit-test", estimator, calibrator, calibrator, {}, dict(report)
    )
    second = training.save_artifacts(
        "atp", "unit-test", estimator, calibrator, calibrator, {}, dict(report)
    )
    directory = tmp_path / "models/personal"
    assert first["model_version"] != second["model_version"]
    assert len(list(directory.glob("*.joblib"))) == 2
    restored = joblib.load(directory / f'{first["model_version"]}.joblib')
    assert restored.feature_schema == 2
    assert restored.use_recent_form is False
    np.testing.assert_array_equal(
        calibrate(restored.calibrator, raw_probability(restored.estimator, features)),
        calibrate(calibrator, probability),
    )
