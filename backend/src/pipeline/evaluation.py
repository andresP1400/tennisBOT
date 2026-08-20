"""Evaluation module -- metrics summary + full evaluation suite driver.

Chart generators live in pipeline/eval_charts.py; this module owns
print_metrics_summary() and full_evaluation().

Metrics (in order of importance):
  - Brier Score
  - Log-loss
  - ROC-AUC
  - Accuracy
"""
from __future__ import annotations

import os
import sys
from typing import Any

from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    classification_report,
    log_loss,
    roc_auc_score,
)

from logging_config import get_logger
from pipeline.eval_charts import (
    plot_brier_monthly,
    plot_calibration_curve,
    plot_feature_importance,
    plot_roc_curve,
    plot_shap_summary,
)

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402


def print_metrics_summary(y_true, y_pred_proba, label: str = "TEST") -> dict:
    """Print all key metrics for one split."""
    brier = brier_score_loss(y_true, y_pred_proba)
    ll = log_loss(y_true, y_pred_proba)
    auc = roc_auc_score(y_true, y_pred_proba)
    acc = accuracy_score(y_true, (y_pred_proba >= 0.5).astype(int))
    logger.info(f"\n  {'='*50}")
    logger.info(f"  METRICS SUMMARY ({label})")
    logger.info(f"  {'='*50}")
    logger.info(f"  Brier Score:  {brier:.5f}  (lower is better)")
    logger.info(f"  Log-loss:     {ll:.5f}  (lower is better)")
    logger.info(f"  ROC-AUC:      {auc:.5f}  (higher is better)")
    logger.info(f"  Accuracy:     {acc:.4f}  ({acc*100:.2f}%)")
    if auc > 0.80:
        logger.warning("\n  [WARNING] AUC > 0.80 detected! This may indicate data leakage.")
        logger.info("  Check feature importance and SHAP plots carefully.")
    elif auc > 0.72:
        logger.info("\n  [EXCELLENT] AUC in the 0.72-0.80 range -- top-tier model.")
    elif auc > 0.68:
        logger.info("\n  [GOOD] AUC > 0.68 -- competitive model.")
    else:
        logger.info("\n  [INFO] AUC < 0.68 -- room for improvement.")
    return {"brier": brier, "logloss": ll, "auc": auc, "accuracy": acc}


def full_evaluation(
    y_test,
    test_probs,
    y_val,
    val_probs,
    df_test,
    feature_cols,
    lgbm_model,
    tour: str = "atp",
    total_matches: int = 0,
    imputer: Any = None,
) -> None:
    """Run the complete evaluation suite."""
    logger.info("\n" + "#" * 70)
    logger.info("  EVALUATION SUITE")
    logger.info("#" * 70)
    reports_dir = os.path.join(config.REPORTS_DIR, tour)
    os.makedirs(reports_dir, exist_ok=True)
    test_metrics = print_metrics_summary(y_test, test_probs, label="TEST SET")
    val_metrics = print_metrics_summary(y_val, val_probs, label="VALIDATION SET")
    plot_roc_curve(y_test, test_probs, os.path.join(reports_dir, "1_roc_curve.png"))
    plot_calibration_curve(y_test, test_probs, os.path.join(reports_dir, "2_calibration_curve.png"))
    plot_feature_importance(lgbm_model, feature_cols, os.path.join(reports_dir, "3_feature_importance.png"))

    # Chart 4: SHAP -- use train-fitted imputer if available; refit on test
    # would leak test-set medians into the SHAP attributions.
    if imputer is None:
        fallback_imputer = SimpleImputer(strategy="median")
        X_test_raw = df_test[feature_cols].values.astype(float)
        X_test_imputed = fallback_imputer.fit_transform(X_test_raw)
    else:
        X_test_raw = df_test[feature_cols].values.astype(float)
        X_test_imputed = imputer.transform(X_test_raw)
    plot_shap_summary(
        lgbm_model, X_test_imputed, feature_cols,
        os.path.join(reports_dir, "4_shap_summary.png"),
    )

    if "tourney_date" in df_test.columns:
        plot_brier_monthly(
            y_test, test_probs, df_test["tourney_date"].values,
            os.path.join(reports_dir, "5_brier_monthly.png"),
        )

    import pandas as pd
    metrics_df = pd.DataFrame({
        "metric": ["brier", "logloss", "auc", "accuracy", "totalMatches", "testMatches"],
        "test": [
            test_metrics["brier"], test_metrics["logloss"],
            test_metrics["auc"], test_metrics["accuracy"],
            total_matches, len(y_test),
        ],
        "val": [
            val_metrics["brier"], val_metrics["logloss"],
            val_metrics["auc"], val_metrics["accuracy"],
            total_matches, len(y_val),
        ],
    })
    metrics_path = os.path.join(reports_dir, "metrics_summary.csv")
    metrics_df.to_csv(metrics_path, index=False)
    logger.info(f"\n  Metrics saved to: {metrics_path}")
    y_pred = (test_probs >= 0.5).astype(int)
    report = classification_report(y_test, y_pred, target_names=["Loss", "Win"])
    logger.info(f"\n  Classification Report (Test Set):\n{report}")
    report_path = os.path.join(reports_dir, "classification_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info(f"\n  All reports saved to: {reports_dir}")
