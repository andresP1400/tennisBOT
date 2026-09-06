"""Open-Meteo HTTP fetching (forecast + historical archive)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import date, datetime, timezone
from typing import Any

from logging_config import get_logger

logger = get_logger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/gfs"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
ARCHIVE_LOOKBACK_DAYS = 7  # archive lags ~5 days; safe window is 7


def select_endpoint(
    match_date: pd.Timestamp | datetime | date | str,
) -> tuple[str, str]:
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


def fetch_weather_batch(requests: list[dict[str, Any]]) -> dict[str, Any]:
    """Fetch weather data from Open-Meteo, automatically picking endpoint per request.

    Each request dict: {"lat": float, "lon": float, "date": "YYYY-MM-DD", "key": str}
    Returns dict mapping key -> weather dict.
    """
    try:
        import requests as req_lib
    except ImportError:
        return {}
    results: dict[str, Any] = {}
    by_query: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for r in requests:
        endpoint, kind = select_endpoint(r["date"])
        query_key = (endpoint, round(r["lat"], 3), round(r["lon"], 3))
        by_query.setdefault(query_key, []).append(
            {**r, "endpoint": endpoint, "kind": kind}
        )

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
                logger.debug(
                    "open-meteo %s returned status %s", endpoint, resp.status_code
                )
                continue
            data = resp.json()
        except Exception as exc:
            logger.warning("open-meteo fetch failed (%s): %s", endpoint, exc)
            continue

        if group[0]["kind"] == "archive":
            _collect_archive_day(data, group, results)
        else:
            _collect_forecast_day(data, group, results)
    return results


def _collect_archive_day(
    data: dict[str, Any], group: list[dict[str, Any]], results: dict[str, Any]
) -> None:
    """Parse ERA5 archive daily rows into the results map."""
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


def _collect_forecast_day(
    data: dict[str, Any], group: list[dict[str, Any]], results: dict[str, Any]
) -> None:
    """Parse GFS hourly rows (12:00-17:00 window) into per-day aggregates."""
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temp = hourly.get("temperature_2m", [])
    wind = hourly.get("wind_speed_10m", [])
    humidity = hourly.get("relative_humidity_2m", [])
    cloud = hourly.get("cloud_cover", [])
    rain_prob = hourly.get("precipitation_probability", [])
    date_weather: dict[str, Any] = {}
    for i, t in enumerate(times):
        if i >= len(temp):
            break
        date_part = t[:10]
        try:
            hour = int(t[11:13]) if len(t) > 11 else 12
        except ValueError:
            continue
        if 12 <= hour <= 17:
            bucket = date_weather.setdefault(
                date_part,
                {
                    "temps": [],
                    "winds": [],
                    "humidity": [],
                    "cloud": [],
                    "rain_prob": [],
                },
            )
            _try_append(bucket["temps"], temp, i)
            _try_append(bucket["winds"], wind, i)
            _try_append(bucket["humidity"], humidity, i)
            _try_append(bucket["cloud"], cloud, i)
            _try_append(bucket["rain_prob"], rain_prob, i)
    for date_part, vals in date_weather.items():
        if not vals["temps"]:
            continue
        wdd = {
            "temperature_c": float(np.mean(vals["temps"])),
            "wind_speed_kmh": float(np.mean(vals["winds"])),
            "rain_probability": (
                float(np.mean(vals["rain_prob"])) / 100.0
                if vals["rain_prob"]
                else np.nan
            ),
            "humidity_pct": (
                float(np.mean(vals["humidity"])) if vals["humidity"] else np.nan
            ),
            "cloud_cover_pct": (
                float(np.mean(vals["cloud"])) if vals["cloud"] else np.nan
            ),
        }
        for r in group:
            if r["date"] == date_part:
                results[r["key"]] = wdd


def _try_append(target: list[float], source: list[Any], index: int) -> None:
    try:
        target.append(float(source[index]))
    except (TypeError, ValueError):
        pass
