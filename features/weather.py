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

import os
import sys
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from logging_config import get_logger
logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FORECAST_URL = "https://api.open-meteo.com/v1/gfs"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
ARCHIVE_LOOKBACK_DAYS = 7  # archive lags ~5 days; safe window is 7

# Tournament city coordinates for weather lookup
TOURNAMENT_COORDS: dict[str, tuple[float, float]] = {
    "Melbourne": (-37.81, 144.96),
    "Sydney": (-33.87, 151.21),
    "Brisbane": (-27.47, 153.03),
    "Adelaide": (-34.93, 138.60),
    "Auckland": (-36.85, 174.76),
    "Indian Wells": (33.72, -116.31),
    "Miami": (25.78, -80.22),
    "Cincinnati": (39.10, -84.51),
    "Washington": (38.90, -77.04),
    "Atlanta": (33.75, -84.39),
    "Dallas": (32.78, -96.80),
    "Houston": (29.76, -95.37),
    "Winston": (36.10, -80.27),
    "Paris": (48.86, 2.35),
    "Roland Garros": (48.84, 2.25),
    "French Open": (48.84, 2.25),
    "Marseille": (43.30, 5.37),
    "Lyon": (45.76, 4.84),
    "Montpellier": (43.61, 3.88),
    "Metz": (49.12, 6.18),
    "Wimbledon": (51.42, -0.22),
    "Queen": (51.49, -0.19),
    "Eastbourne": (50.77, 0.28),
    "Rome": (41.90, 12.50),
    "Madrid": (40.42, -3.70),
    "Barcelona": (41.39, 2.17),
    "Mallorca": (39.57, 2.65),
    "Monte Carlo": (43.74, 7.43),
    "Hamburg": (53.55, 10.00),
    "Stuttgart": (48.78, 9.18),
    "Halle": (52.06, 8.36),
    "Queen's Club": (51.49, -0.19),
    "s-Hertogenbosch": (51.69, 5.30),
    "Berlin": (52.52, 13.40),
    "Munich": (48.14, 11.58),
    "Vienna": (48.21, 16.37),
    "Basel": (47.56, 7.59),
    "Stockholm": (59.33, 18.07),
    "St. Petersburg": (59.93, 30.32),
    "Moscow": (55.76, 37.62),
    "Dubai": (25.27, 55.30),
    "Doha": (25.29, 51.53),
    "Beijing": (39.90, 116.40),
    "Shanghai": (31.23, 121.47),
    "Tokyo": (35.68, 139.69),
    "Chengdu": (30.57, 104.07),
    "Zhuhai": (22.27, 113.57),
    "Hong Kong": (22.30, 114.17),
    "Seoul": (37.57, 126.98),
    "Buenos Aires": (-34.61, -58.38),
    "Rio de Janeiro": (-22.91, -43.17),
    "Sao Paulo": (-23.55, -46.63),
    "Bogota": (4.71, -74.07),
    "Quito": (-0.18, -78.47),
    "Mexico City": (19.43, -99.13),
    "Acapulco": (16.86, -99.88),
    "Toronto": (43.65, -79.38),
    "Montreal": (45.50, -73.57),
    "Johannesburg": (-26.20, 28.05),
    "Cape Town": (-33.92, 18.42),
    "Antwerp": (51.22, 4.40),
    "Rotterdam": (51.92, 4.48),
    "Sofia": (42.70, 23.32),
    "Pune": (18.52, 73.86),
}

WEATHER_COLS: list[str] = [
    "temperature_c", "wind_speed_kmh", "rain_probability",
    "humidity_pct", "cloud_cover_pct",
]


def _get_coords(tourney_name: str) -> tuple[float, float] | None:
    """Return (lat, lon) for a tournament by fuzzy name match."""
    if not isinstance(tourney_name, str):
        return None
    t_lower = tourney_name.lower()
    for key, coords in TOURNAMENT_COORDS.items():
        if key.lower() in t_lower:
            return coords
    return None


def _select_endpoint(match_date: pd.Timestamp | datetime | date | str) -> tuple[str, str]:
    """Pick the right Open-Meteo endpoint based on how recent the date is."""
    today = datetime.now(timezone.utc).date()
    if isinstance(match_date, str):
        match_date = pd.to_datetime(match_date).date()
    elif isinstance(match_date, pd.Timestamp):
        match_date = match_date.date()
    elif isinstance(match_date, datetime):
        match_date = match_date.date()
    if not isinstance(match_date, date):
        return FORECAST_URL, "forecast"
    delta_days = (today - match_date).days
    if delta_days >= ARCHIVE_LOOKBACK_DAYS:
        return ARCHIVE_URL, "archive"
    return FORECAST_URL, "forecast"


def _fetch_weather_batch(requests: list[dict]) -> dict:
    """Fetch weather data from Open-Meteo, automatically picking endpoint per request.

    Each request dict: {"lat": float, "lon": float, "date": "YYYY-MM-DD", "key": str}
    Returns dict mapping key -> weather dict.
    """
    try:
        import requests as req_lib
    except ImportError:
        return {}
    results: dict = {}
    by_query: dict[tuple, list[dict]] = {}
    for r in requests:
        endpoint, kind = _select_endpoint(r["date"])
        query_key = (endpoint, round(r["lat"], 3), round(r["lon"], 3))
        by_query.setdefault(query_key, []).append({**r, "endpoint": endpoint, "kind": kind})

    for (endpoint, lat, lon), group in by_query.items():
        try:
            dates = sorted({r["date"] for r in group})
            kind = group[0]["kind"]
            if kind == "archive":
                url = (
                    f"{endpoint}?latitude={lat}&longitude={lon}"
                    f"&start_date={dates[0]}&end_date={dates[-1]}"
                    f"&daily=temperature_2m_max,temperature_2m_min,"
                    f"precipitation_sum,wind_speed_10m_max,"
                    f"shortwave_radiation_sum"
                    f"&timezone=auto"
                )
            else:
                url = (
                    f"{endpoint}?latitude={lat}&longitude={lon}"
                    f"&hourly=temperature_2m,wind_speed_10m,relative_humidity_2m,"
                    f"cloud_cover,precipitation_probability"
                    f"&start_date={dates[0]}&end_date={dates[-1]}"
                    f"&timezone=auto"
                )
            resp = req_lib.get(url, timeout=30)
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception:
            continue

        if group[0]["kind"] == "archive":
            daily = data.get("daily", {})
            times = daily.get("time", [])
            temp_max = daily.get("temperature_2m_max", [])
            temp_min = daily.get("temperature_2m_min", [])
            precip = daily.get("precipitation_sum", [])
            wind = daily.get("wind_speed_10m_max", [])
            for i, day_str in enumerate(times):
                if i >= len(temp_max):
                    break
                try:
                    tmax = float(temp_max[i])
                    tmin = float(temp_min[i])
                    p = float(precip[i]) if i < len(precip) else 0.0
                    w = float(wind[i]) if i < len(wind) else 0.0
                except (TypeError, ValueError):
                    continue
                wdd = {
                    "temperature_c": (tmax + tmin) / 2.0,
                    "wind_speed_kmh": w,
                    "rain_probability": min(1.0, p / 5.0),
                    "humidity_pct": np.nan,
                    "cloud_cover_pct": np.nan,
                }
                for r in group:
                    if r["date"] == day_str:
                        results[r["key"]] = wdd
        else:
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temp = hourly.get("temperature_2m", [])
            wind = hourly.get("wind_speed_10m", [])
            humidity = hourly.get("relative_humidity_2m", [])
            cloud = hourly.get("cloud_cover", [])
            rain_prob = hourly.get("precipitation_probability", [])
            date_weather: dict = {}
            for i, t in enumerate(times):
                if i >= len(temp):
                    break
                date_part = t[:10]
                try:
                    hour = int(t[11:13]) if len(t) > 11 else 12
                except ValueError:
                    continue
                if 12 <= hour <= 17:
                    if date_part not in date_weather:
                        date_weather[date_part] = {
                            "temps": [], "winds": [], "humidity": [],
                            "cloud": [], "rain_prob": [],
                        }
                    try:
                        date_weather[date_part]["temps"].append(float(temp[i]))
                    except (TypeError, ValueError):
                        pass
                    try:
                        date_weather[date_part]["winds"].append(float(wind[i]))
                    except (TypeError, ValueError):
                        pass
                    try:
                        date_weather[date_part]["humidity"].append(float(humidity[i]))
                    except (TypeError, ValueError):
                        pass
                    try:
                        date_weather[date_part]["cloud"].append(float(cloud[i]))
                    except (TypeError, ValueError):
                        pass
                    try:
                        date_weather[date_part]["rain_prob"].append(float(rain_prob[i]))
                    except (TypeError, ValueError):
                        pass
            for date_part, vals in date_weather.items():
                if not vals["temps"]:
                    continue
                wdd = {
                    "temperature_c": float(np.mean(vals["temps"])),
                    "wind_speed_kmh": float(np.mean(vals["winds"])),
                    "rain_probability": float(np.mean(vals["rain_prob"])) / 100.0
                    if vals["rain_prob"] else np.nan,
                    "humidity_pct": float(np.mean(vals["humidity"]))
                    if vals["humidity"] else np.nan,
                    "cloud_cover_pct": float(np.mean(vals["cloud"]))
                    if vals["cloud"] else np.nan,
                }
                for r in group:
                    if r["date"] == date_part:
                        results[r["key"]] = wdd
    return results


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
        coords = _get_coords(row["tourney_name"])
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
    weather_data = _fetch_weather_batch(requests)
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
    coords = _get_coords(tourney_name)
    if coords is None:
        return {}
    date = match_date or dt.date.today().strftime("%Y-%m-%d")
    result = _fetch_weather_batch([{
        "lat": coords[0],
        "lon": coords[1],
        "date": date,
        "key": "live",
    }])
    return result.get("live", {})
