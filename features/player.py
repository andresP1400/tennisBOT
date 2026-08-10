"""Player-level features (non-rolling).

Computes:
  - ranking_diff          : p1_rank - p2_rank
  - ranking_points_diff   : p1_rank_points - p2_rank_points
  - age_diff              : p1_age - p2_age
  - height_diff           : p1_ht - p2_ht
  - hand_matchup          : encoded handedness matchup
  - home_country_flag     : 1 if player is from tournament country
  - qualifier_flag_diff   : difference in qualifier status
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

from logging_config import get_logger
logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TOURNAMENT_COUNTRIES: dict[str, str] = {
    "Australian Open": "AUS", "Melbourne": "AUS", "Brisbane": "AUS",
    "Adelaide": "AUS", "Sydney": "AUS",
    "Roland Garros": "FRA", "Paris": "FRA", "Marseille": "FRA",
    "Lyon": "FRA", "Montpellier": "FRA",
    "Wimbledon": "GBR", "Queen": "GBR", "Eastbourne": "GBR",
    "US Open": "USA", "Indian Wells": "USA", "Miami": "USA",
    "Cincinnati": "USA", "Washington": "USA", "Atlanta": "USA",
    "Winston": "USA", "Dallas": "USA", "Houston": "USA",
    "Madrid": "ESP", "Barcelona": "ESP", "Mallorca": "ESP",
    "Rome": "ITA", "Milan": "ITA",
    "Monte Carlo": "MON",
    "Hamburg": "GER", "Halle": "GER", "Munich": "GER", "Stuttgart": "GER",
    "Rotterdam": "NED",
    "Basel": "SUI",
    "Vienna": "AUT",
    "Stockholm": "SWE",
    "St. Petersburg": "RUS", "Moscow": "RUS",
    "Beijing": "CHN", "Shanghai": "CHN", "Chengdu": "CHN", "Zhuhai": "CHN",
    "Tokyo": "JPN",
    "Dubai": "UAE",
    "Doha": "QAT",
    "Buenos Aires": "ARG",
    "Rio de Janeiro": "BRA", "Sao Paulo": "BRA",
    "Acapulco": "MEX",
    "Bogota": "COL",
    "Santiago": "CHI",
    "Sofia": "BUL",
    "Antwerp": "BEL",
    "Toronto": "CAN", "Montreal": "CAN",
    "Auckland": "NZL",
    "Metz": "FRA",
    "Nur-Sultan": "KAZ", "Astana": "KAZ",
    "Pune": "IND", "Chennai": "IND", "New Delhi": "IND",
}


def _get_tournament_country(tourney_name: str) -> str:
    """Attempt to map tournament name to IOC country code."""
    if not isinstance(tourney_name, str):
        return ""
    for key, ioc in TOURNAMENT_COUNTRIES.items():
        if key.lower() in tourney_name.lower():
            return ioc
    return ""


def compute_player_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute player-level difference features on the SYMMETRIC dataset.

    Assumes columns p1_*, p2_* are already present.
    """
    logger.info("\n  Computing player-level features ...")
    df["ranking_diff"] = df["p1_rank"] - df["p2_rank"]
    df["ranking_points_diff"] = df["p1_rank_points"] - df["p2_rank_points"]
    # log-rank dampens outliers (rank 1 vs 2000 is not 2000x more signal than 1 vs 50)
    p1r = df["p1_rank"].clip(lower=1)
    p2r = df["p2_rank"].clip(lower=1)
    df["log_rank_diff"] = np.log(p1r) - np.log(p2r)
    df["age_diff"] = df["p1_age"] - df["p2_age"]
    df["height_diff"] = df["p1_ht"] - df["p2_ht"]
    hand_map = {"R": 0, "L": 1, "U": 0.5}
    df["p1_hand_enc"] = df["p1_hand"].map(hand_map).fillna(0.5)
    df["p2_hand_enc"] = df["p2_hand"].map(hand_map).fillna(0.5)
    df["hand_matchup"] = (df["p1_hand_enc"] != df["p2_hand_enc"]).astype(int)
    df["_tourney_country"] = df["tourney_name"].apply(_get_tournament_country)
    df["p1_home"] = (df["p1_ioc"] == df["_tourney_country"]).astype(int)
    df["p2_home"] = (df["p2_ioc"] == df["_tourney_country"]).astype(int)
    df["home_country_flag"] = df["p1_home"] - df["p2_home"]
    df["p1_is_qualifier"] = df["p1_entry"].fillna("").str.contains("Q", case=False).astype(int)
    df["p2_is_qualifier"] = df["p2_entry"].fillna("").str.contains("Q", case=False).astype(int)
    df["qualifier_flag_diff"] = df["p1_is_qualifier"] - df["p2_is_qualifier"]
    df = df.drop(
        columns=[
            "p1_hand_enc", "p2_hand_enc", "_tourney_country",
            "p1_home", "p2_home", "p1_is_qualifier", "p2_is_qualifier",
        ],
        errors="ignore",
    )
    n_lefty_matchups = (df["hand_matchup"] == 1).sum()
    logger.info(f"  Player features added. Lefty-vs-righty matchups: {n_lefty_matchups:,}")
    return df
