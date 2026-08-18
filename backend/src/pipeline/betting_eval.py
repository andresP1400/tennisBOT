"""
Professional evaluation metrics for a probabilistic betting model.

Adds, on top of the standard Brier / log-loss / AUC:
  - Expected Calibration Error (ECE)   -> single-number calibration quality
  - 95% bootstrap confidence intervals -> metrics aren't a single-split fluke
  - Flat-stake ROI (out-of-sample)     -> would value bets have made money?
  - Closing Line Value (CLV)           -> did we beat the closing line?

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

import numpy as np
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss, accuracy_score


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #
def expected_calibration_error(y_true, probs, n_bins: int = 10) -> float:
    """Weighted average gap between predicted confidence and actual accuracy."""
    y_true = np.asarray(y_true)
    probs = np.asarray(probs)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(probs)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (probs > lo) & (probs <= hi) if i > 0 else (probs >= lo) & (probs <= hi)
        if not mask.any():
            continue
        conf = probs[mask].mean()
        acc = y_true[mask].mean()
        ece += (mask.sum() / n) * abs(conf - acc)
    return float(ece)


# --------------------------------------------------------------------------- #
# Bootstrap confidence intervals
# --------------------------------------------------------------------------- #
def bootstrap_ci(y_true, probs, metric: str = "auc",
                 n_boot: int = 1000, seed: int = 42) -> tuple[float, float, float]:
    """Return (point_estimate, lo95, hi95) for a metric via bootstrap resampling."""
    y_true = np.asarray(y_true)
    probs = np.asarray(probs)
    rng = np.random.default_rng(seed)

    def _metric(yt, p):
        if metric == "auc":
            return roc_auc_score(yt, p)
        if metric == "brier":
            return brier_score_loss(yt, p)
        if metric == "logloss":
            return log_loss(yt, np.clip(p, 1e-6, 1 - 1e-6))
        if metric == "accuracy":
            return accuracy_score(yt, p >= 0.5)
        raise ValueError(metric)

    point = _metric(y_true, probs)
    n = len(y_true)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yt = y_true[idx]
        if metric == "auc" and len(np.unique(yt)) < 2:
            continue
        vals.append(_metric(yt, probs[idx]))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(point), float(lo), float(hi)


# --------------------------------------------------------------------------- #
# ROI (flat stake, positive-EV bets only)
# --------------------------------------------------------------------------- #
def flat_stake_roi(y_true, probs, odds_p1, odds_p2, edge: float = 0.0) -> dict:
    """Bet 1 unit on a player whenever model EV is positive (p*odds-1 > edge).

    Settles against the real outcome (y_true=1 means p1 won). Returns ROI,
    number of bets, hit rate and total profit. Out-of-sample only.
    """
    y_true = np.asarray(y_true)
    p1 = np.asarray(probs)
    o1 = np.asarray(odds_p1, dtype=float)
    o2 = np.asarray(odds_p2, dtype=float)
    valid = np.isfinite(o1) & np.isfinite(o2) & (o1 > 1) & (o2 > 1)

    staked = 0
    profit = 0.0
    wins = 0
    for i in np.where(valid)[0]:
        ev1 = p1[i] * o1[i] - 1.0
        ev2 = (1 - p1[i]) * o2[i] - 1.0
        # bet the side with the higher positive expected value
        if max(ev1, ev2) <= edge:
            continue
        staked += 1
        if ev1 >= ev2:
            won = (y_true[i] == 1)
            profit += (o1[i] - 1.0) if won else -1.0
        else:
            won = (y_true[i] == 0)
            profit += (o2[i] - 1.0) if won else -1.0
        wins += int(won)

    roi = (profit / staked) if staked else 0.0
    return {
        "bets": staked,
        "profit_units": round(profit, 2),
        "roi_pct": round(100 * roi, 2),
        "hit_rate_pct": round(100 * wins / staked, 2) if staked else None,
    }


# --------------------------------------------------------------------------- #
# Bet simulation -> structured records (powers CI / segmentation / Kelly)
# --------------------------------------------------------------------------- #
def simulate_bets(y_true, probs, odds_p1, odds_p2,
                  close_p1=None, close_p2=None, edge: float = 0.0) -> list[dict]:
    """One record per positive-EV bet placed at the opening price.

    Each record: net return (units), the model edge vs the vig-free market
    implied prob, the odds taken, and — if closing odds are given — the CLV.
    """
    y = np.asarray(y_true)
    p = np.asarray(probs)
    o1 = np.asarray(odds_p1, float)
    o2 = np.asarray(odds_p2, float)
    c1 = np.asarray(close_p1, float) if close_p1 is not None else None
    c2 = np.asarray(close_p2, float) if close_p2 is not None else None
    valid = np.isfinite(o1) & np.isfinite(o2) & (o1 > 1) & (o2 > 1)

    bets = []
    for i in np.where(valid)[0]:
        # Odds-quality guard: drop implausible / stale lines. A two-way market
        # must have overround (1/o1 + 1/o2) in a sane band; values < 1 mean the
        # two prices are mismatched in time (arbitrage = bad data) and produce
        # fake "edges". Also cap extreme prices.
        inv1, inv2 = 1 / o1[i], 1 / o2[i]
        overround = inv1 + inv2
        if not (1.00 <= overround <= 1.20):
            continue
        if o1[i] > 15 or o2[i] > 15:
            continue
        ev1, ev2 = p[i] * o1[i] - 1, (1 - p[i]) * o2[i] - 1
        if max(ev1, ev2) <= edge:
            continue
        mkt1 = inv1 / (inv1 + inv2)              # vig-free market prob, side 1
        if ev1 >= ev2:
            ret = (o1[i] - 1) if y[i] == 1 else -1.0
            model_p, mkt_p, took = p[i], mkt1, o1[i]
            close = c1[i] if c1 is not None else np.nan
        else:
            ret = (o2[i] - 1) if y[i] == 0 else -1.0
            model_p, mkt_p, took = 1 - p[i], 1 - mkt1, o2[i]
            close = c2[i] if c2 is not None else np.nan
        rec = {"ret": ret, "edge": model_p - mkt_p, "odds": took, "model_p": model_p}
        if np.isfinite(close) and close > 1:
            # Positive CLV = got a better price than close (lower implied).
            rec["clv"] = (1.0 / close) - (1.0 / took)
            rec["beat_close"] = bool(took >= close)
        bets.append(rec)
    return bets


def roi_with_ci(bets: list[dict], n_boot: int = 2000, seed: int = 11) -> dict:
    """ROI point estimate + 95% bootstrap CI + one-sided p-value (ROI<=0)."""
    if not bets:
        return {"bets": 0}
    r = np.array([b["ret"] for b in bets])
    rng = np.random.default_rng(seed)
    means = np.array([r[rng.integers(0, len(r), len(r))].mean() for _ in range(n_boot)])
    lo, hi = np.percentile(means, [2.5, 97.5])
    p_value = float(np.mean(means <= 0))      # fraction of resamples not profitable
    return {
        "bets": len(r),
        "roi_pct": round(100 * r.mean(), 2),
        "roi_ci95": [round(100 * lo, 2), round(100 * hi, 2)],
        "p_value_roi_le_0": round(p_value, 4),
        "significant_5pct": bool(lo > 0),
    }


def segment_by_edge(bets: list[dict]) -> list[dict]:
    """ROI / CLV grouped by how far the model diverges from the market."""
    bands = [("0-2%", 0.0, 0.02), ("2-5%", 0.02, 0.05),
             ("5-10%", 0.05, 0.10), ("10%+", 0.10, 1.01)]
    out = []
    for lab, lo, hi in bands:
        seg = [b for b in bets if lo <= b["edge"] < hi]
        if not seg:
            continue
        r = np.array([b["ret"] for b in seg])
        clvs = [b["clv"] for b in seg if "clv" in b]
        out.append({
            "edge_band": lab, "bets": len(seg),
            "roi_pct": round(100 * r.mean(), 2),
            "hit_pct": round(100 * np.mean(r > 0), 1),
            "avg_clv": round(float(np.mean(clvs)), 5) if clvs else None,
            "clv_beat_pct": round(100 * np.mean(np.array(clvs) > 0), 1) if clvs else None,
        })
    return out


def kelly_backtest(bets: list[dict], fraction: float = 0.25, bankroll: float = 100.0) -> dict:
    """Fractional-Kelly geometric growth on the bet sequence."""
    if not bets:
        return {"bets": 0}
    bank = bankroll
    peak = bankroll
    max_dd = 0.0
    for b in bets:
        odds = b["odds"]
        pm = b["model_p"]
        bb = odds - 1
        f = max((bb * pm - (1 - pm)) / bb, 0.0) * fraction   # fractional Kelly
        stake = bank * f
        won = b["ret"] > 0
        bank += stake * (odds - 1) if won else -stake
        peak = max(peak, bank)
        max_dd = max(max_dd, (peak - bank) / peak)
        if bank <= 0:
            return {"bets": len(bets), "final_bankroll": 0.0, "busted": True}
    growth = bank / bankroll
    return {
        "bets": len(bets),
        "kelly_fraction": fraction,
        "final_bankroll": round(bank, 1),
        "growth_x": round(growth, 3),
        "max_drawdown_pct": round(100 * max_dd, 1),
        "busted": False,
    }


def benchmark_vs_closing(y_true, probs, close_p1, close_p2) -> dict:
    """Compare the model's log-loss/AUC/Brier against the CLOSING implied
    probabilities — the honest 'do we beat the sharpest line?' test."""
    y = np.asarray(y_true)
    p = np.asarray(probs)
    c1 = np.asarray(close_p1, float)
    c2 = np.asarray(close_p2, float)
    mask = np.isfinite(c1) & np.isfinite(c2) & (c1 > 1) & (c2 > 1)
    if mask.sum() < 50:
        return {}
    inv1, inv2 = 1 / c1[mask], 1 / c2[mask]
    close_p = inv1 / (inv1 + inv2)
    ym, pm = y[mask], np.clip(p[mask], 1e-6, 1 - 1e-6)
    cp = np.clip(close_p, 1e-6, 1 - 1e-6)
    return {
        "n": int(mask.sum()),
        "model": {"logloss": round(log_loss(ym, pm), 4), "auc": round(roc_auc_score(ym, pm), 4),
                  "brier": round(brier_score_loss(ym, pm), 4)},
        "closing": {"logloss": round(log_loss(ym, cp), 4), "auc": round(roc_auc_score(ym, cp), 4),
                    "brier": round(brier_score_loss(ym, cp), 4)},
        "beats_closing_logloss": bool(log_loss(ym, pm) < log_loss(ym, cp)),
    }


# --------------------------------------------------------------------------- #
# CLV: opening (bet price) vs closing line
# --------------------------------------------------------------------------- #
def clv_closing(
    probs,
    open_p1,
    open_p2,
    close_p1,
    close_p2,
    edge: float = 0.0,
    close_source: str = "closing",
) -> dict:
    """True CLV vs the dataset closing line (Avg consensus or Max/Pinnacle).

    For each positive-EV bet placed at *opening* price, compare implied
    probability of the bet vs the same side's *closing* price.

    CLV (prob points) = 1/close - 1/bet
      > 0  -> beat the close (got a better price than closing line)
      < 0  -> lost to the close

    beat_rate = fraction of bets with bet_odds >= close_odds.
    """
    p1 = np.asarray(probs)
    o1, o2 = np.asarray(open_p1, float), np.asarray(open_p2, float)
    c1, c2 = np.asarray(close_p1, float), np.asarray(close_p2, float)
    valid = (
        np.isfinite(o1) & np.isfinite(o2) & np.isfinite(c1) & np.isfinite(c2)
        & (o1 > 1) & (o2 > 1) & (c1 > 1) & (c2 > 1)
    )

    diffs, beats, n = [], 0, 0
    for i in np.where(valid)[0]:
        # overround guard on open market
        overround = 1 / o1[i] + 1 / o2[i]
        if not (1.00 <= overround <= 1.20):
            continue
        if o1[i] > 15 or o2[i] > 15:
            continue
        ev1 = p1[i] * o1[i] - 1.0
        ev2 = (1 - p1[i]) * o2[i] - 1.0
        if max(ev1, ev2) <= edge:
            continue
        if ev1 >= ev2:
            bet_odds, close_odds = o1[i], c1[i]
        else:
            bet_odds, close_odds = o2[i], c2[i]
        clv = (1.0 / close_odds) - (1.0 / bet_odds)
        diffs.append(clv)
        beats += int(bet_odds >= close_odds)
        n += 1

    arr = np.array(diffs) if diffs else np.array([])
    return {
        "bets": n,
        "avg_clv": round(float(arr.mean()), 5) if n else None,
        "median_clv": round(float(np.median(arr)), 5) if n else None,
        "beat_rate_pct": round(100 * beats / n, 2) if n else None,
        "clv_std": round(float(arr.std()), 5) if n else None,
        "close_source": close_source,
        "note": (
            f"CLV open->close ({close_source}). "
            "Positive avg_clv / beat_rate>50% = model picks the right side "
            "before the line firms. Free data uses Avg consensus as close when "
            "available (else Max/Pinnacle snapshot)."
        ),
    }


def clv_proxy(probs, open_p1, open_p2, max_p1, max_p2, edge: float = 0.0) -> dict:
    """Backward-compatible alias: opening vs max/close market.

    Prefer clv_closing() for new code. Kept so existing tests keep working.
    """
    res = clv_closing(
        probs, open_p1, open_p2, max_p1, max_p2,
        edge=edge, close_source="max/close",
    )
    return {
        "bets": res["bets"],
        "avg_clv_proxy": res["avg_clv"],
        "beat_rate_pct": res["beat_rate_pct"],
        "note": "PROXY alias of clv_closing (open vs max/close market)",
    }


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def full_betting_report(df_test_single, y_test, test_probs, reports_dir=None) -> dict:
    """Compute and print the professional metric suite. Writes a markdown
    summary to reports_dir if given. Safe when odds columns are absent."""
    import os

    import sys
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
