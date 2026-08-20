"""Central configuration for the TennisBot prediction pipeline.

All paths, constants, and hyperparameters are defined here.
"""
from pathlib import Path

# backend/src/config.py -> repo root is three levels up.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Public path constants for callers that need the source or repo root
# (matches SRC_DIR/BASE_DIR computed inline in api_server, smoke_test, ...).
SRC_DIR: Path = _PROJECT_ROOT / "backend" / "src"
BASE_DIR: Path = _PROJECT_ROOT

# Paths (Path objects so they compose with / and support .resolve())
PROCESSED_DIR: Path = _PROJECT_ROOT / "data" / "processed"
MODELS_DIR: Path = _PROJECT_ROOT / "models" / "saved"
REPORTS_DIR: Path = _PROJECT_ROOT / "reports"
RAW_DIR: Path = _PROJECT_ROOT / "data" / "raw"

# Data sources
# Jeff Sackmann public tennis repos were removed (~June 2026). We pull the
# same layout from a maintained mirror (see data/DATA_SOURCES.md).
DATA_REPO_BASE = "https://raw.githubusercontent.com/Artur73737/ATP-WTA_DATA/main"
ATP_REPO_BASE = f"{DATA_REPO_BASE}/raw/atp"
WTA_REPO_BASE = f"{DATA_REPO_BASE}/raw/wta"
# Optional live fallback for odds if mirror file is missing
ODDS_LIVE_BASE = "http://www.tennis-data.co.uk"

# Year range for match files
MATCH_YEAR_START = 1968
MATCH_YEAR_END = 2026  # inclusive

# Years with reliable granular stats (ace, df, bp, etc.)
STATS_RELIABLE_FROM = 2000

# Feature engineering
ROLLING_WINDOW = 20  # default rolling window (matches)
ROLLING_WINDOWS = [10, 20, 30]
ELO_K_FACTOR = 32
ELO_INITIAL = 1500
DECAY_HALF_LIFE = 10

# --- ELO refinements (ported from rigorous fork) ---
# K multiplier by tournament level: Slam win moves rating more than Challenger.
ELO_LEVEL_K_MULT = {
    "G": 1.2,   # Grand Slam
    "M": 1.1,   # Masters 1000
    "F": 1.1,   # Tour Finals
    "A": 1.0,   # ATP 500/250
    "D": 0.85,  # Davis Cup
    "C": 0.9,   # Challengers
}
# Margin-of-victory: extra K weight per set of margin beyond the minimum.
ELO_MOV_BONUS_PER_SET = 0.1
# Inactivity decay after long layoffs.
ELO_INACTIVITY_GRACE_DAYS = 90
ELO_INACTIVITY_HALF_LIFE_DAYS = 730
# Surface blend: weight of surface ELO = n_surf / (n_surf + shrinkage).
ELO_SURFACE_BLEND_SHRINKAGE = 10

# Data cleaning
DEFAULT_RANK_IMPUTATION = 2000
COLD_START_THRESHOLD = 10

# Temporal split boundaries
TRAIN_END_YEAR = 2021
VAL_START_YEAR = 2022
VAL_END_YEAR = 2023
TEST_START_YEAR = 2024

# Model hyperparameters (defaults -- Optuna will override)
LGBM_PARAMS = {
    "objective": "binary",
    "metric": "binary_logloss",
    "boosting_type": "gbdt",
    "num_leaves": 63,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbose": -1,
    "n_estimators": 1000,
    "early_stopping_rounds": 50,
}

XGB_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "n_estimators": 1000,
    "early_stopping_rounds": 50,
    "verbosity": 0,
}

# Surfaces (used by ELO surface mapping and feature encoding)
SURFACES = ["Hard", "Clay", "Grass", "Carpet"]

# Tournament levels mapping
TOURNEY_LEVEL_MAP = {
    "G": "Grand Slam",
    "M": "Masters 1000",
    "A": "ATP 500/250",
    "D": "Davis Cup",
    "F": "Tour Finals",
    "C": "Challengers",
}

# Round ordering (for ordinal encoding)
ROUND_ORDER = {
    "R128": 1, "R64": 2, "R32": 3, "R16": 4,
    "QF": 5, "SF": 6, "F": 7, "RR": 3,
}

# Estimated days elapsed from tournament start for each round.
# Sackmann's tourney_date is the tournament START date for every match;
# without this offset all matches in an event share one date, which breaks
# fatigue features and intra-tournament chronological ordering.
ROUND_DAY_OFFSET = {
    "R128": 0, "R64": 2, "R32": 4, "R16": 6,
    "QF": 8, "SF": 10, "F": 12,
    "RR": 2, "BR": 11, "ER": 0,
}

# Altitude data (meters above sea level) for key tournament cities
CITY_ALTITUDE = {
    "Madrid": 667,
    "Bogota": 2640,
    "Quito": 2850,
    "Mexico City": 2240,
    "Johannesburg": 1753,
    "Denver": 1609,
    "Sao Paulo": 760,
    "Beijing": 43,
    "Rome": 21,
    "Paris": 35,
    "London": 11,
    "New York": 10,
    "Melbourne": 31,
    "Miami": 2,
    "Indian Wells": 0,
    "Monte Carlo": 62,
    "Shanghai": 4,
    "Toronto": 76,
    "Montreal": 233,
    "Cincinnati": 267,
    "Barcelona": 12,
    "Stuttgart": 245,
    "Hamburg": 6,
    "Dubai": 5,
    "Doha": 10,
    "Brisbane": 27,
    "Auckland": 0,
    "Sydney": 58,
    "Tokyo": 40,
    "Vienna": 171,
    "Basel": 260,
    "Stockholm": 28,
    "St. Petersburg": 3,
    "Moscow": 156,
    "Buenos Aires": 25,
    "Rio de Janeiro": 11,
    "Acapulco": 3,
    "Halle": 79,
    "Queen's Club": 11,
    "Eastbourne": 7,
    "Wimbledon": 40,
    "Washington": 0,
    "Winston-Salem": 283,
    "US Open": 10,
    "Zhuhai": 0,
    "Chengdu": 500,
    "Antwerp": 7,
    "Metz": 179,
    "Sofia": 550,
    "Marseille": 12,
    "Rotterdam": 0,
    "Montpellier": 56,
    "Dallas": 131,
    "Adelaide": 50,
    "Pune": 560,
}
