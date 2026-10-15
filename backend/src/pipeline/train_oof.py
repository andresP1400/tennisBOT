"""Walk-forward stacking with outer folds untouched by tuning or preprocessing."""

from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from exceptions import TrainingError
from pipeline.split import walk_forward_splits
from pipeline.oof_fitting import fit_fold


def generate_oof_predictions(
    df_train: pd.DataFrame,
    feature_cols: list[str],
    imputer: SimpleImputer,
    scaler: StandardScaler,
    n_optuna_trials: int = 50,
) -> dict[str, Any]:
    """Ignore pre-fitted caller transforms; each fold owns its complete fitting state."""
    splits = walk_forward_splits(
        df_train, train_start=int(df_train.year.min()), train_end_initial=2015
    )
    if not splits:
        raise TrainingError("Walk-forward produced no usable chronological folds")
    predictions: dict[str, list[float]] = {name: [] for name in ("lgbm", "xgb", "lr")}
    labels: list[int] = []
    for fold in splits:
        fitted = fit_fold(
            fold["train"], feature_cols, max(0, n_optuna_trials // len(splits))
        )
        held_out = fold["val"]
        values = fitted.scaler.transform(
            fitted.imputer.transform(held_out[feature_cols].to_numpy(dtype=float))
        )
        for name, model in fitted.models.items():
            predictions[name].extend(
                np.asarray(model.predict_proba(values))[:, 1].tolist()
            )
        labels.extend(held_out.label.astype(int).tolist())
    final = fit_fold(df_train, feature_cols, n_optuna_trials)
    return {
        "oof_lgbm": np.asarray(predictions["lgbm"]),
        "oof_xgb": np.asarray(predictions["xgb"]),
        "oof_lr": np.asarray(predictions["lr"]),
        "oof_y": np.asarray(labels),
        "models": final.models,
        "params": final.params,
        "imputer": final.imputer,
        "scaler": final.scaler,
    }
