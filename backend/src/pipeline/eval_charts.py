"""Chart generators for the evaluation suite (5 fundamental analysis charts).

1. ROC Curve          -- AUC > 0.68 good, > 0.80 suspicious (leakage)
2. Calibration Curve  -- should follow diagonal
3. Feature Importance -- sanity check for leakage
4. SHAP Summary Plot  -- direction + magnitude of each feature
5. Brier Score Monthly-- stability over time (concept drift detection)

Thin facade (AGENT.md 300-line budget): implementations live in
pipeline/eval_charts_curves.py and pipeline/eval_charts_explain.py;
shared style in pipeline/eval_charts_style.py.
"""

from pipeline.eval_charts_curves import (  # noqa: F401
    plot_brier_monthly,
    plot_calibration_curve,
    plot_roc_curve,
)
from pipeline.eval_charts_explain import (  # noqa: F401
    plot_feature_importance,
    plot_shap_summary,
)

__all__ = [
    "plot_roc_curve",
    "plot_calibration_curve",
    "plot_feature_importance",
    "plot_shap_summary",
    "plot_brier_monthly",
]
