"""Constants and column name mappings used across the pipeline.

Maps Jeff Sackmann CSV columns to internal naming conventions and lists
the canonical feature column names exposed to the training pipeline.
"""
from __future__ import annotations

SACKMANN_MATCH_COLS: list[str] = [
    "tourney_id", "tourney_name", "surface", "draw_size", "tourney_level",
    "tourney_date", "match_num", "winner_id", "winner_seed", "winner_entry",
    "winner_name", "winner_hand", "winner_ht", "winner_ioc", "winner_age",
    "winner_rank", "winner_rank_points", "loser_id", "loser_seed",
    "loser_entry", "loser_name", "loser_hand", "loser_ht", "loser_ioc",
    "loser_age", "loser_rank", "loser_rank_points", "score", "best_of",
    "round", "minutes",
    "w_ace", "w_df", "w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon",
    "w_SvGms", "w_bpSaved", "w_bpFaced",
    "l_ace", "l_df", "l_svpt", "l_1stIn", "l_1stWon", "l_2ndWon",
    "l_SvGms", "l_bpSaved", "l_bpFaced",
]

WINNER_TO_P1: dict[str, str] = {
    "winner_id": "p1_id",
    "winner_name": "p1_name",
    "winner_hand": "p1_hand",
    "winner_ht": "p1_ht",
    "winner_ioc": "p1_ioc",
    "winner_age": "p1_age",
    "winner_rank": "p1_rank",
    "winner_rank_points": "p1_rank_points",
    "winner_seed": "p1_seed",
    "winner_entry": "p1_entry",
    "w_ace": "p1_ace",
    "w_df": "p1_df",
    "w_svpt": "p1_svpt",
    "w_1stIn": "p1_1stIn",
    "w_1stWon": "p1_1stWon",
    "w_2ndWon": "p1_2ndWon",
    "w_SvGms": "p1_SvGms",
    "w_bpSaved": "p1_bpSaved",
    "w_bpFaced": "p1_bpFaced",
}

LOSER_TO_P2: dict[str, str] = {
    "loser_id": "p2_id",
    "loser_name": "p2_name",
    "loser_hand": "p2_hand",
    "loser_ht": "p2_ht",
    "loser_ioc": "p2_ioc",
    "loser_age": "p2_age",
    "loser_rank": "p2_rank",
    "loser_rank_points": "p2_rank_points",
    "loser_seed": "p2_seed",
    "loser_entry": "p2_entry",
    "l_ace": "p2_ace",
    "l_df": "p2_df",
    "l_svpt": "p2_svpt",
    "l_1stIn": "p2_1stIn",
    "l_1stWon": "p2_1stWon",
    "l_2ndWon": "p2_2ndWon",
    "l_SvGms": "p2_SvGms",
    "l_bpSaved": "p2_bpSaved",
    "l_bpFaced": "p2_bpFaced",
}

# Reverse mapping for the mirrored row (loser as p1).
LOSER_TO_P1_MAP: dict[str, str] = {
    "loser_id": "p1_id",
    "loser_name": "p1_name",
    "loser_hand": "p1_hand",
    "loser_ht": "p1_ht",
    "loser_ioc": "p1_ioc",
    "loser_age": "p1_age",
    "loser_rank": "p1_rank",
    "loser_rank_points": "p1_rank_points",
    "loser_seed": "p1_seed",
    "loser_entry": "p1_entry",
    "l_ace": "p1_ace",
    "l_df": "p1_df",
    "l_svpt": "p1_svpt",
    "l_1stIn": "p1_1stIn",
    "l_1stWon": "p1_1stWon",
    "l_2ndWon": "p1_2ndWon",
    "l_SvGms": "p1_SvGms",
    "l_bpSaved": "p1_bpSaved",
    "l_bpFaced": "p1_bpFaced",
}

WINNER_TO_P2_MAP: dict[str, str] = {
    "winner_id": "p2_id",
    "winner_name": "p2_name",
    "winner_hand": "p2_hand",
    "winner_ht": "p2_ht",
    "winner_ioc": "p2_ioc",
    "winner_age": "p2_age",
    "winner_rank": "p2_rank",
    "winner_rank_points": "p2_rank_points",
    "winner_seed": "p2_seed",
    "winner_entry": "p2_entry",
    "w_ace": "p2_ace",
    "w_df": "p2_df",
    "w_svpt": "p2_svpt",
    "w_1stIn": "p2_1stIn",
    "w_1stWon": "p2_1stWon",
    "w_2ndWon": "p2_2ndWon",
    "w_SvGms": "p2_SvGms",
    "w_bpSaved": "p2_bpSaved",
    "w_bpFaced": "p2_bpFaced",
}

# Indoor tournament identifiers (partial matches on tourney_name).
KNOWN_INDOOR_TOURNAMENTS: list[str] = [
    "Paris Masters", "Paris", "Bercy",
    "Basel", "Vienna", "Stockholm", "Marseille",
    "Rotterdam", "Montpellier", "Metz", "Sofia",
    "St. Petersburg", "Moscow", "Antwerp",
    "Milan", "Lyon", "Nur-Sultan", "Astana",
    "Dallas", "ATP Finals",
]

# -----------------------------------------------------------------------
# Feature column names (final dataset) — TRAIN features only
# Weather / news / live odds are RUNTIME-only (API), not model inputs:
# historical values are almost always NaN and would pollute the imputer.
# -----------------------------------------------------------------------
CONTEXT_FEATURES: list[str] = [
    "surface_Hard", "surface_Clay", "surface_Grass", "surface_Carpet",
    "tourney_level_encoded", "round_encoded", "best_of",
    "indoor_outdoor", "altitude", "month",
]

PLAYER_DIFF_FEATURES: list[str] = [
    "ranking_diff", "ranking_points_diff", "log_rank_diff",
    "elo_diff", "elo_surface_diff", "elo_blend_diff",
    "hand_matchup", "home_country_flag",
    "qualifier_flag_diff",
]

INTERACTION_FEATURES: list[str] = [
    "elo_diff_x_bo5",
]

ROLLING_FEATURES: list[str] = [
    "ace_pct_diff", "df_pct_diff",
    "first_serve_in_pct_diff",
    "win_on_1st_serve_pct_diff", "win_on_2nd_serve_pct_diff",
    "bp_saved_pct_diff", "bp_converted_pct_diff",
    "first_serve_return_pts_won_pct_diff",
    "second_serve_return_pts_won_pct_diff",
    "return_games_won_pct_diff",
    "win_pct_surface_diff", "win_pct_last_10_diff",
    "tiebreak_win_pct_diff",
    "first_set_win_rate_diff",
]

FATIGUE_FEATURES: list[str] = [
    "days_rest_diff",
    "minutes_on_court_last_10_days_diff",
    "matches_last_7_days_diff",
]

H2H_FEATURES: list[str] = [
    "h2h_win_pct", "h2h_win_pct_surface",
]

# Closing odds / line movement deliberately excluded (train/serve mismatch).
ODDS_FEATURES: list[str] = []

# Opening odds only — optional "odds" model variant (--use-odds).
ODDS_OPEN_FEATURES: list[str] = [
    "opening_odds_diff",
]

SOS_FEATURES: list[str] = [
    "sos_last_10_diff",
]

MISC_FEATURES: list[str] = [
    "cold_start_flag",
]

# Runtime-only feature groups (API enrichment; NOT in ALL_FEATURES for training)
WEATHER_FEATURES: list[str] = [
    "temperature_c", "wind_speed_kmh", "rain_probability",
    "humidity_pct", "cloud_cover_pct",
]

NEWS_FEATURES: list[str] = [
    "injury_flag_diff", "injury_severity_diff",
    "form_sentiment_diff", "coach_change_diff",
]

LIVE_ODDS_FEATURES: list[str] = [
    "live_implied_prob1", "live_implied_prob2", "live_margin",
]

ALL_FEATURES: list[str] = (
    CONTEXT_FEATURES
    + PLAYER_DIFF_FEATURES
    + INTERACTION_FEATURES
    + ROLLING_FEATURES
    + FATIGUE_FEATURES
    + H2H_FEATURES
    + ODDS_FEATURES
    + SOS_FEATURES
    + MISC_FEATURES
)
