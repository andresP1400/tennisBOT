"""Weather features for outdoor tennis matches.

Two Open-Meteo endpoints are used:

  - Forecast (GFS):  https://api.open-meteo.com/v1/gfs
                     Free, no API key, ~16 days ahead. Used for current
                     and near-future matches.

  - Historical (ERA5): https://archive-api.open-meteo.com/v1/archive
                     Free, no API key, dates up to ~5 days ago. Used
                     to backfill historical matches (any date < today).

This module exposes:

  - compute_weather_features(df)  : enrich a match DataFrame
  - get_live_weather(tourney, date): single-shot lookup for /api/weather
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from logging_config import get_logger
from features.weather_fetch import fetch_weather_batch
from features.weather_locations import get_coords

logger = get_logger(__name__)

# Back-compat alias for tests/scripts that used the old private name.
_get_coords = get_coords

WEATHER_COLS: list[str] = [
    "temperature_c", "wind_speed_kmh", "rain_probability",
    "humidity_pct", "cloud_cover_pct",
]


def compute_weather_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add weather features to the dataset.

    Works on the ORIGINAL (non-symmetric) dataset.
    Uses tourney_date + tourney_name to fetch historical weather.
    """
    logger.info("\n Computing weather features (Open-Meteo) ...")
    if df.empty:
        for col in WEATHER_COLS:
            df[col] = np.nan
        return df

    df = df.copy()
    df["_date_str"] = pd.to_datetime(df["tourney_date"]).dt.strftime("%Y-%m-%d")
    requests: list[dict] = []
    for _, row in df[["tourney_name", "_date_str"]].drop_duplicates().iterrows():
        coords = get_coords(row["tourney_name"])
        if coords is None:
            continue
        requests.append({
            "lat": coords[0],
            "lon": coords[1],
            "date": row["_date_str"],
            "key": f"{row['tourney_name']}|{row['_date_str']}",
        })
    if not requests:
        logger.info(" No tournament coordinates found. Adding NaN weather columns.")
        for col in WEATHER_COLS:
            df[col] = np.nan
        df = df.drop(columns=["_date_str"], errors="ignore")
        return df

    logger.info(f" Fetching weather for {len(requests)} unique tournament-dates ...")
    weather_data = fetch_weather_batch(requests)
    for col in WEATHER_COLS:
        df[col] = df.apply(
            lambda row, c=col: weather_data.get(
                f"{row['tourney_name']}|{row['_date_str']}", {},
            ).get(c, np.nan),
            axis=1,
        )
    n_with_weather = df["temperature_c"].notna().sum()
    pct = 100 * n_with_weather / len(df) if len(df) > 0 else 0
    logger.info(f" Weather data available for {n_with_weather:,} / {len(df):,} matches ({pct:.1f}%)")
    df = df.drop(columns=["_date_str"], errors="ignore")
    return df


def get_live_weather(tourney_name: str, match_date: str | None = None) -> dict:
    """Get current/recent weather for a tournament location.

    Useful for the /api/predict endpoint to add weather context.
    """
    import datetime as dt
    coords = get_coords(tourney_name)
    if coords is None:
        return {}
    date = match_date or dt.date.today().strftime("%Y-%m-%d")
    result = fetch_weather_batch([{
        "lat": coords[0],
        "lon": coords[1],
        "date": date,
        "key": "live",
    }])
    return result.get("live", {})
