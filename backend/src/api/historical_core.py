"""Historical-row inference helpers (parquet fallback path).

Used by the /api/predict route when the live tracker state is missing:
latest player stats, head-to-head stats and the synthetic feature row built
from historical parquet columns.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime, timezone

import numpy as np
import pandas as pd

_BASE_COL_MAP = {"ranking": "rank", "ranking_points": "rank_points"}
_FATIGUE_BASES = {"days_rest", "minutes_on_court_last_10_days", "matches_last_7_days"}
_SURFACE_BASES = {"elo_surface", "win_pct_surface", "elo_blend"}


def fold_player_name(name: str) -> str:
    """Lowercase and strip diacritics for accent-insensitive matching."""
    if not isinstance(name, str):
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", name) if not unicodedata.combining(c)
    ).strip().lower()


def get_player_latest_stats(
    player_name: str, df: pd.DataFrame, surface: str | None = None
) -> pd.Series | None:
    """Last chronological row where the player appears as p1 (win OR loss)."""
    key = fold_player_name(player_name)
    mask = df["p1_name"].map(fold_player_name) == key
    if surface and "surface" in df.columns:
        mask &= df["surface"] == surface
    p_df = df[mask]
    if p_df.empty:
        return None
    sort_col = "match_date_est" if "match_date_est" in p_df.columns else "tourney_date"
    return p_df.sort_values(sort_col, ascending=False).iloc[0]


def get_h2h_stats(
    player1: str, player2: str, df: pd.DataFrame, surface: str | None = None
) -> dict:
    mask = (
        (df["p1_name"].map(fold_player_name) == fold_player_name(player1))
        & (df["p2_name"].map(fold_player_name) == fold_player_name(player2))
    )
    h_df = df[mask]
    result = {"h2h_win_pct": np.nan, "h2h_win_pct_surface": np.nan, "h2h_total_matches": 0}
    if h_df.empty:
        return result
    result["h2h_win_pct"] = float(h_df["label"].mean())
    result["h2h_total_matches"] = int(len(h_df))
    if surface and "surface" in h_df.columns:
        s_df = h_df[h_df["surface"] == surface]
        if not s_df.empty:
            result["h2h_win_pct_surface"] = float(s_df["label"].mean())
    return result


def stat_value(stats_row, base: str) -> float:
    if stats_row is None:
        return np.nan
    col = f"p1_{_BASE_COL_MAP.get(base, base)}"
    if col not in stats_row.index:
        return np.nan
    try:
        return float(stats_row[col])
    except (TypeError, ValueError):
        return np.nan


def build_feature_row(feature_cols, sA, sB, sA_surf, sB_surf, h2h, surface, best_of=3):
    """Build model input row for fallback historical-row inference."""
    df_fake = pd.DataFrame(np.nan, index=[0], columns=feature_cols)
    for col in feature_cols:
        if col.startswith("surface_"):
            df_fake[col] = 1.0 if col == f"surface_{surface}" else 0.0
        elif col == "tourney_level_encoded":
            df_fake[col] = 2
        elif col == "round_encoded":
            df_fake[col] = 3
        elif col == "best_of":
            df_fake[col] = best_of
        elif col == "month":
            df_fake[col] = datetime.now(timezone.utc).month
        elif col == "indoor_outdoor":
            df_fake[col] = 0
        elif col == "altitude":
            df_fake[col] = 0.0
        elif col == "h2h_win_pct":
            df_fake[col] = h2h["h2h_win_pct"]
        elif col == "h2h_win_pct_surface":
            df_fake[col] = h2h["h2h_win_pct_surface"]
        elif col == "hand_matchup":
            try:
                hand_a = str(sA["p1_hand"]) if sA is not None else "U"
                hand_b = str(sB["p1_hand"]) if sB is not None else "U"
                df_fake[col] = int(hand_a != hand_b) if "U" not in (hand_a, hand_b) else 0
            except Exception:
                df_fake[col] = 0
        elif col == "home_country_flag":
            df_fake[col] = 0
        elif col == "qualifier_flag_diff":
            df_fake[col] = 0
        elif col == "cold_start_flag":
            count_a = stat_value(sA, "match_count")
            count_b = stat_value(sB, "match_count")
            cold = (
                np.isnan(count_a) or count_a < 10
                or np.isnan(count_b) or count_b < 10
            )
            df_fake[col] = int(cold)
        elif col == "log_rank_diff":
            rank_a = stat_value(sA, "rank")
            rank_b = stat_value(sB, "rank")
            if not np.isnan(rank_a) and not np.isnan(rank_b):
                df_fake[col] = np.log(max(rank_a, 1.0)) - np.log(max(rank_b, 1.0))
        elif col == "elo_diff_x_bo5":
            ea = stat_value(sA, "elo")
            eb = stat_value(sB, "elo")
            if not np.isnan(ea) and not np.isnan(eb):
                df_fake[col] = (ea - eb) * (1 if best_of == 5 else 0)
        elif col.endswith("_diff"):
            base = col[: -len("_diff")]
            if base in _FATIGUE_BASES:
                continue  # NaN -> train median (stale fatigue is worse than missing)
            row_a, row_b = (sA_surf, sB_surf) if base in _SURFACE_BASES else (sA, sB)
            val_a = stat_value(row_a, base)
            val_b = stat_value(row_b, base)
            if not np.isnan(val_a) and not np.isnan(val_b):
                df_fake[col] = val_a - val_b
    return df_fake
