"""Symmetric-row feature math for the feature-building pipeline.

Split out of features/builder_helpers.py to respect the 300-line module
budget (AGENT.md): forward->symmetric mapping, feature diffs and the
matchup-independent columns live here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from logging_config import get_logger

logger = get_logger(__name__)

_IDENTITY_COLS_WINNER = (
    "winner_id",
    "winner_name",
    "winner_hand",
    "winner_ht",
    "winner_ioc",
    "winner_age",
    "winner_rank",
    "winner_rank_points",
    "winner_seed",
    "winner_entry",
)

_IDENTITY_COLS_LOSER = tuple(
    c.replace("winner_", "loser_") for c in _IDENTITY_COLS_WINNER
)


def add_matchup_independent_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add player-agnostic per-match features that don't depend on player diffs."""
    if "p1_h2h_win_pct" in df.columns:
        df["h2h_win_pct"] = df["p1_h2h_win_pct"]
    else:
        df["h2h_win_pct"] = np.nan
    if "p1_h2h_win_pct_surface" in df.columns:
        df["h2h_win_pct_surface"] = df["p1_h2h_win_pct_surface"]
    else:
        df["h2h_win_pct_surface"] = np.nan
    for col in [
        "temperature_c",
        "wind_speed_kmh",
        "rain_probability",
        "humidity_pct",
        "cloud_cover_pct",
    ]:
        if col not in df.columns:
            df[col] = np.nan
    for col in ["live_implied_prob1", "live_implied_prob2", "live_margin"]:
        if col not in df.columns:
            df[col] = np.nan
    return df


def rename_forward_features_for_symmetric(
    df_original: pd.DataFrame,
    df_symmetric: pd.DataFrame,
) -> pd.DataFrame:
    """Map forward-only features (winner_X, loser_X) to symmetric (p1_X, p2_X).

    The symmetric dataset already has match_id like '123_A' (winner=p1) or '123_B' (loser=p1).
    We use this to assign the correct values.
    """
    logger.info("\n  Mapping forward features to symmetric rows ...")
    forward_cols_winner = [
        c
        for c in df_original.columns
        if c.startswith("winner_") and c not in _IDENTITY_COLS_WINNER
    ]
    forward_cols_loser = [
        c
        for c in df_original.columns
        if c.startswith("loser_") and c not in _IDENTITY_COLS_LOSER
    ]
    forward_data = df_original[
        forward_cols_winner + forward_cols_loser + ["h2h_total_matches"]
    ].copy()
    forward_data.index = forward_data.index.astype(str)

    df_symmetric["_orig_idx"] = df_symmetric["match_id"].str.rsplit("_", n=1).str[0]
    df_symmetric["_variant"] = df_symmetric["match_id"].str.rsplit("_", n=1).str[1]
    forward_data_reset = forward_data.reset_index().rename(
        columns={"index": "_orig_idx"}
    )
    merged = df_symmetric.merge(
        forward_data_reset,
        on="_orig_idx",
        how="left",
        suffixes=("", "_fwd"),
    )
    for col in forward_cols_winner:
        feat_name = col.replace("winner_", "")
        p1_col = f"p1_{feat_name}"
        p2_col = f"p2_{feat_name}"
        loser_col = col.replace("winner_", "loser_")
        if col in merged.columns and loser_col in merged.columns:
            merged[p1_col] = np.where(
                merged["_variant"] == "A",
                merged[col],
                merged.get(loser_col, np.nan),
            )
            merged[p2_col] = np.where(
                merged["_variant"] == "A",
                merged.get(loser_col, np.nan),
                merged[col],
            )
    if "h2h_total_matches" not in merged.columns:
        merged["h2h_total_matches"] = 0
    if "winner_h2h_win_pct" in merged.columns:
        merged["p1_h2h_win_pct"] = np.where(
            merged["_variant"] == "A",
            merged["winner_h2h_win_pct"],
            merged.get("loser_h2h_win_pct", np.nan),
        )
        merged["p1_h2h_win_pct_surface"] = np.where(
            merged["_variant"] == "A",
            merged.get("winner_h2h_win_pct_surface", np.nan),
            merged.get("loser_h2h_win_pct_surface", np.nan),
        )
    drop_cols = ["_orig_idx", "_variant"] + forward_cols_winner + forward_cols_loser
    drop_cols += [c for c in merged.columns if c.endswith("_fwd")]
    drop_cols += [
        "winner_h2h_win_pct",
        "loser_h2h_win_pct",
        "winner_h2h_win_pct_surface",
        "loser_h2h_win_pct_surface",
    ]
    merged = merged.drop(
        columns=[c for c in drop_cols if c in merged.columns], errors="ignore"
    )
    logger.info(f"  Forward features mapped. Shape: {merged.shape}")
    return merged


_DIFF_PAIRS = [
    ("p1_elo", "p2_elo", "elo_diff"),
    ("p1_elo_surface", "p2_elo_surface", "elo_surface_diff"),
    ("p1_elo_blend", "p2_elo_blend", "elo_blend_diff"),
    ("p1_ace_pct", "p2_ace_pct", "ace_pct_diff"),
    ("p1_df_pct", "p2_df_pct", "df_pct_diff"),
    ("p1_first_serve_in_pct", "p2_first_serve_in_pct", "first_serve_in_pct_diff"),
    (
        "p1_win_on_1st_serve_pct",
        "p2_win_on_1st_serve_pct",
        "win_on_1st_serve_pct_diff",
    ),
    (
        "p1_win_on_2nd_serve_pct",
        "p2_win_on_2nd_serve_pct",
        "win_on_2nd_serve_pct_diff",
    ),
    ("p1_bp_saved_pct", "p2_bp_saved_pct", "bp_saved_pct_diff"),
    ("p1_bp_converted_pct", "p2_bp_converted_pct", "bp_converted_pct_diff"),
    (
        "p1_first_serve_return_pts_won_pct",
        "p2_first_serve_return_pts_won_pct",
        "first_serve_return_pts_won_pct_diff",
    ),
    (
        "p1_second_serve_return_pts_won_pct",
        "p2_second_serve_return_pts_won_pct",
        "second_serve_return_pts_won_pct_diff",
    ),
    (
        "p1_return_games_won_pct",
        "p2_return_games_won_pct",
        "return_games_won_pct_diff",
    ),
    ("p1_win_pct_surface", "p2_win_pct_surface", "win_pct_surface_diff"),
    ("p1_win_pct_last_10", "p2_win_pct_last_10", "win_pct_last_10_diff"),
    ("p1_tiebreak_win_pct", "p2_tiebreak_win_pct", "tiebreak_win_pct_diff"),
    ("p1_first_set_win_rate", "p2_first_set_win_rate", "first_set_win_rate_diff"),
    ("p1_days_rest", "p2_days_rest", "days_rest_diff"),
    (
        "p1_minutes_on_court_last_10_days",
        "p2_minutes_on_court_last_10_days",
        "minutes_on_court_last_10_days_diff",
    ),
    (
        "p1_matches_last_7_days",
        "p2_matches_last_7_days",
        "matches_last_7_days_diff",
    ),
    ("p1_sos_last_10", "p2_sos_last_10", "sos_last_10_diff"),
    ("p1_opening_odds", "p2_opening_odds", "opening_odds_diff"),
    ("p1_closing_odds", "p2_closing_odds", "closing_odds_diff"),
]


def compute_diffs(df: pd.DataFrame) -> pd.DataFrame:
    """Compute p1 - p2 differences for all forward-only features.

    These features were computed on the ORIGINAL (winner/loser) data.
    In symmetric rows:
      - Row A (winner=p1): p1 columns have winner values, p2 have loser values
      - Row B (loser=p1):  p1 columns have loser values,  p2 have winner values
    """
    logger.info("\n  Computing feature differences (p1 - p2) ...")
    for p1_col, p2_col, diff_col in _DIFF_PAIRS:
        if p1_col in df.columns and p2_col in df.columns:
            df[diff_col] = df[p1_col] - df[p2_col]
        else:
            df[diff_col] = np.nan

    # Interaction: favorites win more often in best-of-5
    if "elo_diff" in df.columns and "best_of" in df.columns:
        best_of_num = pd.to_numeric(df["best_of"], errors="coerce").fillna(3)
        df["elo_diff_x_bo5"] = df["elo_diff"] * (best_of_num == 5).astype(int)
    else:
        df["elo_diff_x_bo5"] = np.nan

    df = add_matchup_independent_features(df)
    return df
