"""Tests for the professional betting-evaluation metrics."""

import numpy as np

from pipeline.betting_eval import (
    expected_calibration_error,
    bootstrap_ci,
    flat_stake_roi,
    clv_proxy,
    clv_closing,
    simulate_bets,
)


def test_ece_perfectly_calibrated_is_low():
    rng = np.random.default_rng(0)
    probs = rng.uniform(0, 1, 20000)
    y = (rng.uniform(0, 1, 20000) < probs).astype(int)  # outcomes match probs
    assert expected_calibration_error(y, probs, n_bins=10) < 0.05


def test_ece_miscalibrated_is_high():
    # predict 0.9 everywhere but win only half -> badly calibrated
    y = np.array([0, 1] * 500)
    probs = np.full(1000, 0.9)
    assert expected_calibration_error(y, probs) > 0.3


def test_bootstrap_ci_brackets_point():
    rng = np.random.default_rng(1)
    probs = rng.uniform(0, 1, 2000)
    y = (rng.uniform(0, 1, 2000) < probs).astype(int)
    point, lo, hi = bootstrap_ci(y, probs, metric="auc", n_boot=200)
    assert lo <= point <= hi
    assert 0.0 <= lo < hi <= 1.0


def test_flat_stake_roi_profitable_when_model_beats_fair_odds():
    # p1 truly wins 70% but offered at even-ish odds 1.8 -> positive EV, profit
    rng = np.random.default_rng(2)
    n = 5000
    y = (rng.uniform(0, 1, n) < 0.7).astype(int)
    probs = np.full(n, 0.7)
    o1 = np.full(n, 1.8)
    o2 = np.full(n, 2.2)
    res = flat_stake_roi(y, probs, o1, o2)
    assert res["bets"] > 0
    assert res["roi_pct"] > 0  # 0.7*1.8-1 = +0.26 EV -> long-run profit


def test_flat_stake_roi_skips_negative_ev():
    # model prob low and odds short -> no positive-EV bet -> no action
    y = np.array([1, 0, 1, 0])
    probs = np.array([0.5, 0.5, 0.5, 0.5])
    o1 = np.array([1.2, 1.2, 1.2, 1.2])
    o2 = np.array([1.2, 1.2, 1.2, 1.2])
    res = flat_stake_roi(y, probs, o1, o2)  # 0.5*1.2-1 = -0.4 both sides
    assert res["bets"] == 0


def test_clv_proxy_returns_structure():
    probs = np.array([0.6, 0.6])
    res = clv_proxy(probs, [2.0, 2.0], [2.0, 2.0], [1.9, 1.9], [2.1, 2.1])
    assert "avg_clv_proxy" in res and "beat_rate_pct" in res and "note" in res


def test_clv_closing_positive_when_bet_beats_close():
    # Bet at 2.10, close at 1.90 → beat close (positive CLV)
    probs = np.array([0.6, 0.6, 0.6])
    open_p1 = np.array([2.10, 2.10, 2.10])
    open_p2 = np.array([1.85, 1.85, 1.85])  # overround ~1.02
    close_p1 = np.array([1.90, 1.90, 1.90])
    close_p2 = np.array([2.00, 2.00, 2.00])
    res = clv_closing(probs, open_p1, open_p2, close_p1, close_p2)
    assert res["bets"] > 0
    assert res["avg_clv"] is not None and res["avg_clv"] > 0
    assert res["beat_rate_pct"] == 100.0
    assert "avg_clv" in res and "median_clv" in res and "close_source" in res


def test_simulate_bets_includes_clv():
    y = np.array([1, 0, 1])
    probs = np.array([0.65, 0.65, 0.65])
    o1 = np.array([2.0, 2.0, 2.0])
    o2 = np.array([1.9, 1.9, 1.9])
    c1 = np.array([1.85, 1.85, 1.85])
    c2 = np.array([2.05, 2.05, 2.05])
    bets = simulate_bets(y, probs, o1, o2, c1, c2)
    assert len(bets) > 0
    assert any("clv" in b for b in bets)
