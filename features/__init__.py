"""Features subpackage: feature engineering modules for tennis match prediction."""
from features.elo import compute_elo_features, EloRatingSystem
from features.fatigue import compute_fatigue_features, FatigueTracker
from features.h2h import compute_h2h_features, H2HTracker
from features.player import compute_player_features
from features.rolling_stats import compute_rolling_features, PlayerStatsTracker
from features.cleaning import (
    add_altitude,
    add_indoor_flag,
    clean_pipeline,
    create_symmetric_rows,
    impute_missing,
    load_players,
    load_raw_matches,
    parse_dates,
    remove_incomplete_matches,
)
from features.context import compute_context_features
from features.weather import compute_weather_features, get_live_weather
from features.odds import load_odds_data, merge_odds_to_matches
from features.builder import build_features
from features.live_odds import LiveOddsScraper, compute_value_bets
from features.player_news import PlayerNewsResearcher

__all__ = [
    "EloRatingSystem",
    "compute_elo_features",
    "FatigueTracker",
    "compute_fatigue_features",
    "H2HTracker",
    "compute_h2h_features",
    "compute_player_features",
    "PlayerStatsTracker",
    "compute_rolling_features",
    "load_raw_matches",
    "load_players",
    "remove_incomplete_matches",
    "parse_dates",
    "impute_missing",
    "add_indoor_flag",
    "add_altitude",
    "create_symmetric_rows",
    "clean_pipeline",
    "compute_context_features",
    "compute_weather_features",
    "get_live_weather",
    "load_odds_data",
    "merge_odds_to_matches",
    "build_features",
    "LiveOddsScraper",
    "compute_value_bets",
    "PlayerNewsResearcher",
]
