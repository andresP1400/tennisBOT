"""Walk-forward OOF generation for the stacking ensemble.

Split out of pipeline/train_helpers.py to respect the 300-line module
budget (AGENT.md).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from logging_config import get_logger
from pipeline.learners import train_lgbm, train_xgboost, train_logistic
from exceptions import TrainingError
from pipeline.split import walk_forward_splits
from pipeline.train_helpers import prepare_data_transform

logger = get_logger(__name__)


def generate_oof_predictions(
    df_train: pd.DataFrame,
    feature_cols: list[str],
    imputer: SimpleImputer,
    scaler: StandardScaler,
    n_optuna_trials: int = 50,
) -> dict[str, Any]:
    """Generate out-of-fold predictions using walk-forward CV on training data.

    Returns dict with:
      - 'oof_lgbm': np.array of OOF probabilities
      - 'oof_xgb':  np.array of OOF probabilities
      - 'oof_lr':   np.array of OOF probabilities
      - 'oof_y':    np.array of true labels (aligned with OOF)
      - 'models':   dict of final models (trained on full train)
    """
    logger.info("\n" + "=" * 60)
    logger.info("  LAYER 1 -- Base Learners (Walk-Forward OOF)")
    logger.info("=" * 60)
    splits = walk_forward_splits(
        df_train,
        train_start=df_train["year"].min(),
        train_end_initial=2015,
        val_years=1,
        step=1,
    )
    if not splits:
        raise TrainingError(
            "Walk-forward produced no usable folds. Increase training data range."
        )

    oof_indices: list[Any] = []
    oof_lgbm: list[Any] = []
    oof_xgb: list[Any] = []
    oof_lr: list[Any] = []
    oof_y: list[Any] = []

    for fold_info in splits:
        fold = fold_info["fold"]
        train_fold = fold_info["train"]
        val_fold = fold_info["val"]
        logger.info(
            f"\n  --- Fold {fold}: train {fold_info['train_years']}, "
            f"val {fold_info['val_years']} ---"
        )
        X_tr, y_tr = prepare_data_transform(train_fold, feature_cols, imputer, scaler)
        X_vl, y_vl = prepare_data_transform(val_fold, feature_cols, imputer, scaler)
        lgbm_model, _ = train_lgbm(
            X_tr,
            y_tr,
            X_vl,
            y_vl,
            use_optuna=True,
            n_trials=max(10, n_optuna_trials // len(splits)),
        )
        pred_lgbm = lgbm_model.predict_proba(X_vl)[:, 1]
        xgb_model, _ = train_xgboost(
            X_tr,
            y_tr,
            X_vl,
            y_vl,
            use_optuna=True,
            n_trials=max(10, n_optuna_trials // len(splits)),
        )
        pred_xgb = xgb_model.predict_proba(X_vl)[:, 1]
        lr_model = train_logistic(X_tr, y_tr)
        pred_lr = lr_model.predict_proba(X_vl)[:, 1]
        oof_indices.extend(val_fold.index.tolist())
        oof_lgbm.extend(pred_lgbm.tolist())
        oof_xgb.extend(pred_xgb.tolist())
        oof_lr.extend(pred_lr.tolist())
        oof_y.extend(y_vl.tolist())
        from sklearn.metrics import log_loss, roc_auc_score

        logger.info(
            f"    LGBM: logloss={log_loss(y_vl, pred_lgbm):.4f}, "
            f"AUC={roc_auc_score(y_vl, pred_lgbm):.4f}"
        )
        logger.info(
            f"    XGB:  logloss={log_loss(y_vl, pred_xgb):.4f}, "
            f"AUC={roc_auc_score(y_vl, pred_xgb):.4f}"
        )
        logger.info(
            f"    LR:   logloss={log_loss(y_vl, pred_lr):.4f}, "
            f"AUC={roc_auc_score(y_vl, pred_lr):.4f}"
        )

    logger.info("\n  Training final models on full training set ...")
    X_full, y_full = prepare_data_transform(df_train, feature_cols, imputer, scaler)
    split_idx = int(len(X_full) * 0.9)
    X_tr_final, X_es = X_full[:split_idx], X_full[split_idx:]
    y_tr_final, y_es = y_full[:split_idx], y_full[split_idx:]
    final_lgbm, lgbm_params = train_lgbm(
        X_tr_final,
        y_tr_final,
        X_es,
        y_es,
        use_optuna=True,
        n_trials=n_optuna_trials,
    )
    final_xgb, xgb_params = train_xgboost(
        X_tr_final,
        y_tr_final,
        X_es,
        y_es,
        use_optuna=True,
        n_trials=n_optuna_trials,
    )
    final_lr = train_logistic(X_full, y_full)

    return {
        "oof_lgbm": np.array(oof_lgbm),
        "oof_xgb": np.array(oof_xgb),
        "oof_lr": np.array(oof_lr),
        "oof_y": np.array(oof_y),
        "models": {
            "lgbm": final_lgbm,
            "xgb": final_xgb,
            "lr": final_lr,
        },
        "params": {
            "lgbm": lgbm_params,
            "xgb": xgb_params,
        },
    }
