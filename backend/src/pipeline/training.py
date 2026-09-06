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

The heavy lifting lives in pipeline/learners.py (model trainers) and
pipeline/train_helpers.py (OOF generation, meta-learner, prediction,
benchmarks); this module is the orchestration entry point.
"""

import os
import sys
import warnings
from typing import Any

import numpy as np
import pandas as pd
import joblib
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from logging_config import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from exceptions import DataNotFoundError  # noqa: E402
from pipeline.calibration import calibrate_probabilities  # noqa: E402
from pipeline.split import fixed_temporal_split  # noqa: E402
from pipeline.train_helpers import (  # noqa: E402
    benchmark_vs_market,
    get_feature_columns,
    predict_stacking,
    symmetrize_probs,
    train_meta_learner,
)
from pipeline.train_oof import generate_oof_predictions  # noqa: E402

warnings.filterwarnings("ignore", category=UserWarning)


def train_pipeline(
    tour: str = "atp",
    n_optuna_trials: int = 50,
    start_year: int | None = None,
    end_year: int | None = None,
    use_odds: bool = False,
    model_name: str | None = None,
) -> dict[str, Any]:
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
        raise DataNotFoundError(
            f"Feature dataset not found: {data_path}. Run `python main.py features` first."
        )
    df = pd.read_parquet(data_path)
    if start_year is not None:
        df = df[df["year"] >= start_year]
    if end_year is not None:
        df = df[df["year"] <= end_year]

    variant = "odds" if use_odds else "no-odds"
    if model_name is None:
        model_name = (
            f"{tour}_model_odds.pkl" if use_odds else f"{tour}_stacking_model.pkl"
        )
    logger.info(
        f"\n  Loaded {len(df):,} rows from {data_path} (Filter: {start_year}-{end_year})"
    )
    logger.info(f"  Variant: {variant}  ->  {model_name}")
    feature_cols = get_feature_columns(df, use_odds=use_odds)

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
        df_val, feature_cols, imputer, scaler, oof_result["models"], meta_model
    )
    val_probs_all = symmetrize_probs(df_val, val_probs_raw)
    y_val_all = df_val["label"].values
    calibrator = calibrate_probabilities(val_probs_all, y_val_all)
    val_probs_all = calibrator.predict(val_probs_all.reshape(-1, 1))

    logger.info("\n  Predicting on TEST set (one-time evaluation) ...")
    test_probs_raw = predict_stacking(
        df_test, feature_cols, imputer, scaler, oof_result["models"], meta_model
    )
    test_probs_all = calibrator.predict(
        symmetrize_probs(df_test, test_probs_raw).reshape(-1, 1)
    )
    y_test_all = df_test["label"].values

    logger.info("\n  De-duplicating to single matches for evaluation ...")

    def get_balanced_mask(dataset: pd.DataFrame) -> np.ndarray[Any, Any]:
        try:
            base_ids = dataset["match_id"].str.split("_").str[0].astype(int)
        except ValueError:
            base_ids = pd.Series(range(len(dataset)))
        keep_a = (base_ids % 2 == 0) & dataset["match_id"].str.endswith("_A", na=False)
        keep_b = (base_ids % 2 != 0) & dataset["match_id"].str.endswith("_B", na=False)
        return np.asarray((keep_a | keep_b).values)

    val_single_mask = get_balanced_mask(df_val)
    val_probs = val_probs_all[val_single_mask]
    y_val = y_val_all[val_single_mask]
    logger.info(
        f"  VAL: {len(df_val):,} symmetric -> {val_single_mask.sum():,} single matches"
    )
    test_single_mask = get_balanced_mask(df_test)
    test_probs = test_probs_all[test_single_mask]
    y_test = y_test_all[test_single_mask]
    df_test_single = df_test[test_single_mask]
    logger.info(
        f"  TEST: {len(df_test):,} symmetric -> {test_single_mask.sum():,} single matches"
    )

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

    benchmark_vs_market(df_test_single, y_test, test_probs)

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

    parser = argparse.ArgumentParser(
        description="Train stacking ensemble for tennis prediction"
    )
    parser.add_argument("--tour", default="atp", choices=["atp", "wta"])
    parser.add_argument(
        "--optuna-trials",
        type=int,
        default=50,
        help="Number of Optuna trials per model (default: 50)",
    )
    parser.add_argument(
        "--use-odds",
        action="store_true",
        help="Train the market-aware variant with opening odds",
    )
    args = parser.parse_args()
    train_pipeline(args.tour, args.optuna_trials, use_odds=args.use_odds)
