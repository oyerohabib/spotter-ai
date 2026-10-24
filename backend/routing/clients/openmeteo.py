"""Open-Meteo hourly weather client."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Sequence

import httpx
from django.conf import settings

DEFAULT_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# Smaller chunks: shorter URLs + less burst load on shared-host IPs (e.g. Render).
CHUNK_SIZE = 15
MAX_RETRIES = 4
USER_AGENT = "spotter-ai/1.0 (weather-aware truck routing; github.com/oyerohabib/spotter-ai)"

logger = logging.getLogger(__name__)


class WeatherError(Exception):
    pass


def _forecast_url() -> str:
    return (
        getattr(settings, "OPEN_METEO_FORECAST_URL", "") or DEFAULT_FORECAST_URL
    ).rstrip("/")


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


def _point_key(lon: float, lat: float) -> tuple[float, float]:
    # ~100 m grid — enough to collapse near-duplicate corridor samples.
    return (round(lon, 3), round(lat, 3))


def _entry_to_series(lon: float, lat: float, entry: dict[str, Any]) -> dict[str, Any]:
    if entry.get("error"):
        raise WeatherError(
            f"Open-Meteo error: {entry.get('reason') or entry.get('error')}"
        )
    hourly = entry.get("hourly") or {}
    times = hourly.get("time") or []
    return {
        "lon": lon,
        "lat": lat,
        "times": times,
        "wind_mph": hourly.get("wind_speed_10m") or [],
        "precip_in": hourly.get("precipitation") or [],
        "snowfall": hourly.get("snowfall") or [],  # cm in Open-Meteo default
        "temp_c": hourly.get("temperature_2m") or [],
    }


def _fetch_chunk(
    client: httpx.Client,
    chunk: Sequence[tuple[float, float]],
    *,
    forecast_days: int,
) -> list[dict[str, Any]]:
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

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(_forecast_url(), params=params)
        except httpx.TimeoutException as exc:
            last_error = WeatherError("Open-Meteo request timed out.")
            logger.warning("Open-Meteo timeout (attempt %s): %s", attempt + 1, exc)
        except httpx.HTTPError as exc:
            last_error = WeatherError(f"Open-Meteo request failed: {exc}")
            logger.warning("Open-Meteo HTTP error (attempt %s): %s", attempt + 1, exc)
        else:
            if resp.status_code in {429, 503}:
                retry_after = resp.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else (1.5 * (2**attempt))
                except ValueError:
                    delay = 1.5 * (2**attempt)
                delay = min(delay, 20.0)
                logger.warning(
                    "Open-Meteo %s (attempt %s); sleeping %.1fs. Body: %s",
                    resp.status_code,
                    attempt + 1,
                    delay,
                    resp.text[:200],
                )
                last_error = WeatherError(
                    f"Open-Meteo rate-limited ({resp.status_code}): {resp.text[:200]}"
                )
                time.sleep(delay)
                continue

            if resp.status_code >= 400:
                raise WeatherError(
                    f"Open-Meteo failed ({resp.status_code}): {resp.text[:200]}"
                )

            payload = resp.json()
            if isinstance(payload, dict) and payload.get("error"):
                raise WeatherError(
                    f"Open-Meteo error: {payload.get('reason') or 'unknown'}"
                )

            entries = payload if isinstance(payload, list) else [payload]
            if len(entries) != len(chunk):
                raise WeatherError(
                    f"Open-Meteo returned {len(entries)} locations for {len(chunk)} points."
                )
            return [
                _entry_to_series(chunk[i][0], chunk[i][1], entries[i])
                for i in range(len(chunk))
            ]

        # Network failure backoff
        time.sleep(min(1.5 * (2**attempt), 20.0))

    assert last_error is not None
    raise last_error


def fetch_hourly_weather(
    points: Sequence[tuple[float, float]],
    *,
    forecast_days: int = 3,
) -> list[dict[str, Any]]:
    """
    Fetch hourly weather for many lat/lon points.

    Dedupes near-identical coordinates, then uses Open-Meteo's multi-location API
    in small chunks with retries (important on shared hosts like Render).
    """
    if not points:
        return []

    # Map each input index → unique key; fetch unique keys once.
    keys: list[tuple[float, float]] = []
    key_to_unique_idx: dict[tuple[float, float], int] = {}
    point_unique_idxs: list[int] = []
    for lon, lat in points:
        key = _point_key(lon, lat)
        if key not in key_to_unique_idx:
            key_to_unique_idx[key] = len(keys)
            keys.append(key)
        point_unique_idxs.append(key_to_unique_idx[key])

    unique_series: list[dict[str, Any] | None] = [None] * len(keys)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    with httpx.Client(timeout=60.0, headers=headers) as client:
        for start in range(0, len(keys), CHUNK_SIZE):
            chunk = keys[start : start + CHUNK_SIZE]
            fetched = _fetch_chunk(client, chunk, forecast_days=forecast_days)
            for offset, series in enumerate(fetched):
                unique_series[start + offset] = series

    results: list[dict[str, Any]] = []
    for u_idx in point_unique_idxs:
        series = unique_series[u_idx]
        if series is None:
            raise WeatherError("Missing weather series after Open-Meteo fetch.")
        results.append(series)
    return results


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
