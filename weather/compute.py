#!/usr/bin/env python3
import math
import datetime as dt
from typing import Dict, Any

from astral.sun import elevation as sun_elevation, azimuth as sun_azimuth


I_SC = 1367.0  # W/m^2 solar constant


def _to_rad(deg: float) -> float:
    return math.radians(deg)


def _to_deg(rad: float) -> float:
    return math.degrees(rad)


def solar_geometry(lat: float, lon: float, when_utc: dt.datetime) -> Dict[str, float]:
    """Compute solar elevation/azimuth/zenith using astral for given UTC time."""
    el = float(sun_elevation(lat, lon, when_utc))
    az = float(sun_azimuth(lat, lon, when_utc))
    zen = max(0.0, 90.0 - el)
    return {
        "sun_elevation_deg": el,
        "sun_azimuth_deg": az,
        "sun_zenith_deg": zen,
    }


def extraterrestrial_horizontal(lat: float, when_utc: dt.datetime, zenith_deg: float) -> float:
    """Extraterrestrial irradiance on horizontal plane (GHI0) for current hour center.
    I0h = I_sc * E0 * cosZ. Returns 0 if sun below horizon.
    """
    cosz = max(0.0, math.cos(_to_rad(zenith_deg)))
    if cosz <= 0:
        return 0.0
    n = when_utc.timetuple().tm_yday
    e0 = 1.0 + 0.033 * math.cos(2 * math.pi * n / 365.0)
    return I_SC * e0 * cosz


def clearsky_ghi_haurwitz(zenith_deg: float) -> float:
    """Simple clear-sky GHI via Haurwitz model.
    GHI_cs = 1098 * cosZ * exp(-0.059 / cosZ)
    Returns 0 if cosZ<=0.
    """
    cosz = max(0.0, math.cos(_to_rad(zenith_deg)))
    if cosz <= 0:
        return 0.0
    return 1098.0 * cosz * math.exp(-0.059 / max(1e-6, cosz))


def erbs_decomposition(ghi: float, ghi0: float, zenith_deg: float) -> Dict[str, float]:
    """Split GHI into DHI and DNI using Erbs correlation.
    Requires GHI0 (extraterrestrial on horizontal).
    """
    cosz = max(0.0, math.cos(_to_rad(zenith_deg)))
    if ghi <= 0 or cosz <= 0 or ghi0 <= 0:
        return {"dni": 0.0, "dhi": max(0.0, ghi)}
    kt = min(2.0, ghi / ghi0)

    if kt <= 0.22:
        df = 1.0 - 0.09 * kt
    elif kt <= 0.8:
        df = 0.9511 - 0.1604 * kt + 4.388 * kt ** 2 - 16.638 * kt ** 3 + 12.336 * kt ** 4
    else:
        df = 0.165
    df = max(0.0, min(1.0, df))
    dhi = df * ghi
    dni = max(0.0, (ghi - dhi) / max(1e-6, cosz))
    return {"dni": dni, "dhi": dhi}


def sunshine_duration_hour_from_ghi(ghi_w_m2: float, threshold: float = 120.0) -> float:
    """Approximate sunshine duration per hour using a fixed threshold on GHI.
    Returns either 3600 or 0 seconds in this simple implementation.
    """
    return 3600.0 if (ghi_w_m2 or 0.0) >= threshold else 0.0


def derive_hourly_features(
    *,
    latitude: float,
    longitude: float,
    ts_utc: dt.datetime,
    cfg: Dict[str, Any],
    raw: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute derived solar and PV features for an hourly record using simple models."""
    sun = solar_geometry(latitude, longitude, ts_utc)
    zen = sun["sun_zenith_deg"]
    ghi0 = extraterrestrial_horizontal(latitude, ts_utc, zen)
    ghi_cs = clearsky_ghi_haurwitz(zen)

    # Use provider GHI if available, else 0
    ghi = float(raw.get("ghi_w_m2") or 0.0)
    # Decompose into DNI/DHI using Erbs; fall back to provider fields if present
    if raw.get("dni_w_m2") is not None and raw.get("dhi_w_m2") is not None:
        dni = float(raw.get("dni_w_m2") or 0.0)
        dhi = float(raw.get("dhi_w_m2") or 0.0)
    else:
        ed = erbs_decomposition(ghi, ghi0, zen)
        dni, dhi = ed["dni"], ed["dhi"]

    k_ghi = (ghi / ghi_cs) if ghi_cs > 0 else 0.0
    k_dni = (dni / (ghi_cs / max(1e-6, math.cos(math.radians(zen))))) if (ghi_cs > 0 and math.cos(math.radians(zen)) > 0) else 0.0

    out = {
        **sun,
        "ghi_cs_w_m2": ghi_cs,
        "k_ghi": float(max(0.0, min(2.0, k_ghi))),
        "k_dni": float(max(0.0, min(2.0, k_dni))),
        "sunshine_duration_s_hour": sunshine_duration_hour_from_ghi(ghi),
    }
    return out
