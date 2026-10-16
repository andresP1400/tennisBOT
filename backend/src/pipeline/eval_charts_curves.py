"""Accuracy/calibration charts (split of pipeline/eval_charts.py)."""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve

from logging_config import get_logger
from pipeline.eval_charts_style import _setup_plot_style

logger = get_logger(__name__)


def plot_roc_curve(
    y_true: np.ndarray[Any, Any], y_pred_proba: np.ndarray[Any, Any], save_path: str
) -> None:
    """1. ROC Curve with AUC annotation."""
    _setup_plot_style()
    fig, ax = plt.subplots(figsize=(8, 8))
    fpr, tpr, _ = roc_curve(y_true, y_pred_proba)
    auc = roc_auc_score(y_true, y_pred_proba)
    ax.plot(fpr, tpr, color="#00d4ff", linewidth=2.5, label=f"Model (AUC = {auc:.4f})")
    ax.plot(
        [0, 1],
        [0, 1],
        "--",
        color="#ff4444",
        linewidth=1,
        alpha=0.7,
        label="Random (AUC = 0.5)",
    )
    ax.fill_between(fpr, tpr, alpha=0.1, color="#00d4ff")
    ax.set_xlabel("False Positive Rate", fontsize=13)
    ax.set_ylabel("True Positive Rate", fontsize=13)
    ax.set_title("ROC Curve", fontsize=16, fontweight="bold", pad=15)
    ax.legend(loc="lower right", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_xlim((-0.01, 1.01))
    ax.set_ylim((-0.01, 1.01))
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"  [Chart 1/5] ROC Curve saved to: {save_path}")


def plot_calibration_curve(
    y_true: np.ndarray[Any, Any],
    y_pred_proba: np.ndarray[Any, Any],
    save_path: str,
    n_bins: int = 10,
) -> None:
    """2. Calibration Curve -- predicted prob vs actual frequency."""
    _setup_plot_style()
    fig, ax = plt.subplots(figsize=(8, 8))
    fraction_of_positives, mean_predicted_value = calibration_curve(
        y_true, y_pred_proba, n_bins=n_bins, strategy="uniform"
    )
    ax.plot(
        mean_predicted_value,
        fraction_of_positives,
        "o-",
        color="#00ff88",
        linewidth=2.5,
        markersize=8,
        label="Model",
    )
    ax.plot(
        [0, 1],
        [0, 1],
        "--",
        color="#ff4444",
        linewidth=1,
        alpha=0.7,
        label="Perfect calibration",
    )
    ax.set_xlabel("Mean Predicted Probability", fontsize=13)
    ax.set_ylabel("Fraction of Positives", fontsize=13)
    ax.set_title("Calibration Curve", fontsize=16, fontweight="bold", pad=15)
    ax.legend(loc="upper left", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_xlim((-0.01, 1.01))
    ax.set_ylim((-0.01, 1.01))
    brier = brier_score_loss(y_true, y_pred_proba)
    ax.annotate(
        f"Brier = {brier:.4f}",
        xy=(0.7, 0.15),
        fontsize=14,
        fontweight="bold",
        color="#ffd700",
        bbox=dict(
            boxstyle="round,pad=0.3",
            facecolor="#2a2a4a",
            edgecolor="#ffd700",
            alpha=0.8,
        ),
    )
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"  [Chart 2/5] Calibration Curve saved to: {save_path}")


def plot_brier_monthly(
    y_true: np.ndarray[Any, Any],
    y_pred_proba: np.ndarray[Any, Any],
    dates: np.ndarray[Any, Any] | pd.Series,
    save_path: str,
) -> None:
    """5. Brier Score per month on test set.

    Checks stability over time (concept drift detection).
    Spike = concept drift (new generation, rule changes, etc.)
    """
    _setup_plot_style()
    df_brier = pd.DataFrame(
        {
            "y_true": y_true,
            "y_prob": y_pred_proba,
            "date": pd.to_datetime(dates),
        }
    )
    df_brier["year_month"] = df_brier["date"].dt.to_period("M")
    monthly = (
        df_brier.groupby("year_month")
        .apply(
            lambda g: (
                brier_score_loss(g["y_true"], g["y_prob"]) if len(g) > 5 else np.nan
            ),
            include_groups=False,
        )
        .dropna()
    )
    fig, ax = plt.subplots(figsize=(14, 6))
    x = range(len(monthly))
    bars = ax.bar(
        x,
        monthly.values,
        color="#00d4ff",
        edgecolor="#1a1a2e",
        alpha=0.85,
        width=0.8,
    )
    median_brier = monthly.median()
    for i, (bar, val) in enumerate(zip(bars, monthly.values)):
        if val > 1.5 * median_brier:
            bar.set_color("#ff4444")
            bar.set_alpha(1.0)
    avg = monthly.mean()
    ax.axhline(
        y=avg, color="#ffd700", linestyle="--", linewidth=2, label=f"Average: {avg:.4f}"
    )
    ax.set_xticks(x)
    ax.set_xticklabels(
        [str(p) for p in monthly.index], rotation=45, ha="right", fontsize=9
    )
    ax.set_xlabel("Month", fontsize=13)
    ax.set_ylabel("Brier Score", fontsize=13)
    ax.set_title(
        "Brier Score by Month (Test Set)", fontsize=16, fontweight="bold", pad=15
    )
    ax.legend(fontsize=12)
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"  [Chart 5/5] Monthly Brier Score saved to: {save_path}")
