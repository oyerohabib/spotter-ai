"""Orchestrate geocoding, routing, weather sampling, risk, and recommendation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .clients import mapbox, openmeteo
from .recommend import recommend_route, summarize_route_risk
from .risk import classify_checkpoint
from .sampling import METERS_PER_MILE, sample_checkpoints


ALLOWED_INTERVALS = {10, 25, 50}
logger = logging.getLogger(__name__)


class AnalyzeError(Exception):
    def __init__(
        self,
        message: str,
        status: int = 400,
        *,
        field: str | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.field = field


def _parse_departure(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AnalyzeError(
            "Enter a valid departure date and time.",
            field="departure_at",
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _optional_float(payload: dict[str, Any], key: str) -> float | None:
    if key not in payload or payload.get(key) in (None, ""):
        return None
    try:
        return float(payload[key])
    except (TypeError, ValueError) as exc:
        raise AnalyzeError(f"{key} must be a number.") from exc


def _resolve_place(
    *,
    label: str,
    field: str,
    query: str,
    lon: float | None,
    lat: float | None,
    name: str | None,
) -> dict[str, Any]:
    if lon is not None and lat is not None:
        return {
            "query": query,
            "name": (name or query).strip() or query,
            "lon": lon,
            "lat": lat,
        }
    try:
        return mapbox.geocode(query)
    except mapbox.MapboxError as exc:
        msg = str(exc)
        if "No geocoding results" in msg:
            raise AnalyzeError(
                f"We couldn’t find that {label}. Pick a suggestion from the list.",
                status=400,
                field=field,
            ) from exc
        if "not configured" in msg:
            raise AnalyzeError(msg, status=502) from exc
        raise AnalyzeError(
            f"Couldn’t look up that {label}. Try another search and pick a suggestion.",
            status=502,
            field=field,
        ) from exc


def analyze_routes(payload: dict[str, Any]) -> dict[str, Any]:
    origin_q = str(payload.get("origin") or "").strip()
    dest_q = str(payload.get("destination") or "").strip()
    if not origin_q:
        raise AnalyzeError("Origin is required.", field="origin")
    if not dest_q:
        raise AnalyzeError("Destination is required.", field="destination")

    try:
        load_weight_lb = float(payload.get("load_weight_lb"))
    except (TypeError, ValueError) as exc:
        raise AnalyzeError(
            "Load weight must be a number.",
            field="load_weight_lb",
        ) from exc
    if load_weight_lb < 0:
        raise AnalyzeError(
            "Load weight must be zero or greater.",
            field="load_weight_lb",
        )

    try:
        interval = int(payload.get("sample_interval_miles", 25))
    except (TypeError, ValueError) as exc:
        raise AnalyzeError(
            "Sample interval must be 10, 25, or 50 miles.",
            field="sample_interval_miles",
        ) from exc
    if interval not in ALLOWED_INTERVALS:
        raise AnalyzeError(
            "Sample interval must be 10, 25, or 50 miles.",
            field="sample_interval_miles",
        )

    departure_raw = payload.get("departure_at")
    if not departure_raw:
        raise AnalyzeError("Departure date/time is required.", field="departure_at")
    departure_at = _parse_departure(str(departure_raw))

    origin_lon = _optional_float(payload, "origin_lon")
    origin_lat = _optional_float(payload, "origin_lat")
    dest_lon = _optional_float(payload, "destination_lon")
    dest_lat = _optional_float(payload, "destination_lat")
    origin_name = str(payload.get("origin_name") or "").strip() or None
    dest_name = str(payload.get("destination_name") or "").strip() or None

    origin = _resolve_place(
        label="origin",
        field="origin",
        query=origin_q,
        lon=origin_lon,
        lat=origin_lat,
        name=origin_name,
    )
    destination = _resolve_place(
        label="destination",
        field="destination",
        query=dest_q,
        lon=dest_lon,
        lat=dest_lat,
        name=dest_name,
    )

    if abs(origin["lon"] - destination["lon"]) < 1e-6 and abs(
        origin["lat"] - destination["lat"]
    ) < 1e-6:
        raise AnalyzeError(
            "Origin and destination must be different places.",
            field="destination",
        )

    try:
        raw_routes = mapbox.get_route_alternatives(
            (origin["lon"], origin["lat"]),
            (destination["lon"], destination["lat"]),
        )
    except mapbox.MapboxError as exc:
        msg = str(exc)
        if "No routes found" in msg or "NoRoute" in msg:
            raise AnalyzeError(
                "No driving route found between those places. Try different locations.",
                status=400,
            ) from exc
        if "not configured" in msg:
            raise AnalyzeError(msg, status=502) from exc
        raise AnalyzeError(
            "Couldn’t calculate routes right now. Please try again in a moment.",
            status=502,
        ) from exc

    # Build checkpoints for each route (without weather yet).
    route_drafts: list[dict[str, Any]] = []
    all_points: list[tuple[float, float]] = []
    point_owners: list[tuple[int, int]] = []  # (route_idx, checkpoint_idx)

    for r_idx, route in enumerate(raw_routes):
        coords = route["coordinates"]
        distance_miles = route["distance_meters"] / METERS_PER_MILE
        checkpoints = sample_checkpoints(
            coords,
            interval_miles=interval,
            total_duration_seconds=route["duration_seconds"],
            departure_at=departure_at,
            total_distance_miles=distance_miles,
        )
        for c_idx, cp in enumerate(checkpoints):
            all_points.append((cp["lon"], cp["lat"]))
            point_owners.append((r_idx, c_idx))
        route_drafts.append(
            {
                **route,
                "distance_miles": round(distance_miles, 2),
                "duration_minutes": round(route["duration_seconds"] / 60.0, 1),
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords,
                },
                "checkpoints": checkpoints,
            }
        )

    heatmap_base_coords = max(raw_routes, key=lambda r: r["distance_meters"])["coordinates"]
    heatmap_samples = sample_checkpoints(
        heatmap_base_coords,
        interval_miles=max(interval, 25),
        total_duration_seconds=max(r["duration_seconds"] for r in raw_routes),
        departure_at=departure_at,
        total_distance_miles=max(r["distance_meters"] for r in raw_routes) / METERS_PER_MILE,
    )
    heatmap_points = [(p["lon"], p["lat"]) for p in heatmap_samples]
    heatmap_offset = len(all_points)
    all_points.extend(heatmap_points)

    try:
        weather_series = openmeteo.fetch_hourly_weather(all_points, forecast_days=3)
    except openmeteo.WeatherError as exc:
        logger.warning("Weather fetch failed: %s", exc)
        detail = str(exc)
        if "rate-limited" in detail.lower() or "429" in detail:
            message = (
                "Weather provider is rate-limiting this server "
                "(common on shared hosts like Render). Wait a minute and try again."
            )
        else:
            message = "Weather data is unavailable right now. Please try again shortly."
        raise AnalyzeError(message, status=502) from exc

    for series_idx, (r_idx, c_idx) in enumerate(point_owners):
        series = weather_series[series_idx]
        cp = route_drafts[r_idx]["checkpoints"][c_idx]
        when = datetime.fromisoformat(cp["eta"])
        wx = openmeteo.weather_at_time(series, when)
        risk = classify_checkpoint(
            wind_mph=wx["wind_mph"],
            rain_in_hr=wx["rain_in_hr"],
            snow_in_hr=wx["snow_in_hr"],
            load_weight_lb=load_weight_lb,
        )
        cp["weather"] = wx
        cp.update(risk)

    routes_out: list[dict[str, Any]] = []
    for draft in route_drafts:
        summary = summarize_route_risk(draft["checkpoints"])
        routes_out.append(
            {
                "id": draft["id"],
                "distance_miles": draft["distance_miles"],
                "duration_seconds": draft["duration_seconds"],
                "duration_minutes": draft["duration_minutes"],
                "geometry": draft["geometry"],
                "checkpoints": draft["checkpoints"],
                "summary": summary,
            }
        )

    recommended_id, reason = recommend_route(routes_out)

    heatmap_features: list[dict[str, Any]] = []
    for i, point in enumerate(heatmap_samples):
        series = weather_series[heatmap_offset + i]
        hourly = openmeteo.build_heatmap_series(series, hours=49)
        heatmap_features.append(
            {
                "lon": point["lon"],
                "lat": point["lat"],
                "miles_from_origin": point["miles_from_origin"],
                "hourly": hourly,
            }
        )

    return {
        "origin": origin,
        "destination": destination,
        "departure_at": departure_at.isoformat(),
        "load_weight_lb": load_weight_lb,
        "sample_interval_miles": interval,
        "routes": routes_out,
        "recommended_route_id": recommended_id,
        "recommendation_reason": reason,
        "heatmap": {
            "hours": 48,
            "points": heatmap_features,
        },
    }
