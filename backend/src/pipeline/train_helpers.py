"""Training helpers: OOF generation, meta-learner, prediction, benchmarks.

Used by train_pipeline() in pipeline/training.py. Depends on the base
learner trainers in pipeline/learners.py.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

from logging_config import get_logger
from pipeline.learners import train_lgbm, train_xgboost, train_logistic

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.constants import ALL_FEATURES, ODDS_OPEN_FEATURES  # noqa: E402
from pipeline.split import walk_forward_splits  # noqa: E402


def get_feature_columns(df: pd.DataFrame, use_odds: bool = False) -> list[str]:
    """Return available feature columns that exist in df.

    use_odds=True adds opening-odds features (market-aware model variant).
    """
    wanted = ALL_FEATURES + (ODDS_OPEN_FEATURES if use_odds else [])
    available = [c for c in wanted if c in df.columns]
    logger.info(
        f"  Features available: {len(available)} / {len(wanted)}"
        f"{' (with opening odds)' if use_odds else ''}"
    )
    missing = [c for c in wanted if c not in df.columns]
    if missing:
        logger.info(f"  Missing features (will be skipped): {missing}")
    return available


def prepare_data(df: pd.DataFrame, feature_cols: list[str]):
    """Extract X, y from DataFrame. Impute NaN and scale.

    Returns X (np.ndarray), y (np.ndarray), imputer, scaler.
    """
    X = df[feature_cols].values.astype(float)
    y = df["label"].values.astype(int)
    imputer = SimpleImputer(strategy="median")
    X = imputer.fit_transform(X)
    scaler = StandardScaler()
    X = scaler.fit_transform(X)
    return X, y, imputer, scaler


def prepare_data_transform(df, feature_cols, imputer, scaler):
    """Transform data using pre-fitted imputer and scaler (no leakage)."""
    X = df[feature_cols].values.astype(float)
    y = df["label"].values.astype(int)
    X = imputer.transform(X)
    X = scaler.transform(X)
    return X, y


def generate_oof_predictions(
    df_train: pd.DataFrame,
    feature_cols: list[str],
    imputer,
    scaler,
    n_optuna_trials: int = 50,
) -> dict:
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
        raise RuntimeError(
            "Walk-forward produced no usable folds. Increase training data range."
        )

    oof_indices: list = []
    oof_lgbm: list = []
    oof_xgb: list = []
    oof_lr: list = []
    oof_y: list = []

    for fold_info in splits:
        fold = fold_info["fold"]
        train_fold = fold_info["train"]
        val_fold = fold_info["val"]
        logger.info(f"\n  --- Fold {fold}: train {fold_info['train_years']}, "
                    f"val {fold_info['val_years']} ---")
        X_tr, y_tr = prepare_data_transform(train_fold, feature_cols, imputer, scaler)
        X_vl, y_vl = prepare_data_transform(val_fold, feature_cols, imputer, scaler)
        lgbm_model, _ = train_lgbm(
            X_tr, y_tr, X_vl, y_vl,
            use_optuna=True, n_trials=max(10, n_optuna_trials // len(splits)),
        )
        pred_lgbm = lgbm_model.predict_proba(X_vl)[:, 1]
        xgb_model, _ = train_xgboost(
            X_tr, y_tr, X_vl, y_vl,
            use_optuna=True, n_trials=max(10, n_optuna_trials // len(splits)),
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
        logger.info(f"    LGBM: logloss={log_loss(y_vl, pred_lgbm):.4f}, "
                    f"AUC={roc_auc_score(y_vl, pred_lgbm):.4f}")
        logger.info(f"    XGB:  logloss={log_loss(y_vl, pred_xgb):.4f}, "
                    f"AUC={roc_auc_score(y_vl, pred_xgb):.4f}")
        logger.info(f"    LR:   logloss={log_loss(y_vl, pred_lr):.4f}, "
                    f"AUC={roc_auc_score(y_vl, pred_lr):.4f}")

    logger.info("\n  Training final models on full training set ...")
    X_full, y_full = prepare_data_transform(df_train, feature_cols, imputer, scaler)
    split_idx = int(len(X_full) * 0.9)
    X_tr_final, X_es = X_full[:split_idx], X_full[split_idx:]
    y_tr_final, y_es = y_full[:split_idx], y_full[split_idx:]
    final_lgbm, lgbm_params = train_lgbm(
        X_tr_final, y_tr_final, X_es, y_es,
        use_optuna=True, n_trials=n_optuna_trials,
    )
    final_xgb, xgb_params = train_xgboost(
        X_tr_final, y_tr_final, X_es, y_es,
        use_optuna=True, n_trials=n_optuna_trials,
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


def train_meta_learner(oof_lgbm, oof_xgb, oof_lr, oof_y) -> LogisticRegression:
    """Layer 2: Meta-learner trained on OOF predictions from Layer 1.

    Input: stacked probabilities from the 3 base learners.
    Output: Logistic Regression meta-model.
    """
    logger.info("\n" + "=" * 60)
    logger.info("  LAYER 2 -- Meta-Learner (Logistic Regression)")
    logger.info("=" * 60)
    X_meta = np.column_stack([oof_lgbm, oof_xgb, oof_lr])
    meta_model = LogisticRegression(max_iter=1000, C=0.5, solver="lbfgs")
    meta_model.fit(X_meta, oof_y)
    coefs = meta_model.coef_[0]
    logger.info("  Meta-learner weights:")
    logger.info(f"    LightGBM: {coefs[0]:.4f}")
    logger.info(f"    XGBoost:  {coefs[1]:.4f}")
    logger.info(f"    LogReg:   {coefs[2]:.4f}")
    from sklearn.metrics import log_loss, roc_auc_score
    meta_preds = meta_model.predict_proba(X_meta)[:, 1]
    logger.info(f"  OOF meta-learner: logloss={log_loss(oof_y, meta_preds):.4f}, "
                f"AUC={roc_auc_score(oof_y, meta_preds):.4f}")
    return meta_model


def predict_stacking(
    df: pd.DataFrame,
    feature_cols: list[str],
    imputer,
    scaler,
    base_models: dict,
    meta_model,
    calibrator=None,
) -> np.ndarray:
    """Generate predictions using the full stacking pipeline.

    Steps:
      1. Transform features (imputer + scaler fitted on train)
      2. Get Layer 1 probabilities from each base model
      3. Stack and pass to meta-learner
      4. Optionally calibrate final probabilities

    Returns np.ndarray of calibrated probabilities.
    """
    X, _ = prepare_data_transform(df, feature_cols, imputer, scaler)
    p_lgbm = base_models["lgbm"].predict_proba(X)[:, 1]
    p_xgb = base_models["xgb"].predict_proba(X)[:, 1]
    p_lr = base_models["lr"].predict_proba(X)[:, 1]
    X_meta = np.column_stack([p_lgbm, p_xgb, p_lr])
    raw_probs = meta_model.predict_proba(X_meta)[:, 1]
    if calibrator is not None:
        return calibrator.predict(raw_probs.reshape(-1, 1))
    return raw_probs


def symmetrize_probs(df_part: pd.DataFrame, probs: np.ndarray) -> np.ndarray:
    """Average each row's probability with the mirrored view of the same match."""
    match_ids = df_part["match_id"].astype(str)
    base = match_ids.str.rsplit("_", n=1).str[0]
    variant = match_ids.str.rsplit("_", n=1).str[1]
    mirror_key = base + "_" + np.where(variant == "A", "B", "A")
    prob_by_id = pd.Series(probs, index=match_ids.values)
    mirror_probs = prob_by_id.reindex(mirror_key.values).values
    return np.where(np.isnan(mirror_probs), probs, (probs + (1.0 - mirror_probs)) / 2.0)


def benchmark_vs_market(df_test_single: pd.DataFrame, y_test: np.ndarray,
                        test_probs: np.ndarray) -> None:
    """Compare the model against bookmaker opening odds when available."""
    if "p1_opening_odds" not in df_test_single.columns:
        return
    o1 = pd.to_numeric(df_test_single["p1_opening_odds"], errors="coerce").values
    o2 = pd.to_numeric(df_test_single["p2_opening_odds"], errors="coerce").values
    mask = (~np.isnan(o1)) & (~np.isnan(o2)) & (o1 > 1.0) & (o2 > 1.0)
    if mask.sum() < 50:
        logger.info("\n  [Benchmark] Not enough matches with odds for market comparison.")
        return
    inv1, inv2 = 1.0 / o1[mask], 1.0 / o2[mask]
    implied = inv1 / (inv1 + inv2)
    y = y_test[mask]
    p_model = np.clip(test_probs[mask], 1e-6, 1 - 1e-6)
    p_market = np.clip(implied, 1e-6, 1 - 1e-6)
    from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score, accuracy_score
    logger.info("\n  " + "=" * 50)
    logger.info(f"  BENCHMARK vs MARKET (opening odds, {mask.sum():,} test matches)")
    logger.info("  " + "=" * 50)
    for name, p in [("Model ", p_model), ("Market", p_market)]:
        logger.info(
            f"  {name}: logloss={log_loss(y, p):.5f}  brier={brier_score_loss(y, p):.5f}  "
            f"AUC={roc_auc_score(y, p):.5f}  acc={accuracy_score(y, p >= 0.5):.4f}"
        )
    gap = log_loss(y, p_model) - log_loss(y, p_market)
    logger.info(
        f"  Log-loss gap vs market: {gap:+.5f} "
        f"({'model BEATS market' if gap < 0 else 'market still ahead'})"
    )
