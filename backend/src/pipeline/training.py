"""Training module -- Stacking Ensemble with walk-forward CV.

Architecture:
  Layer 1 (Base Learners, trained with walk-forward CV on TRAIN):
    - LightGBM  (Bayesian tuning with Optuna)
    - XGBoost   (Bayesian tuning with Optuna)
    - Logistic Regression (calibrated baseline, no tuning)

  Layer 2 (Meta-Learner on VAL):
    - Logistic Regression (receives OOF probabilities from Layer 1)

  Post-processing:
    - Probability calibration (Platt or Isotonic) on VAL
"""

import os
import sys
import warnings
from typing import Any

import numpy as np
import pandas as pd
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

from logging_config import get_logger
logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.constants import ALL_FEATURES, ODDS_OPEN_FEATURES
from pipeline.split import fixed_temporal_split, walk_forward_splits
from pipeline.calibration import calibrate_probabilities

warnings.filterwarnings("ignore", category=UserWarning)


def _get_feature_columns(df: pd.DataFrame, use_odds: bool = False) -> list[str]:
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


def _prepare_data(df: pd.DataFrame, feature_cols: list[str]):
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


def _prepare_data_transform(df, feature_cols, imputer, scaler):
    """Transform data using pre-fitted imputer and scaler (no leakage)."""
    X = df[feature_cols].values.astype(float)
    y = df["label"].values.astype(int)
    X = imputer.transform(X)
    X = scaler.transform(X)
    return X, y


def _train_lgbm(X_train, y_train, X_val, y_val, use_optuna: bool = True, n_trials: int = 50):
    """Train LightGBM with optional Optuna Bayesian tuning."""
    import lightgbm as lgb
    best_params: dict[str, Any]
    if use_optuna:
        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)

            def objective(trial):
                params = {
                    "objective": "binary",
                    "metric": "binary_logloss",
                    "boosting_type": "gbdt",
                    "num_leaves": trial.suggest_int("num_leaves", 25, 50),
                    "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.07),
                    "feature_fraction": trial.suggest_float("feature_fraction", 0.6, 0.8),
                    "bagging_fraction": trial.suggest_float("bagging_fraction", 0.7, 0.9),
                    "bagging_freq": trial.suggest_int("bagging_freq", 1, 10),
                    "min_child_samples": trial.suggest_int("min_child_samples", 15, 30),
                    "reg_alpha": trial.suggest_float("reg_alpha", 0.05, 0.2),
                    "reg_lambda": trial.suggest_float("reg_lambda", 0.05, 0.2),
                    "verbose": -1,
                    "n_estimators": trial.suggest_int("n_estimators", 400, 600),
                }
                model = lgb.LGBMClassifier(**params)
                model.fit(
                    X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
                )
                preds = model.predict_proba(X_val)[:, 1]
                from sklearn.metrics import log_loss
                return log_loss(y_val, preds)

            study = optuna.create_study(direction="minimize")
            study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
            best_params = study.best_params
            best_params.update({
                "objective": "binary",
                "metric": "binary_logloss",
                "boosting_type": "gbdt",
                "verbose": -1,
            })
            logger.info(f"  LightGBM Optuna best logloss: {study.best_value:.5f}")
        except ImportError:
            logger.warning("  [WARN] Optuna not installed, using default params")
            best_params = config.LGBM_PARAMS.copy()
    else:
        best_params = config.LGBM_PARAMS.copy()
    model = lgb.LGBMClassifier(**best_params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )
    return model, best_params


def _train_xgboost(X_train, y_train, X_val, y_val, use_optuna: bool = True, n_trials: int = 50):
    """Train XGBoost with optional Optuna Bayesian tuning."""
    import xgboost as xgb
    best_params: dict[str, Any]
    if use_optuna:
        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)

            def objective(trial):
                params = {
                    "objective": "binary:logistic",
                    "eval_metric": "logloss",
                    "max_depth": trial.suggest_int("max_depth", 3, 5),
                    "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.07),
                    "subsample": trial.suggest_float("subsample", 0.7, 0.9),
                    "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 0.8),
                    "reg_alpha": trial.suggest_float("reg_alpha", 0.1, 0.3),
                    "reg_lambda": trial.suggest_float("reg_lambda", 0.5, 2.0),
                    "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
                    "n_estimators": trial.suggest_int("n_estimators", 400, 600),
                    "verbosity": 0,
                    "early_stopping_rounds": 50,
                }
                model = xgb.XGBClassifier(**params)
                model.fit(
                    X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    verbose=False,
                )
                preds = model.predict_proba(X_val)[:, 1]
                from sklearn.metrics import log_loss
                return log_loss(y_val, preds)

            study = optuna.create_study(direction="minimize")
            study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
            best_params = study.best_params
            best_params.update({
                "objective": "binary:logistic",
                "eval_metric": "logloss",
                "verbosity": 0,
                "early_stopping_rounds": 50,
            })
            logger.info(f"  XGBoost Optuna best logloss: {study.best_value:.5f}")
        except ImportError:
            logger.warning("  [WARN] Optuna not installed, using default params")
            best_params = config.XGB_PARAMS.copy()
    else:
        best_params = config.XGB_PARAMS.copy()
    model = xgb.XGBClassifier(**best_params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    return model, best_params


def _train_logistic(X_train, y_train):
    """Train Logistic Regression baseline. No tuning needed."""
    model = LogisticRegression(
        max_iter=1000,
        C=1.0,
        penalty="l2",
        solver="lbfgs",
    )
    model.fit(X_train, y_train)
    return model


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
        X_tr, y_tr = _prepare_data_transform(train_fold, feature_cols, imputer, scaler)
        X_vl, y_vl = _prepare_data_transform(val_fold, feature_cols, imputer, scaler)
        lgbm_model, _ = _train_lgbm(
            X_tr, y_tr, X_vl, y_vl,
            use_optuna=True, n_trials=max(10, n_optuna_trials // len(splits)),
        )
        pred_lgbm = lgbm_model.predict_proba(X_vl)[:, 1]
        xgb_model, _ = _train_xgboost(
            X_tr, y_tr, X_vl, y_vl,
            use_optuna=True, n_trials=max(10, n_optuna_trials // len(splits)),
        )
        pred_xgb = xgb_model.predict_proba(X_vl)[:, 1]
        lr_model = _train_logistic(X_tr, y_tr)
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
    X_full, y_full = _prepare_data_transform(df_train, feature_cols, imputer, scaler)
    split_idx = int(len(X_full) * 0.9)
    X_tr_final, X_es = X_full[:split_idx], X_full[split_idx:]
    y_tr_final, y_es = y_full[:split_idx], y_full[split_idx:]
    final_lgbm, lgbm_params = _train_lgbm(
        X_tr_final, y_tr_final, X_es, y_es,
        use_optuna=True, n_trials=n_optuna_trials,
    )
    final_xgb, xgb_params = _train_xgboost(
        X_tr_final, y_tr_final, X_es, y_es,
        use_optuna=True, n_trials=n_optuna_trials,
    )
    final_lr = _train_logistic(X_full, y_full)

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
    X, _ = _prepare_data_transform(df, feature_cols, imputer, scaler)
    p_lgbm = base_models["lgbm"].predict_proba(X)[:, 1]
    p_xgb = base_models["xgb"].predict_proba(X)[:, 1]
    p_lr = base_models["lr"].predict_proba(X)[:, 1]
    X_meta = np.column_stack([p_lgbm, p_xgb, p_lr])
    raw_probs = meta_model.predict_proba(X_meta)[:, 1]
    if calibrator is not None:
        return calibrator.predict(raw_probs.reshape(-1, 1))
    return raw_probs


def _symmetrize_probs(df_part: pd.DataFrame, probs: np.ndarray) -> np.ndarray:
    """Average each row's probability with the mirrored view of the same match."""
    match_ids = df_part["match_id"].astype(str)
    base = match_ids.str.rsplit("_", n=1).str[0]
    variant = match_ids.str.rsplit("_", n=1).str[1]
    mirror_key = base + "_" + np.where(variant == "A", "B", "A")
    prob_by_id = pd.Series(probs, index=match_ids.values)
    mirror_probs = prob_by_id.reindex(mirror_key.values).values
    return np.where(np.isnan(mirror_probs), probs, (probs + (1.0 - mirror_probs)) / 2.0)


def _benchmark_vs_market(df_test_single: pd.DataFrame, y_test: np.ndarray,
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


def train_pipeline(
    tour: str = "atp",
    n_optuna_trials: int = 50,
    start_year: int = None,
    end_year: int = None,
    use_odds: bool = False,
    model_name: str = None,
) -> dict:
    """Full training pipeline.

    Steps:
      1. Load feature dataset
      2. Temporal split (train / val / test)
      3. Fit imputer + scaler on TRAIN only
      4. Walk-forward OOF predictions (Layer 1)
      5. Train meta-learner on OOF (Layer 2)
      6. Calibrate on VAL set
      7. Evaluate on TEST set (ONE TIME ONLY)
      8. Save models and generate reports

    Pure-stats default: {tour}_stacking_model.pkl (and {tour}_model.pkl alias).
    Market-aware: {tour}_model_odds.pkl when use_odds=True.
    """
    logger.info("\n" + "#" * 70)
    logger.info("  TRAINING PIPELINE")
    logger.info("#" * 70)
    data_path = os.path.join(config.PROCESSED_DIR, f"{tour}_features.parquet")
    if not os.path.exists(data_path):
        raise FileNotFoundError(
            f"Feature dataset not found: {data_path}. Run `python main.py features` first."
        )
    df = pd.read_parquet(data_path)
    if start_year is not None:
        df = df[df["year"] >= start_year]
    if end_year is not None:
        df = df[df["year"] <= end_year]

    variant = "odds" if use_odds else "no-odds"
    if model_name is None:
        model_name = f"{tour}_model_odds.pkl" if use_odds else f"{tour}_stacking_model.pkl"
    logger.info(f"\n  Loaded {len(df):,} rows from {data_path} (Filter: {start_year}-{end_year})")
    logger.info(f"  Variant: {variant}  ->  {model_name}")
    feature_cols = _get_feature_columns(df, use_odds=use_odds)

    splits = fixed_temporal_split(df)
    df_train = splits["train"]
    df_val = splits["val"]
    df_test = splits["test"]

    logger.info("\n  Fitting imputer + scaler on TRAIN set only ...")
    X_train_raw = df_train[feature_cols].values.astype(float)
    imputer = SimpleImputer(strategy="median")
    imputer.fit(X_train_raw)
    scaler = StandardScaler()
    scaler.fit(imputer.transform(X_train_raw))

    oof_result = generate_oof_predictions(
        df_train, feature_cols, imputer, scaler, n_optuna_trials
    )

    meta_model = train_meta_learner(
        oof_result["oof_lgbm"],
        oof_result["oof_xgb"],
        oof_result["oof_lr"],
        oof_result["oof_y"],
    )

    logger.info("\n  Calibrating on validation set ...")
    val_probs_raw = predict_stacking(
        df_val, feature_cols, imputer, scaler,
        oof_result["models"], meta_model
    )
    val_probs_all = _symmetrize_probs(df_val, val_probs_raw)
    y_val_all = df_val["label"].values
    calibrator = calibrate_probabilities(val_probs_all, y_val_all)
    val_probs_all = calibrator.predict(val_probs_all.reshape(-1, 1))

    logger.info("\n  Predicting on TEST set (one-time evaluation) ...")
    test_probs_raw = predict_stacking(
        df_test, feature_cols, imputer, scaler,
        oof_result["models"], meta_model
    )
    test_probs_all = calibrator.predict(
        _symmetrize_probs(df_test, test_probs_raw).reshape(-1, 1)
    )
    y_test_all = df_test["label"].values

    logger.info("\n  De-duplicating to single matches for evaluation ...")
    def get_balanced_mask(dataset: pd.DataFrame) -> np.ndarray:
        try:
            base_ids = dataset["match_id"].str.split("_").str[0].astype(int)
        except ValueError:
            base_ids = pd.Series(range(len(dataset)))
        keep_a = (base_ids % 2 == 0) & dataset["match_id"].str.endswith("_A", na=False)
        keep_b = (base_ids % 2 != 0) & dataset["match_id"].str.endswith("_B", na=False)
        return (keep_a | keep_b).values

    val_single_mask = get_balanced_mask(df_val)
    val_probs = val_probs_all[val_single_mask]
    y_val = y_val_all[val_single_mask]
    logger.info(f"  VAL: {len(df_val):,} symmetric -> {val_single_mask.sum():,} single matches")
    test_single_mask = get_balanced_mask(df_test)
    test_probs = test_probs_all[test_single_mask]
    y_test = y_test_all[test_single_mask]
    df_test_single = df_test[test_single_mask]
    logger.info(f"  TEST: {len(df_test):,} symmetric -> {test_single_mask.sum():,} single matches")

    os.makedirs(config.MODELS_DIR, exist_ok=True)
    model_bundle = {
        "base_models": oof_result["models"],
        "meta_model": meta_model,
        "calibrator": calibrator,
        "imputer": imputer,
        "scaler": scaler,
        "feature_cols": feature_cols,
        "params": oof_result["params"],
        "use_odds": use_odds,
        "tour": tour,
    }
    model_path = os.path.join(config.MODELS_DIR, model_name)
    joblib.dump(model_bundle, model_path)
    logger.info(f"\n  Models saved to: {model_path}")

    # Keep legacy alias for pure-stats so older UI still finds stacking name
    if not use_odds and model_name != f"{tour}_stacking_model.pkl":
        alias = os.path.join(config.MODELS_DIR, f"{tour}_stacking_model.pkl")
        joblib.dump(model_bundle, alias)
        logger.info(f"  Alias saved to: {alias}")
    if not use_odds:
        pure_alias = os.path.join(config.MODELS_DIR, f"{tour}_model.pkl")
        joblib.dump(model_bundle, pure_alias)

    report_tour = f"{tour}_odds" if use_odds else tour
    from pipeline.evaluation import full_evaluation
    full_evaluation(
        y_test=y_test,
        test_probs=test_probs,
        y_val=y_val,
        val_probs=val_probs,
        df_test=df_test_single,
        feature_cols=feature_cols,
        lgbm_model=oof_result["models"]["lgbm"],
        imputer=imputer,
        tour=report_tour,
        total_matches=len(df),
    )

    _benchmark_vs_market(df_test_single, y_test, test_probs)

    try:
        from pipeline.betting_eval import full_betting_report
        reports_dir = os.path.join(config.REPORTS_DIR, report_tour)
        full_betting_report(df_test_single, y_test, test_probs, reports_dir=reports_dir)
    except Exception as exc:
        logger.warning(f"  Betting eval skipped: {exc}")

    return {
        "model_bundle": model_bundle,
        "test_probs": test_probs,
        "y_test": y_test,
        "val_probs": val_probs,
        "y_val": y_val,
        "oof_result": oof_result,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train stacking ensemble for tennis prediction")
    parser.add_argument("--tour", default="atp", choices=["atp", "wta"])
    parser.add_argument("--optuna-trials", type=int, default=50,
                        help="Number of Optuna trials per model (default: 50)")
    parser.add_argument("--use-odds", action="store_true",
                        help="Train the market-aware variant with opening odds")
    args = parser.parse_args()
    train_pipeline(args.tour, args.optuna_trials, use_odds=args.use_odds)
