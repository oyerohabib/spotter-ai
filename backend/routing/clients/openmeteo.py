"""Open-Meteo hourly weather client."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherError(Exception):
    pass


def _parse_iso(ts: str) -> datetime:
    # Open-Meteo returns local or UTC depending on params; we request timezone=UTC.
    if ts.endswith("Z"):
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def mm_to_inches(mm: float) -> float:
    return mm / 25.4


def ms_to_mph(ms: float) -> float:
    return ms * 2.2369362921


def fetch_hourly_weather(
    points: Sequence[tuple[float, float]],
    *,
    forecast_days: int = 3,
) -> list[dict[str, Any]]:
    """
    Fetch hourly weather for many lat/lon points.

    Uses Open-Meteo's multi-location API (comma-separated latitudes/longitudes).
    Returns one dict per point with hourly series.
    """
    if not points:
        return []

    # Open-Meteo caps multi-point requests; chunk to stay safe.
    chunk_size = 50
    results: list[dict[str, Any] | None] = [None] * len(points)

    with httpx.Client(timeout=60.0) as client:
        for start in range(0, len(points), chunk_size):
            chunk = points[start : start + chunk_size]
            lats = ",".join(f"{lat:.5f}" for _, lat in chunk)
            lons = ",".join(f"{lon:.5f}" for lon, _ in chunk)
            params = {
                "latitude": lats,
                "longitude": lons,
                "hourly": ",".join(
                    [
                        "wind_speed_10m",
                        "precipitation",
                        "snowfall",
                        "temperature_2m",
                    ]
                ),
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "UTC",
                "forecast_days": forecast_days,
            }
            resp = client.get(FORECAST_URL, params=params)
            if resp.status_code >= 400:
                raise WeatherError(
                    f"Open-Meteo failed ({resp.status_code}): {resp.text[:200]}"
                )
            payload = resp.json()
            # Single-point responses are objects; multi-point are lists.
            entries = payload if isinstance(payload, list) else [payload]
            if len(entries) != len(chunk):
                raise WeatherError(
                    f"Open-Meteo returned {len(entries)} locations for {len(chunk)} points."
                )
            for offset, entry in enumerate(entries):
                hourly = entry.get("hourly") or {}
                times = hourly.get("time") or []
                results[start + offset] = {
                    "lon": chunk[offset][0],
                    "lat": chunk[offset][1],
                    "times": times,
                    "wind_mph": hourly.get("wind_speed_10m") or [],
                    "precip_in": hourly.get("precipitation") or [],
                    "snowfall": hourly.get("snowfall") or [],  # cm in Open-Meteo default
                    "temp_c": hourly.get("temperature_2m") or [],
                }

    return [r for r in results if r is not None]


def weather_at_time(series: dict[str, Any], when: datetime) -> dict[str, float]:
    """Pick the nearest hourly sample to `when`."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    else:
        when = when.astimezone(timezone.utc)

    times = series.get("times") or []
    if not times:
        return {"wind_mph": 0.0, "rain_in_hr": 0.0, "snow_in_hr": 0.0, "temp_c": 0.0}

    parsed = [_parse_iso(t) for t in times]
    best_i = min(range(len(parsed)), key=lambda i: abs((parsed[i] - when).total_seconds()))

    wind = series.get("wind_mph") or []
    precip = series.get("precip_in") or []
    snow_cm = series.get("snowfall") or []
    temp = series.get("temp_c") or []

    wind_mph = float(wind[best_i] or 0) if best_i < len(wind) else 0.0
    rain_in = float(precip[best_i] or 0) if best_i < len(precip) else 0.0
    # Open-Meteo snowfall is cm per hour; convert to inches/hr.
    snow_in = (float(snow_cm[best_i] or 0) / 2.54) if best_i < len(snow_cm) else 0.0
    temp_c = float(temp[best_i] or 0) if best_i < len(temp) else 0.0

    return {
        "wind_mph": round(wind_mph, 2),
        "rain_in_hr": round(rain_in, 3),
        "snow_in_hr": round(snow_in, 3),
        "temp_c": round(temp_c, 1),
        "observed_at": parsed[best_i].isoformat(),
    }


def build_heatmap_series(
    series: dict[str, Any],
    *,
    hours: int = 49,
) -> list[dict[str, Any]]:
    """
    Build 0..hours-1 forecast samples for heatmap slider.
    Intensity uses normalized risk score from wind/precip/snow.
    """
    from routing.risk import classify_rain, classify_snow, classify_wind

    times = series.get("times") or []
    wind = series.get("wind_mph") or []
    precip = series.get("precip_in") or []
    snow_cm = series.get("snowfall") or []

    samples: list[dict[str, Any]] = []
    for i in range(min(hours, len(times))):
        wind_mph = float(wind[i] or 0) if i < len(wind) else 0.0
        rain_in = float(precip[i] or 0) if i < len(precip) else 0.0
        snow_in = (float(snow_cm[i] or 0) / 2.54) if i < len(snow_cm) else 0.0
        score = max(
            int(classify_wind(wind_mph)),
            int(classify_rain(rain_in)),
            int(classify_snow(snow_in)),
        )
        samples.append(
            {
                "hour_offset": i,
                "time": times[i],
                "wind_mph": round(wind_mph, 2),
                "rain_in_hr": round(rain_in, 3),
                "snow_in_hr": round(snow_in, 3),
                "risk_score": score,
                "intensity": score / 4.0,
            }
        )
    return samples
