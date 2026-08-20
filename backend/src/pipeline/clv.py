"""Closing Line Value (CLV) computations for betting evaluation.

CLV compares the price taken for a bet against the closing line: a positive
value means the bettor got a better price than the market's final opinion.
"""
from __future__ import annotations

import numpy as np


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
