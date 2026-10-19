"""Regression coverage for the restored chronological stacking contract."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from exceptions import TrainingError
from pipeline.calibration import ProbabilityCalibrator
from pipeline.oof_fitting import chronological_tail, fit_preprocessing
from pipeline.split import fixed_temporal_split, walk_forward_splits
from pipeline.symmetric_calibration import symmetric_calibration
from pipeline.temporal_groups import date_partitions
from pipeline.train_oof import generate_oof_predictions


def chronology():
    return pd.DataFrame(
        [
            {
                "tourney_date": day,
                "year": 2025,
                "match_id": f"{day}_{side}",
                "label": label,
                "feature": float(day),
            }
            for day in range(1, 13)
            for side, label in [("A", 1), ("B", 0)]
        ]
    )


def assert_separated(parts):
    for earlier, later in zip(parts, parts[1:]):
        assert earlier.tourney_date.max() < later.tourney_date.min()
        assert set(earlier.match_id).isdisjoint(later.match_id)
    assert sum(map(len, parts)) == 24


def test_adaptive_partitions_never_separate_same_day_mirrors():
    parts = fixed_temporal_split(chronology().sample(frac=1, random_state=42))
    assert_separated([parts["train"], parts["val"], parts["test"]])
    for split in walk_forward_splits(chronology()):
        assert split["train"].tourney_date.max() < split["val"].tourney_date.min()


def test_inner_stopping_and_invalid_chronology():
    train, stopping = chronological_tail(chronology())
    assert train.tourney_date.max() < stopping.tourney_date.min()
    with pytest.raises(TrainingError):
        chronological_tail(chronology().iloc[:2])
    with pytest.raises(TrainingError):
        date_partitions(chronology().iloc[:2], (0.7, 0.15, 0.15))


def test_fold_preprocessing_ignores_future_extremes_and_keeps_missing_columns():
    training = pd.DataFrame({"value": [1.0, 3.0, np.nan], "missing": [np.nan] * 3})
    imputer, scaler = fit_preprocessing(training, ["value", "missing"])
    np.testing.assert_allclose(imputer.statistics_, [2, 0])
    np.testing.assert_allclose(scaler.mean_, [2, 0])
    future = np.asarray([[1e9, np.nan]])
    assert scaler.transform(imputer.transform(future)).shape == (1, 2)
    np.testing.assert_allclose(scaler.mean_, [2, 0])


def test_outer_oof_never_passes_validation_rows_into_fitting(monkeypatch):
    import pipeline.train_oof as module

    frame = chronology()
    fitted_dates = []

    class Classifier:
        def predict_proba(self, values):
            return np.tile([0.3, 0.7], (len(values), 1))

    def fitting(training, columns, trials):
        fitted_dates.append(set(training.tourney_date))
        imputer, scaler = fit_preprocessing(training, columns)
        return SimpleNamespace(
            models={key: Classifier() for key in ("lgbm", "xgb", "lr")},
            imputer=imputer,
            scaler=scaler,
            params={},
        )

    monkeypatch.setattr(module, "fit_fold", fitting)
    result = generate_oof_predictions(
        frame, ["feature"], SimpleImputer(), StandardScaler(), 0
    )
    splits = walk_forward_splits(frame)
    for dates, split in zip(fitted_dates[:-1], splits):
        assert dates == set(split["train"].tourney_date)
        assert dates.isdisjoint(split["val"].tourney_date)
    assert fitted_dates[-1] == set(frame.tourney_date)
    assert len(result["oof_y"]) == sum(len(split["val"]) for split in splits)
    assert result["scaler"].mean_[0] == frame.feature.mean()


def test_nonlinear_calibration_is_order_invariant_after_symmetrization():
    class SquaredCalibrator:
        def predict(self, values):
            return values**2

    raw = np.asarray([0.1, 0.4, 0.8])
    calibrated = symmetric_calibration(raw, SquaredCalibrator())
    reverse = symmetric_calibration(1 - raw, SquaredCalibrator())
    np.testing.assert_allclose(calibrated + reverse, 1)
    np.testing.assert_allclose(calibrated, (raw**2 + 1 - (1 - raw) ** 2) / 2)
    np.testing.assert_array_equal(symmetric_calibration(raw, None), raw)


@pytest.mark.parametrize("method", ["isotonic", "platt"])
def test_calibration_shapes_and_invalid_values(method):
    values = np.asarray([0.1, 0.3, 0.6, 0.9])
    calibrator = ProbabilityCalibrator(method).fit(
        values[:, None], np.asarray([0, 0, 1, 1])
    )
    assert calibrator.predict(values[:, None]).shape == (4,)
    np.testing.assert_allclose(
        symmetric_calibration(values, calibrator)
        + symmetric_calibration(1 - values, calibrator),
        1,
    )
    for invalid in [np.asarray([np.nan]), np.asarray([1.2]), np.asarray([0.2])]:
        with pytest.raises(ValueError):
            ProbabilityCalibrator(method).fit(invalid, np.asarray([0, 1]))


def test_live_stacking_uses_identical_calibration_order_as_batch(monkeypatch):
    import api.predict_core as core
    import pipeline.inference as inference
    from api.schemas import PredictRequest

    class NonlinearCalibration:
        def predict(self, values):
            return values**3

    monkeypatch.setattr(inference, "resolve_player_id", lambda *args: None)
    monkeypatch.setattr(
        inference, "build_match_features", lambda *args, **kwargs: pd.DataFrame()
    )
    monkeypatch.setattr(
        inference, "assess_reliability", lambda *args: {"level": "low", "reasons": []}
    )
    probabilities = iter([0.9, 0.4])

    def raw_predict(bundle, row, calibrated=True):
        assert calibrated is False
        return next(probabilities)

    monkeypatch.setattr(core, "predict_proba_from_features", raw_predict)
    calibrator = NonlinearCalibration()
    result = core.predict_with_state(
        {"feature_cols": [], "calibrator": calibrator},
        {},
        PredictRequest(
            player1="One", player2="Two", surface="Hard", model="atp_model.pkl"
        ),
    )
    expected = symmetric_calibration(np.asarray([(0.9 + 1 - 0.4) / 2]), calibrator)[0]
    assert result["prob1"] == pytest.approx(expected)
    assert result["prob1"] + result["prob2"] == 1


def test_raw_cleaning_never_imputes_demographics_from_future_matches():
    from features.cleaning_transforms import impute_missing

    earlier = pd.DataFrame(
        {
            "winner_rank": [np.nan, 10.0],
            "loser_rank": [20.0, 30.0],
            "winner_ht": [np.nan, 180.0],
            "loser_ht": [170.0, np.nan],
            "winner_age": [np.nan, 25.0],
            "loser_age": [22.0, np.nan],
        }
    )
    future = earlier.iloc[[1]].copy()
    future[["winner_ht", "loser_ht", "winner_age", "loser_age"]] = 9999.0
    before = impute_missing(earlier)
    after = impute_missing(pd.concat([earlier, future], ignore_index=True))
    pd.testing.assert_frame_equal(before, after.iloc[: len(earlier)])
    assert np.isnan(before.iloc[0].winner_ht)
    assert np.isnan(before.iloc[0].winner_age)
    assert before.iloc[0].winner_rank == 2000
    assert np.isnan(earlier.iloc[0].winner_rank)
