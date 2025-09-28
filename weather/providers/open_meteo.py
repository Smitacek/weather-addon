#!/usr/bin/env python3
import datetime as dt
import json
from typing import Dict, List, Any

import requests


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def _iso_z(ts: str) -> str:
    # Ensure trailing 'Z' for UTC
    if ts.endswith("Z"):
        return ts
    return ts + "Z"


def fetch_open_meteo(
    *,
    latitude: float,
    longitude: float,
    hourly_horizon_h: int,
    forecast_days: int,
    units: str = "metric",
) -> Dict[str, Any]:
    """Fetch hourly and daily forecast from Open-Meteo.

    Returns dict with keys: issue_time_utc, hourly: List[dict], daily: List[dict]
    """

    # unit parameters
    temp_unit = "celsius" if units == "metric" else "fahrenheit"
    wind_unit = "ms" if units == "metric" else "mph"

    hourly_vars = [
        "temperature_2m",
        "relative_humidity_2m",
        "dewpoint_2m",
        "pressure_msl",
        "precipitation",
        "precipitation_probability",
        "cloudcover",
        "shortwave_radiation",
        "direct_radiation",
        "diffuse_radiation",
        "windspeed_10m",
        "winddirection_10m",
        "windgusts_10m",
        "visibility",
    ]
    daily_vars = [
        "sunrise",
        "sunset",
        "sunshine_duration",
        "precipitation_sum",
        "precipitation_probability_max",
        "temperature_2m_max",
        "temperature_2m_min",
        "wind_speed_10m_max",
    ]

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(hourly_vars),
        "daily": ",".join(daily_vars),
        "timezone": "UTC",
        "temperature_unit": temp_unit,
        "windspeed_unit": wind_unit,
        "forecast_days": max(1, min(16, int(forecast_days))),
        # limit hourly to horizon if supported; Open-Meteo returns at least 7 days
    }

    resp = requests.get(OPEN_METEO_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    issue_time_utc = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    hourly: List[Dict[str, Any]] = []
    htime = data.get("hourly", {}).get("time", [])

    def _get(name: str, default=None):
        return data.get("hourly", {}).get(name, []) or [default] * len(htime)

    for i, t in enumerate(htime):
        rec = {
            "ts_utc": _iso_z(t),
            "temp_2m_c": _get("temperature_2m")[i],
            "relative_humidity_pct": _get("relative_humidity_2m")[i],
            "dew_point_c": _get("dewpoint_2m")[i],
            "mslp_hpa": _get("pressure_msl")[i],
            "precip_mm": _get("precipitation")[i],
            "precip_probability_pct": _get("precipitation_probability")[i],
            "cloud_cover_pct": _get("cloudcover")[i],
            "ghi_w_m2": _get("shortwave_radiation")[i],
            "dni_w_m2": _get("direct_radiation")[i],
            "dhi_w_m2": _get("diffuse_radiation")[i],
            "wind_speed_10m_ms": _get("windspeed_10m")[i],
            "wind_dir_10m_deg": _get("winddirection_10m")[i],
            "wind_gust_10m_ms": _get("windgusts_10m")[i],
            "visibility_m": _get("visibility")[i],
        }
        hourly.append(rec)

    # truncate to requested horizon from now
    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    horizon_end = now + dt.timedelta(hours=int(hourly_horizon_h))
    hourly = [
        h for h in hourly
        if now <= dt.datetime.fromisoformat(h["ts_utc"].replace("Z", "+00:00")) <= horizon_end
    ]

    # daily
    daily: List[Dict[str, Any]] = []
    dtime = data.get("daily", {}).get("time", [])

    def _d(name: str, default=None):
        return data.get("daily", {}).get(name, []) or [default] * len(dtime)

    for i, d in enumerate(dtime):
        daily.append({
            "date_utc": d,
            "sunrise": _iso_z(_d("sunrise")[i]) if _d("sunrise")[i] else None,
            "sunset": _iso_z(_d("sunset")[i]) if _d("sunset")[i] else None,
            "sunshine_duration_s": _d("sunshine_duration")[i],
            "precip_day_total_mm": _d("precipitation_sum")[i],
            "precip_probability_max_pct": _d("precipitation_probability_max")[i],
            "temp_day_max_c": _d("temperature_2m_max")[i],
            "temp_day_min_c": _d("temperature_2m_min")[i],
            "wind_day_max_ms": _d("wind_speed_10m_max")[i],
        })

    return {
        "issue_time_utc": issue_time_utc,
        "hourly": hourly,
        "daily": daily,
    }
