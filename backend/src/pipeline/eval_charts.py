"""Chart generators for the evaluation suite (5 fundamental analysis charts).

  1. ROC Curve          -- AUC > 0.68 good, > 0.80 suspicious (leakage)
  2. Calibration Curve  -- should follow diagonal
  3. Feature Importance -- sanity check for leakage
  4. SHAP Summary Plot  -- direction + magnitude of each feature
  5. Brier Score Monthly-- stability over time (concept drift detection)
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve

from logging_config import get_logger

logger = get_logger(__name__)


def _setup_plot_style() -> None:
    """Set a clean, professional plot style."""
    plt.rcParams.update({
        "figure.facecolor": "#0f0f0f",
        "axes.facecolor": "#1a1a2e",
        "axes.edgecolor": "#3a3a5a",
        "axes.labelcolor": "#e0e0e0",
        "text.color": "#e0e0e0",
        "xtick.color": "#a0a0a0",
        "ytick.color": "#a0a0a0",
        "grid.color": "#2a2a4a",
        "grid.alpha": 0.5,
        "font.family": "sans-serif",
        "font.size": 11,
    })


def plot_roc_curve(y_true, y_pred_proba, save_path: str) -> None:
    """1. ROC Curve with AUC annotation."""
    _setup_plot_style()
    fig, ax = plt.subplots(figsize=(8, 8))
    fpr, tpr, _ = roc_curve(y_true, y_pred_proba)
    auc = roc_auc_score(y_true, y_pred_proba)
    ax.plot(fpr, tpr, color="#00d4ff", linewidth=2.5, label=f"Model (AUC = {auc:.4f})")
    ax.plot([0, 1], [0, 1], "--", color="#ff4444", linewidth=1, alpha=0.7, label="Random (AUC = 0.5)")
    ax.fill_between(fpr, tpr, alpha=0.1, color="#00d4ff")
    ax.set_xlabel("False Positive Rate", fontsize=13)
    ax.set_ylabel("True Positive Rate", fontsize=13)
    ax.set_title("ROC Curve", fontsize=16, fontweight="bold", pad=15)
    ax.legend(loc="lower right", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_xlim([-0.01, 1.01])
    ax.set_ylim([-0.01, 1.01])
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"  [Chart 1/5] ROC Curve saved to: {save_path}")


def plot_calibration_curve(y_true, y_pred_proba, save_path: str, n_bins: int = 10) -> None:
    """2. Calibration Curve -- predicted prob vs actual frequency."""
    _setup_plot_style()
    fig, ax = plt.subplots(figsize=(8, 8))
    fraction_of_positives, mean_predicted_value = calibration_curve(
        y_true, y_pred_proba, n_bins=n_bins, strategy="uniform"
    )
    ax.plot(
        mean_predicted_value, fraction_of_positives,
        "o-", color="#00ff88", linewidth=2.5, markersize=8, label="Model",
    )
    ax.plot([0, 1], [0, 1], "--", color="#ff4444", linewidth=1, alpha=0.7, label="Perfect calibration")
    ax.set_xlabel("Mean Predicted Probability", fontsize=13)
    ax.set_ylabel("Fraction of Positives", fontsize=13)
    ax.set_title("Calibration Curve", fontsize=16, fontweight="bold", pad=15)
    ax.legend(loc="upper left", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_xlim([-0.01, 1.01])
    ax.set_ylim([-0.01, 1.01])
    brier = brier_score_loss(y_true, y_pred_proba)
    ax.annotate(
        f"Brier = {brier:.4f}",
        xy=(0.7, 0.15), fontsize=14, fontweight="bold",
        color="#ffd700",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#2a2a4a", edgecolor="#ffd700", alpha=0.8),
    )
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"  [Chart 2/5] Calibration Curve saved to: {save_path}")


def plot_feature_importance(lgbm_model, feature_cols, save_path: str, top_n: int = 25) -> None:
    """3. Feature Importance from LightGBM.

    SANITY CHECK: if player_id or match_id are top features -> leakage.
    """
    _setup_plot_style()
    importances = lgbm_model.feature_importances_
    indices = np.argsort(importances)[-top_n:]
    fig, ax = plt.subplots(figsize=(10, 10))
    colors: list[str] = []
    for i in indices:
        feat_name = feature_cols[i]
        if any(bad in feat_name.lower() for bad in ["id", "name", "match_id", "player_id"]):
            colors.append("#ff4444")
        elif "elo" in feat_name.lower():
            colors.append("#00d4ff")
        elif "odds" in feat_name.lower():
            colors.append("#ffd700")
        else:
            colors.append("#00ff88")
    ax.barh(
        range(len(indices)),
        importances[indices],
        color=colors,
        edgecolor="#3a3a5a",
        height=0.7,
    )
    ax.set_yticks(range(len(indices)))
    ax.set_yticklabels([feature_cols[i] for i in indices], fontsize=10)
    ax.set_xlabel("Feature Importance (split count)", fontsize=13)
    ax.set_title("Feature Importance (LightGBM)", fontsize=16, fontweight="bold", pad=15)
    ax.grid(True, axis="x", alpha=0.3)
    top_feats = [feature_cols[i] for i in indices[-5:]]
    suspicious = [f for f in top_feats if any(bad in f.lower() for bad in ["id", "name"])]
    if suspicious:
        ax.annotate(
            f"LEAKAGE WARNING: {suspicious}",
            xy=(0.5, 0.02), xycoords="axes fraction",
            fontsize=14, fontweight="bold", color="#ff4444",
            ha="center",
            bbox=dict(boxstyle="round", facecolor="#330000", edgecolor="#ff4444"),
        )
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"  [Chart 3/5] Feature Importance saved to: {save_path}")
    logger.info("  Top 10 features:")
    for i in reversed(indices[-10:]):
        logger.info(f"    {feature_cols[i]}: {importances[i]}")


def plot_shap_summary(lgbm_model, X_test, feature_cols, save_path: str) -> None:
    """4. SHAP Summary Plot.

    Direction must be logical:
      elo_surface_diff high -> victory
      days_rest_diff negative -> fatigue = loss
    """
    try:
        import shap
        _setup_plot_style()
        plt.rcParams.update(plt.rcParamsDefault)
        explainer = shap.TreeExplainer(lgbm_model)
        shap_values = explainer.shap_values(X_test)
        if isinstance(shap_values, list):
            shap_vals = shap_values[1]
        else:
            shap_vals = shap_values
        plt.figure(figsize=(12, 10))
        shap.summary_plot(
            shap_vals,
            X_test,
            feature_names=feature_cols,
            show=False,
            max_display=20,
        )
        plt.title("SHAP Summary Plot", fontsize=16, fontweight="bold", pad=15)
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
        logger.info(f"  [Chart 4/5] SHAP Summary saved to: {save_path}")
    except ImportError:
        logger.warning("  [WARN] shap package not installed. Skipping SHAP plot.")
        logger.info("  Install with: pip install shap")
    except Exception as exc:
        logger.warning(f"  [WARN] SHAP plot failed: {exc}")


def plot_brier_monthly(y_true, y_pred_proba, dates, save_path: str) -> None:
    """5. Brier Score per month on test set.

    Checks stability over time (concept drift detection).
    Spike = concept drift (new generation, rule changes, etc.)
    """
    _setup_plot_style()
    df_brier = pd.DataFrame({
        "y_true": y_true,
        "y_prob": y_pred_proba,
        "date": pd.to_datetime(dates),
    })
    df_brier["year_month"] = df_brier["date"].dt.to_period("M")
    monthly = df_brier.groupby("year_month").apply(
        lambda g: brier_score_loss(g["y_true"], g["y_prob"]) if len(g) > 5 else np.nan,
        include_groups=False,
    ).dropna()
    fig, ax = plt.subplots(figsize=(14, 6))
    x = range(len(monthly))
    bars = ax.bar(
        x, monthly.values, color="#00d4ff",
        edgecolor="#1a1a2e", alpha=0.85, width=0.8,
    )
    median_brier = monthly.median()
    for i, (bar, val) in enumerate(zip(bars, monthly.values)):
        if val > 1.5 * median_brier:
            bar.set_color("#ff4444")
            bar.set_alpha(1.0)
    avg = monthly.mean()
    ax.axhline(y=avg, color="#ffd700", linestyle="--", linewidth=2,
               label=f"Average: {avg:.4f}")
    ax.set_xticks(x)
    ax.set_xticklabels([str(p) for p in monthly.index], rotation=45, ha="right", fontsize=9)
    ax.set_xlabel("Month", fontsize=13)
    ax.set_ylabel("Brier Score", fontsize=13)
    ax.set_title("Brier Score by Month (Test Set)", fontsize=16, fontweight="bold", pad=15)
    ax.legend(fontsize=12)
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"  [Chart 5/5] Monthly Brier Score saved to: {save_path}")
