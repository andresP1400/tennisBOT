"""Fold-local preprocessing and inner chronological tuning for stacking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

import pandas as pd
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from exceptions import TrainingError
from pipeline.learners import train_lgbm, train_xgboost, train_logistic

Classifier: TypeAlias = LGBMClassifier | XGBClassifier | LogisticRegression


@dataclass
class FoldFit:
    models: dict[str, Classifier]
    imputer: SimpleImputer
    scaler: StandardScaler
    params: dict[str, dict[str, object]]


def chronological_tail(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Never split mirrored matches or a calendar group across early-stopping sets."""
    column = "tourney_date" if "tourney_date" in frame else "year"
    groups = sorted(frame[column].unique())
    if len(groups) < 2:
        raise TrainingError("At least two distinct chronological groups are required")
    boundary = groups[min(len(groups) - 1, max(1, int(len(groups) * 0.9)))]
    return frame[frame[column] < boundary], frame[frame[column] >= boundary]


def fit_preprocessing(
    frame: pd.DataFrame, columns: list[str]
) -> tuple[SimpleImputer, StandardScaler]:
    """Fit only the provided training slice, retaining all-missing feature columns."""
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    transformed = imputer.fit_transform(frame[columns].to_numpy(dtype=float))
    return imputer, StandardScaler().fit(transformed)


def tune_inside_fold(
    frame: pd.DataFrame, columns: list[str], trials: int
) -> tuple[LGBMClassifier, XGBClassifier, dict[str, dict[str, object]]]:
    """The stopping set is strictly inside the outer training data."""
    inner, stopping = chronological_tail(frame)
    inner_imputer, inner_scaler = fit_preprocessing(inner, columns)
    train_x = inner_scaler.transform(
        inner_imputer.transform(inner[columns].to_numpy(dtype=float))
    )
    stop_x = inner_scaler.transform(
        inner_imputer.transform(stopping[columns].to_numpy(dtype=float))
    )
    light, light_params = train_lgbm(
        train_x,
        inner.label.to_numpy(),
        stop_x,
        stopping.label.to_numpy(),
        use_optuna=trials > 0,
        n_trials=trials,
    )
    boosted, boosted_params = train_xgboost(
        train_x,
        inner.label.to_numpy(),
        stop_x,
        stopping.label.to_numpy(),
        use_optuna=trials > 0,
        n_trials=trials,
    )
    return light, boosted, {"lgbm": light_params, "xgb": boosted_params}


def fit_fold(frame: pd.DataFrame, columns: list[str], trials: int) -> FoldFit:
    """Refit selected estimators on all outer-training rows with fresh transforms."""
    light, boosted, params = tune_inside_fold(frame, columns, trials)
    imputer, scaler = fit_preprocessing(frame, columns)
    full_x = scaler.transform(imputer.transform(frame[columns].to_numpy(dtype=float)))
    light.set_params(
        n_estimators=max(1, int(light.best_iteration_ or light.n_estimators)),
        early_stopping_rounds=None,
    )
    boosted.set_params(
        n_estimators=int(boosted.best_iteration) + 1, early_stopping_rounds=None
    )
    light.fit(full_x, frame.label.to_numpy())
    boosted.fit(full_x, frame.label.to_numpy(), verbose=False)
    linear = train_logistic(full_x, frame.label.to_numpy())
    return FoldFit(
        {"lgbm": light, "xgb": boosted, "lr": linear},
        imputer,
        scaler,
        params,
    )
