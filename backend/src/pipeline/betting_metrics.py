"""Core betting-metric functions (pure numpy/sklearn, no I/O).

Used by full_betting_report() in pipeline/betting_eval.py: ECE, bootstrap
CIs, flat-stake ROI, bet simulation, edge segmentation, fractional Kelly
and the model-vs-closing benchmark.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss, accuracy_score


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
