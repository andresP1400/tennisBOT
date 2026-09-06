"""Shared matplotlib style for the evaluation charts (split of eval_charts.py)."""

import matplotlib

matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt


def _setup_plot_style() -> None:
    """Set a clean, professional plot style."""
    plt.rcParams.update(
        {
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
        }
    )
