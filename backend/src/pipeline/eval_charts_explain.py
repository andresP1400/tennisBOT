"""Model-explainability charts (split of pipeline/eval_charts.py)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from logging_config import get_logger
from pipeline.eval_charts_style import _setup_plot_style

if TYPE_CHECKING:
    import lightgbm as lgb

logger = get_logger(__name__)


def plot_feature_importance(
    lgbm_model: lgb.LGBMClassifier,
    feature_cols: list[str],
    save_path: str,
    top_n: int = 25,
) -> None:
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
        if any(
            bad in feat_name.lower() for bad in ["id", "name", "match_id", "player_id"]
        ):
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
    ax.set_title(
        "Feature Importance (LightGBM)", fontsize=16, fontweight="bold", pad=15
    )
    ax.grid(True, axis="x", alpha=0.3)
    top_feats = [feature_cols[i] for i in indices[-5:]]
    suspicious = [
        f for f in top_feats if any(bad in f.lower() for bad in ["id", "name"])
    ]
    if suspicious:
        ax.annotate(
            f"LEAKAGE WARNING: {suspicious}",
            xy=(0.5, 0.02),
            xycoords="axes fraction",
            fontsize=14,
            fontweight="bold",
            color="#ff4444",
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


def plot_shap_summary(
    lgbm_model: lgb.LGBMClassifier,
    X_test: np.ndarray[Any, Any] | pd.DataFrame,
    feature_cols: list[str],
    save_path: str,
) -> None:
    """4. SHAP Summary Plot.

    Direction must be logical:
      elo_surface_diff high -> victory
      days_rest_diff negative -> fatigue = loss
    """
    try:
        import shap

        _setup_plot_style()
        plt.rcParams.update(plt.rcParamsDefault)  # type: ignore[attr-defined]
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
