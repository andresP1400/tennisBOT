"""Base-learner trainers for the stacking ensemble.

LightGBM and XGBoost support optional Optuna Bayesian tuning; Logistic
Regression is an untuned calibration baseline. Used by
generate_oof_predictions() in pipeline/train_helpers.py.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import numpy as np
import pandas as pd

from logging_config import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402


def train_lgbm(
    X_train: np.ndarray[Any, Any] | pd.DataFrame,
    y_train: np.ndarray[Any, Any] | pd.Series,
    X_val: np.ndarray[Any, Any] | pd.DataFrame,
    y_val: np.ndarray[Any, Any] | pd.Series,
    use_optuna: bool = True,
    n_trials: int = 50,
) -> tuple[Any, dict[str, Any]]:
    """Train LightGBM with optional Optuna Bayesian tuning."""
    import lightgbm as lgb

    best_params: dict[str, Any]
    if use_optuna:
        try:
            import optuna

            optuna.logging.set_verbosity(optuna.logging.WARNING)

            def objective(trial: Any) -> float:
                params = {
                    "objective": "binary",
                    "metric": "binary_logloss",
                    "boosting_type": "gbdt",
                    "num_leaves": trial.suggest_int("num_leaves", 25, 50),
                    "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.07),
                    "feature_fraction": trial.suggest_float(
                        "feature_fraction", 0.6, 0.8
                    ),
                    "bagging_fraction": trial.suggest_float(
                        "bagging_fraction", 0.7, 0.9
                    ),
                    "bagging_freq": trial.suggest_int("bagging_freq", 1, 10),
                    "min_child_samples": trial.suggest_int("min_child_samples", 15, 30),
                    "reg_alpha": trial.suggest_float("reg_alpha", 0.05, 0.2),
                    "reg_lambda": trial.suggest_float("reg_lambda", 0.05, 0.2),
                    "verbose": -1,
                    "n_estimators": trial.suggest_int("n_estimators", 400, 600),
                }
                model = lgb.LGBMClassifier(**params)
                model.fit(
                    X_train,
                    y_train,
                    eval_set=[(X_val, y_val)],
                    callbacks=[
                        lgb.early_stopping(50, verbose=False),
                        lgb.log_evaluation(0),
                    ],
                )
                preds = model.predict_proba(X_val)[:, 1]
                from sklearn.metrics import log_loss

                return log_loss(y_val, preds)  # type: ignore[no-any-return]

            study = optuna.create_study(direction="minimize")
            study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
            best_params = study.best_params
            best_params.update(
                {
                    "objective": "binary",
                    "metric": "binary_logloss",
                    "boosting_type": "gbdt",
                    "verbose": -1,
                }
            )
            logger.info(f"  LightGBM Optuna best logloss: {study.best_value:.5f}")
        except ImportError:
            logger.warning("  [WARN] Optuna not installed, using default params")
            best_params = config.LGBM_PARAMS.copy()
    else:
        best_params = config.LGBM_PARAMS.copy()
    model = lgb.LGBMClassifier(**best_params)
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )
    return model, best_params


def train_xgboost(
    X_train: np.ndarray[Any, Any] | pd.DataFrame,
    y_train: np.ndarray[Any, Any] | pd.Series,
    X_val: np.ndarray[Any, Any] | pd.DataFrame,
    y_val: np.ndarray[Any, Any] | pd.Series,
    use_optuna: bool = True,
    n_trials: int = 50,
) -> tuple[Any, dict[str, Any]]:
    """Train XGBoost with optional Optuna Bayesian tuning."""
    import xgboost as xgb

    best_params: dict[str, Any]
    if use_optuna:
        try:
            import optuna

            optuna.logging.set_verbosity(optuna.logging.WARNING)

            def objective(trial: Any) -> float:
                params = {
                    "objective": "binary:logistic",
                    "eval_metric": "logloss",
                    "max_depth": trial.suggest_int("max_depth", 3, 5),
                    "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.07),
                    "subsample": trial.suggest_float("subsample", 0.7, 0.9),
                    "colsample_bytree": trial.suggest_float(
                        "colsample_bytree", 0.6, 0.8
                    ),
                    "reg_alpha": trial.suggest_float("reg_alpha", 0.1, 0.3),
                    "reg_lambda": trial.suggest_float("reg_lambda", 0.5, 2.0),
                    "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
                    "n_estimators": trial.suggest_int("n_estimators", 400, 600),
                    "verbosity": 0,
                    "early_stopping_rounds": 50,
                }
                model = xgb.XGBClassifier(**params)
                model.fit(
                    X_train,
                    y_train,
                    eval_set=[(X_val, y_val)],
                    verbose=False,
                )
                preds = model.predict_proba(X_val)[:, 1]
                from sklearn.metrics import log_loss

                return log_loss(y_val, preds)  # type: ignore[no-any-return]

            study = optuna.create_study(direction="minimize")
            study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
            best_params = study.best_params
            best_params.update(
                {
                    "objective": "binary:logistic",
                    "eval_metric": "logloss",
                    "verbosity": 0,
                    "early_stopping_rounds": 50,
                }
            )
            logger.info(f"  XGBoost Optuna best logloss: {study.best_value:.5f}")
        except ImportError:
            logger.warning("  [WARN] Optuna not installed, using default params")
            best_params = config.XGB_PARAMS.copy()
    else:
        best_params = config.XGB_PARAMS.copy()
    model = xgb.XGBClassifier(**best_params)
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    return model, best_params


def train_logistic(
    X_train: np.ndarray[Any, Any] | pd.DataFrame,
    y_train: np.ndarray[Any, Any] | pd.Series,
) -> Any:
    """Train Logistic Regression baseline. No tuning needed."""
    from sklearn.linear_model import LogisticRegression

    model = LogisticRegression(
        max_iter=1000,
        C=1.0,
        penalty="l2",
        solver="lbfgs",
    )
    model.fit(X_train, y_train)
    return model
