"""
Professional evaluation metrics for a probabilistic betting model.

Adds, on top of the standard Brier / log-loss / AUC:
  - Expected Calibration Error (ECE)   -> single-number calibration quality
  - 95% bootstrap confidence intervals -> metrics aren't a single-split fluke
  - Flat-stake ROI (out-of-sample)     -> would value bets have made money?
  - Closing Line Value (CLV)           -> did we beat the closing line?

Metric math lives in pipeline/betting_metrics.py and pipeline/clv.py; this
module is the orchestration + markdown report layer and the public import
surface for tests.

HONESTY NOTES
-------------
* ROI is computed at a FIXED 1-unit stake on positive-EV bets only, on the
  held-out test set. It is indicative, not a promise — real betting faces
  limits, vig on the line you actually get, and the closing line being sharper.
* tennis-data provides one post-match odds snapshot per match. We use:
    opening = Pinnacle (sharp) -> Bet365 -> Avg
    closing = Avg (market consensus) -> Max -> Pinnacle
  CLV is labelled with the close source. True tick-by-tick Pinnacle open/close
  is not available in free data; Avg close is the best free consensus anchor.
"""

from __future__ import annotations

import os
import sys

from pipeline.betting_metrics import (
    bootstrap_ci,
    expected_calibration_error,
    flat_stake_roi,
    kelly_backtest,
    benchmark_vs_closing,
    segment_by_edge,
    simulate_bets,
    roi_with_ci,
)
from pipeline.clv import clv_closing, clv_proxy  # noqa: F401  (public re-export)

__all__ = [
    "full_betting_report",
    "clv_closing",
    "clv_proxy",
    "expected_calibration_error",
    "bootstrap_ci",
    "flat_stake_roi",
    "simulate_bets",
]


def full_betting_report(df_test_single, y_test, test_probs, reports_dir=None) -> dict:
    """Compute and print the professional metric suite. Writes a markdown
    summary to reports_dir if given. Safe when odds columns are absent."""
    if sys.stdout.encoding is None or sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print("\n  " + "=" * 52)
    print("  PROFESSIONAL EVALUATION (calibration - CI - ROI - CLV)")
    print("  " + "=" * 52)

    report: dict = {}

    # --- ECE ---
    ece = expected_calibration_error(y_test, test_probs)
    report["ece"] = round(ece, 4)
    print(f"  ECE (10-bin): {ece:.4f}   (lower = better calibrated)")

    # --- Bootstrap CIs ---
    print("\n  95% bootstrap confidence intervals (1000 resamples):")
    ci = {}
    for m in ["auc", "accuracy", "brier", "logloss"]:
        pt, lo, hi = bootstrap_ci(y_test, test_probs, metric=m)
        ci[m] = {"point": round(pt, 4), "lo": round(lo, 4), "hi": round(hi, 4)}
        print(f"    {m:>8}: {pt:.4f}  [{lo:.4f}, {hi:.4f}]")
    report["ci_95"] = ci

    # --- ROI + CLV (need odds) ---
    cols = df_test_single.columns
    if "p1_opening_odds" in cols and "p2_opening_odds" in cols:
        import pandas as pd
        o1 = pd.to_numeric(df_test_single["p1_opening_odds"], errors="coerce").values
        o2 = pd.to_numeric(df_test_single["p2_opening_odds"], errors="coerce").values
        roi = flat_stake_roi(y_test, test_probs, o1, o2)
        report["roi"] = roi
        print("\n  Flat-stake ROI (positive-EV bets, out-of-sample):")
        print(f"    bets={roi['bets']}  profit={roi['profit_units']}u  "
              f"ROI={roi['roi_pct']}%  hit={roi['hit_rate_pct']}%")

        close_p1 = close_p2 = None
        if "p1_closing_odds" in cols and "p2_closing_odds" in cols:
            close_p1 = pd.to_numeric(df_test_single["p1_closing_odds"], errors="coerce").values
            close_p2 = pd.to_numeric(df_test_single["p2_closing_odds"], errors="coerce").values

            clv = clv_closing(test_probs, o1, o2, close_p1, close_p2, close_source="closing")
            report["clv"] = clv
            # keep proxy key for backward-compatible consumers
            report["clv_proxy"] = {
                "bets": clv["bets"],
                "avg_clv_proxy": clv["avg_clv"],
                "beat_rate_pct": clv["beat_rate_pct"],
                "note": clv["note"],
            }
            print(f"\n  CLV (open -> closing line): bets={clv['bets']}  "
                  f"avg={clv['avg_clv']}  median={clv['median_clv']}  "
                  f"beat_rate={clv['beat_rate_pct']}%")
            print(f"    [{clv['note']}]")

            # Bet-level simulation with CLV, edge bands, Kelly, vs-close benchmark
            bets = simulate_bets(y_test, test_probs, o1, o2, close_p1, close_p2)
            if bets:
                report["roi_ci"] = roi_with_ci(bets)
                report["edge_segments"] = segment_by_edge(bets)
                report["kelly"] = kelly_backtest(bets)
                print(f"\n  ROI with CI: {report['roi_ci']}")
                print(f"  Edge segments: {report['edge_segments']}")
                print(f"  Kelly (1/4): {report['kelly']}")

            bench = benchmark_vs_closing(y_test, test_probs, close_p1, close_p2)
            if bench:
                report["vs_closing"] = bench
                print(f"\n  Model vs closing market: "
                      f"beats_logloss={bench['beats_closing_logloss']}  "
                      f"model_ll={bench['model']['logloss']}  "
                      f"close_ll={bench['closing']['logloss']}  n={bench['n']}")
    else:
        print("\n  ROI/CLV skipped (no odds in this model variant).")

    # --- write markdown ---
    if reports_dir:
        os.makedirs(reports_dir, exist_ok=True)
        path = os.path.join(reports_dir, "betting_metrics.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(_to_markdown(report))
        print(f"\n  Betting metrics written to: {path}")

    return report


def _to_markdown(r: dict) -> str:
    def _f(v):
        """Render np.float64 / int cleanly without the numpy repr wrapper."""
        import numpy as np
        if isinstance(v, np.generic):
            return v.item()
        return v
    lines = ["# Professional evaluation metrics\n"]
    lines.append(f"**Expected Calibration Error (ECE, 10-bin):** {_f(r.get('ece'))}  ")
    lines.append("_Lower is better; measures how well predicted probabilities match reality._\n")
    if "ci_95" in r:
        lines.append("## 95% confidence intervals (bootstrap)\n")
        lines.append("| Metric | Estimate | 95% CI |")
        lines.append("| :-- | :-: | :-: |")
        for m, v in r["ci_95"].items():
            lines.append(f"| {m} | {_f(v['point'])} | [{_f(v['lo'])}, {_f(v['hi'])}] |")
        lines.append("")
    if "roi" in r:
        roi = r["roi"]
        lines.append("## Flat-stake ROI (out-of-sample, positive-EV bets)\n")
        lines.append(f"- Bets placed: **{_f(roi['bets'])}**")
        lines.append(f"- Profit: **{_f(roi['profit_units'])} units**")
        lines.append(f"- ROI: **{_f(roi['roi_pct'])}%**")
        lines.append(f"- Hit rate: **{_f(roi['hit_rate_pct'])}%**")
        lines.append("\n_1-unit flat stakes, settled on real outcomes. Indicative only:_")
        lines.append("_real betting faces stake limits and the closing line being sharper._\n")
    if "roi_ci" in r and r["roi_ci"].get("bets", 0):
        rc = r["roi_ci"]
        lo, hi = rc["roi_ci95"]
        lines.append("## ROI bootstrap CI\n")
        lines.append(f"- ROI: **{_f(rc['roi_pct'])}%**  95% CI: **[{_f(lo)}, {_f(hi)}]**")
        lines.append(f"- p(ROI<=0): **{_f(rc['p_value_roi_le_0'])}** - "
                     f"significant@5%: **{_f(rc['significant_5pct'])}**\n")
    if "clv" in r:
        clv = r["clv"]
        lines.append("## Closing Line Value (open -> close)\n")
        lines.append(
            f"- Bets: **{_f(clv['bets'])}** - avg CLV: **{_f(clv['avg_clv'])}** - "
            f"median: **{_f(clv.get('median_clv'))}** - beat rate: **{_f(clv['beat_rate_pct'])}%**"
        )
        lines.append(f"- Close source: **{_f(clv.get('close_source', 'closing'))}**")
        lines.append(f"\n> {clv['note']}\n")
    elif "clv_proxy" in r:
        clv = r["clv_proxy"]
        lines.append("## Closing Line Value\n")
        lines.append(f"- Bets: **{_f(clv['bets'])}** - avg CLV: **{_f(clv.get('avg_clv_proxy'))}** - "
                     f"beat rate: **{_f(clv['beat_rate_pct'])}%**")
        lines.append(f"\n> {clv.get('note', '')}\n")
    if "edge_segments" in r and r["edge_segments"]:
        lines.append("## ROI / CLV by model edge band\n")
        lines.append("| Edge | Bets | ROI% | Hit% | Avg CLV | CLV beat% |")
        lines.append("| :-- | :-: | :-: | :-: | :-: | :-: |")
        for s in r["edge_segments"]:
            lines.append(
                f"| {s['edge_band']} | {_f(s['bets'])} | {_f(s['roi_pct'])} | "
                f"{_f(s['hit_pct'])} | {_f(s['avg_clv'])} | {_f(s['clv_beat_pct'])} |"
            )
        lines.append("")
    if "kelly" in r and r["kelly"].get("bets", 0):
        k = r["kelly"]
        lines.append("## Fractional Kelly (0.25)\n")
        lines.append(f"- Final bankroll: **{_f(k['final_bankroll'])}** "
                     f"(growth **{_f(k['growth_x'])}x**, max DD **{_f(k['max_drawdown_pct'])}%**)\n")
    if "vs_closing" in r and r["vs_closing"]:
        b = r["vs_closing"]
        lines.append("## Model vs closing market\n")
        lines.append(f"- n matches with close: **{_f(b['n'])}**")
        lines.append(f"- Model logloss/AUC/Brier: **{(_f(b['model']['logloss']), _f(b['model']['auc']), _f(b['model']['brier']))}**")
        lines.append(f"- Closing logloss/AUC/Brier: **{(_f(b['closing']['logloss']), _f(b['closing']['auc']), _f(b['closing']['brier']))}**")
        lines.append(f"- Beats closing on logloss: **{_f(b['beats_closing_logloss'])}**\n")
    return "\n".join(lines) + "\n"
