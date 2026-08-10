"""Rolling statistics computed with exponential decay.

All stats are computed forward-only (no data leakage):
  - At match i, rolling stats use matches 0..i-1 for each player.
  - Exponential decay gives more weight to recent matches.

Stats computed per player:
  SERVE STATS:
    ace_pct, df_pct, first_serve_in_pct, win_on_1st_serve_pct,
    win_on_2nd_serve_pct, bp_saved_pct, bp_converted_pct
  RETURN STATS:
    first_serve_return_pts_won_pct, second_serve_return_pts_won_pct,
    return_games_won_pct
  GENERAL:
    win_pct_surface, win_pct_last_10, tiebreak_win_pct, first_set_win_rate,
    sos_last_10
"""
from __future__ import annotations

import os
import re
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

from logging_config import get_logger
logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _exponential_weights(n: int, half_life: int | None = None) -> np.ndarray:
    """Generate exponential decay weights for the last *n* observations.

    Most recent observation gets weight 1.0.
    """
    half_life = half_life or config.DECAY_HALF_LIFE
    decay = np.log(2) / half_life
    weights = np.exp(-decay * np.arange(n)[::-1])
    return weights


def _weighted_mean(values: list, half_life: int | None = None) -> float:
    """Compute exponentially weighted mean of a list of values."""
    if not values:
        return np.nan
    arr = np.array(values, dtype=float)
    mask = ~np.isnan(arr)
    arr = arr[mask]
    if len(arr) == 0:
        return np.nan
    w = _exponential_weights(len(arr), half_life)
    return float(np.average(arr, weights=w))


class PlayerStatsTracker:
    """Tracks rolling statistics for a single player.

    All updates are forward-only.
    """

    def __init__(self, window: int | None = None) -> None:
        self.window = window or config.ROLLING_WINDOW
        self.ace_pcts: list[float] = []
        self.df_pcts: list[float] = []
        self.first_serve_in_pcts: list[float] = []
        self.win_1st_pcts: list[float] = []
        self.win_2nd_pcts: list[float] = []
        self.bp_saved_pcts: list[float] = []
        self.bp_conversion_against: list[float] = []
        self.first_serve_return_pts_won_pcts: list[float] = []
        self.second_serve_return_pts_won_pcts: list[float] = []
        self.return_games_won_pcts: list[float] = []
        self.results_by_surface: dict[str, list[int]] = defaultdict(list)
        self.results_all: list[int] = []
        self.tiebreaks_won: list[int] = []
        self.tiebreaks_played: list[int] = []
        self.first_set_wins: list[float] = []
        self.opponent_ranks: list[float] = []

    def get_rolling_stats(self, surface: str | None = None) -> dict:
        """Return current rolling stats (BEFORE updating with current match)."""
        w = self.window
        stats: dict = {}
        stats["ace_pct"] = _weighted_mean(self.ace_pcts[-w:])
        stats["df_pct"] = _weighted_mean(self.df_pcts[-w:])
        stats["first_serve_in_pct"] = _weighted_mean(self.first_serve_in_pcts[-w:])
        stats["win_on_1st_serve_pct"] = _weighted_mean(self.win_1st_pcts[-w:])
        stats["win_on_2nd_serve_pct"] = _weighted_mean(self.win_2nd_pcts[-w:])
        stats["bp_saved_pct"] = _weighted_mean(self.bp_saved_pcts[-w:])
        stats["bp_converted_pct"] = _weighted_mean(self.bp_conversion_against[-w:])
        stats["first_serve_return_pts_won_pct"] = _weighted_mean(
            self.first_serve_return_pts_won_pcts[-w:]
        )
        stats["second_serve_return_pts_won_pct"] = _weighted_mean(
            self.second_serve_return_pts_won_pcts[-w:]
        )
        stats["return_games_won_pct"] = _weighted_mean(
            self.return_games_won_pcts[-w:]
        )
        if surface and surface in self.results_by_surface:
            surf_results = self.results_by_surface[surface][-w:]
            stats["win_pct_surface"] = (
                _weighted_mean(surf_results) if surf_results else np.nan
            )
        else:
            stats["win_pct_surface"] = np.nan
        last10 = self.results_all[-10:]
        stats["win_pct_last_10"] = float(np.mean(last10)) if last10 else np.nan
        if self.tiebreaks_played:
            tb_total = sum(self.tiebreaks_played[-w:])
            if tb_total > 0:
                tb_won = sum(self.tiebreaks_won[-w:])
                stats["tiebreak_win_pct"] = tb_won / tb_total
            else:
                stats["tiebreak_win_pct"] = np.nan
        else:
            stats["tiebreak_win_pct"] = np.nan
        if self.first_set_wins:
            stats["first_set_win_rate"] = _weighted_mean(self.first_set_wins[-w:])
        else:
            stats["first_set_win_rate"] = np.nan
        if self.opponent_ranks:
            recent_opp_ranks = [r for r in self.opponent_ranks[-10:] if not np.isnan(r)]
            if recent_opp_ranks:
                stats["sos_last_10"] = float(np.mean(recent_opp_ranks))
            else:
                stats["sos_last_10"] = np.nan
        else:
            stats["sos_last_10"] = np.nan
        # Match count (for cold-start detection at inference)
        stats["match_count"] = len(self.results_all)
        return stats

    def update(
        self,
        won: bool,
        surface: str,
        ace: float, df: float, svpt: float,
        first_in: float, first_won: float, second_won: float,
        bp_saved: float, bp_faced: float,
        opp_bp_saved: float, opp_bp_faced: float,
        opp_svpt: float, opp_1stIn: float, opp_1stWon: float,
        opp_2ndWon: float, opp_SvGms: float,
        score: str,
        opp_rank: float,
    ) -> None:
        """Update tracker with a new match result. Called AFTER feature extraction."""
        if svpt and svpt > 0 and not np.isnan(svpt):
            self.ace_pcts.append(ace / svpt if not np.isnan(ace) else np.nan)
            self.df_pcts.append(df / svpt if not np.isnan(df) else np.nan)
            self.first_serve_in_pcts.append(
                first_in / svpt if not np.isnan(first_in) else np.nan
            )
            if first_in and first_in > 0 and not np.isnan(first_in):
                self.win_1st_pcts.append(
                    first_won / first_in if not np.isnan(first_won) else np.nan
                )
            else:
                self.win_1st_pcts.append(np.nan)
            second_attempts = (svpt - first_in) if first_in else 0
            if second_attempts > 0:
                self.win_2nd_pcts.append(
                    second_won / second_attempts if not np.isnan(second_won) else np.nan
                )
            else:
                self.win_2nd_pcts.append(np.nan)
        else:
            self.ace_pcts.append(np.nan)
            self.df_pcts.append(np.nan)
            self.first_serve_in_pcts.append(np.nan)
            self.win_1st_pcts.append(np.nan)
            self.win_2nd_pcts.append(np.nan)

        if bp_faced and bp_faced > 0 and not np.isnan(bp_faced):
            self.bp_saved_pcts.append(bp_saved / bp_faced)
        else:
            self.bp_saved_pcts.append(np.nan)
        if opp_bp_faced and opp_bp_faced > 0 and not np.isnan(opp_bp_faced):
            converted = opp_bp_faced - opp_bp_saved
            self.bp_conversion_against.append(converted / opp_bp_faced)
        else:
            self.bp_conversion_against.append(np.nan)

        # Return stats (derived from opponent's serve data)
        if (opp_1stIn and opp_1stIn > 0 and not np.isnan(opp_1stIn)
                and not np.isnan(opp_1stWon)):
            return_1st_won = opp_1stIn - opp_1stWon
            self.first_serve_return_pts_won_pcts.append(return_1st_won / opp_1stIn)
        else:
            self.first_serve_return_pts_won_pcts.append(np.nan)
        if (opp_svpt and not np.isnan(opp_svpt)
                and opp_1stIn and not np.isnan(opp_1stIn)
                and not np.isnan(opp_2ndWon)):
            opp_2nd_attempts = opp_svpt - opp_1stIn
            if opp_2nd_attempts > 0:
                return_2nd_won = opp_2nd_attempts - opp_2ndWon
                self.second_serve_return_pts_won_pcts.append(
                    return_2nd_won / opp_2nd_attempts
                )
            else:
                self.second_serve_return_pts_won_pcts.append(np.nan)
        else:
            self.second_serve_return_pts_won_pcts.append(np.nan)
        if (opp_SvGms and opp_SvGms > 0 and not np.isnan(opp_SvGms)
                and opp_bp_faced is not None and not np.isnan(opp_bp_faced)):
            breaks_won = (
                (opp_bp_faced - opp_bp_saved)
                if not np.isnan(opp_bp_saved) else 0
            )
            self.return_games_won_pcts.append(breaks_won / opp_SvGms)
        else:
            self.return_games_won_pcts.append(np.nan)

        result = 1 if won else 0
        self.results_all.append(result)
        if surface:
            self.results_by_surface[surface].append(result)

        tb_won, tb_played = self._parse_tiebreaks(score, won)
        self.tiebreaks_won.append(tb_won)
        self.tiebreaks_played.append(tb_played)
        first_set_won = self._parse_first_set(score, won)
        self.first_set_wins.append(first_set_won)
        if not np.isnan(opp_rank):
            self.opponent_ranks.append(opp_rank)

    @staticmethod
    def _parse_tiebreaks(score: str, won: bool) -> tuple[int, int]:
        """Parse tiebreaks from score string.

        Score format: '6-3 7-6(4) 6-4' or '6-7(5) 7-6(3) 7-5'.
        Sackmann scores are always winner-perspective.
        """
        if not score or not isinstance(score, str):
            return 0, 0
        tb_pattern = re.compile(r"(\d+)-(\d+)\((\d+)\)")
        matches = tb_pattern.findall(score)
        tb_played = len(matches)
        tb_won = 0
        for s1, s2, _ in matches:
            try:
                s1_i, s2_i = int(s1), int(s2)
            except ValueError:
                continue
            if won:
                if s1_i > s2_i:
                    tb_won += 1
            else:
                if s2_i > s1_i:
                    tb_won += 1
        return tb_won, tb_played

    @staticmethod
    def _parse_first_set(score: str, won: bool) -> float:
        """Did this player win the first set? 1.0, 0.0, or NaN if unparseable."""
        if not score or not isinstance(score, str):
            return np.nan
        sets = score.strip().split()
        if not sets:
            return np.nan
        first = sets[0]
        first_clean = re.sub(r"\(\d+\)", "", first)
        parts = first_clean.split("-")
        if len(parts) != 2:
            return np.nan
        try:
            s1, s2 = int(parts[0]), int(parts[1])
        except ValueError:
            return np.nan
        if won:
            return 1.0 if s1 > s2 else 0.0
        return 1.0 if s2 > s1 else 0.0


def compute_rolling_features(df_original: pd.DataFrame, return_state: bool = False):
    """Compute rolling statistics on the ORIGINAL (non-symmetric) dataset.

    CRITICAL: stats at match i use only matches 0..i-1 (forward-only).
    With return_state=True, also returns per-player trackers as a plain dict.
    """
    logger.info("\n  Computing rolling statistics (forward-only, exp-decay) ...")
    sort_cols = [c for c in ["match_date_est", "tourney_date", "match_num"] if c in df_original.columns]
    df = df_original.sort_values(sort_cols).reset_index(drop=True)
    trackers: dict = defaultdict(lambda: PlayerStatsTracker())
    records = []
    for idx in range(len(df)):
        row = df.iloc[idx]
        w_id = row["winner_id"]
        l_id = row["loser_id"]
        surface = row.get("surface", None)
        w_stats = trackers[w_id].get_rolling_stats(surface)
        l_stats = trackers[l_id].get_rolling_stats(surface)
        record: dict = {}
        for key in w_stats:
            record[f"winner_{key}"] = w_stats[key]
            record[f"loser_{key}"] = l_stats[key]
        records.append(record)
        trackers[w_id].update(
            won=True, surface=surface,
            ace=row.get("w_ace", np.nan), df=row.get("w_df", np.nan),
            svpt=row.get("w_svpt", np.nan),
            first_in=row.get("w_1stIn", np.nan),
            first_won=row.get("w_1stWon", np.nan),
            second_won=row.get("w_2ndWon", np.nan),
            bp_saved=row.get("w_bpSaved", np.nan),
            bp_faced=row.get("w_bpFaced", np.nan),
            opp_bp_saved=row.get("l_bpSaved", np.nan),
            opp_bp_faced=row.get("l_bpFaced", np.nan),
            opp_svpt=row.get("l_svpt", np.nan),
            opp_1stIn=row.get("l_1stIn", np.nan),
            opp_1stWon=row.get("l_1stWon", np.nan),
            opp_2ndWon=row.get("l_2ndWon", np.nan),
            opp_SvGms=row.get("l_SvGms", np.nan),
            score=row.get("score", ""),
            opp_rank=row.get("loser_rank", np.nan),
        )
        trackers[l_id].update(
            won=False, surface=surface,
            ace=row.get("l_ace", np.nan), df=row.get("l_df", np.nan),
            svpt=row.get("l_svpt", np.nan),
            first_in=row.get("l_1stIn", np.nan),
            first_won=row.get("l_1stWon", np.nan),
            second_won=row.get("l_2ndWon", np.nan),
            bp_saved=row.get("l_bpSaved", np.nan),
            bp_faced=row.get("l_bpFaced", np.nan),
            opp_bp_saved=row.get("w_bpSaved", np.nan),
            opp_bp_faced=row.get("w_bpFaced", np.nan),
            opp_svpt=row.get("w_svpt", np.nan),
            opp_1stIn=row.get("w_1stIn", np.nan),
            opp_1stWon=row.get("w_1stWon", np.nan),
            opp_2ndWon=row.get("w_2ndWon", np.nan),
            opp_SvGms=row.get("w_SvGms", np.nan),
            score=row.get("score", ""),
            opp_rank=row.get("winner_rank", np.nan),
        )
    rolling_df = pd.DataFrame(records, index=df.index)
    result = pd.concat([df, rolling_df], axis=1)
    logger.info(f"  Rolling features computed for {len(result):,} matches")
    if return_state:
        # Plain dict: defaultdict with lambda factory is not picklable
        return result, dict(trackers)
    return result
