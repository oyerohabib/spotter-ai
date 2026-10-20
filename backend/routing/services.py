"""Orchestrate geocoding, routing, weather sampling, risk, and recommendation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .clients import mapbox, openmeteo
from .recommend import recommend_route, summarize_route_risk
from .risk import classify_checkpoint
from .sampling import METERS_PER_MILE, sample_checkpoints


ALLOWED_INTERVALS = {10, 25, 50}


class AnalyzeError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _parse_departure(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AnalyzeError("departure_at must be an ISO-8601 datetime.") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def analyze_routes(payload: dict[str, Any]) -> dict[str, Any]:
    origin_q = str(payload.get("origin") or "").strip()
    dest_q = str(payload.get("destination") or "").strip()
    if not origin_q or not dest_q:
        raise AnalyzeError("origin and destination are required.")

    try:
        load_weight_lb = float(payload.get("load_weight_lb"))
    except (TypeError, ValueError) as exc:
        raise AnalyzeError("load_weight_lb must be a number.") from exc
    if load_weight_lb < 0:
        raise AnalyzeError("load_weight_lb must be non-negative.")

    try:
        interval = int(payload.get("sample_interval_miles", 25))
    except (TypeError, ValueError) as exc:
        raise AnalyzeError("sample_interval_miles must be 10, 25, or 50.") from exc
    if interval not in ALLOWED_INTERVALS:
        raise AnalyzeError("sample_interval_miles must be 10, 25, or 50.")

    departure_raw = payload.get("departure_at")
    if not departure_raw:
        raise AnalyzeError("departure_at is required.")
    departure_at = _parse_departure(str(departure_raw))

    try:
        origin = mapbox.geocode(origin_q)
        destination = mapbox.geocode(dest_q)
        raw_routes = mapbox.get_route_alternatives(
            (origin["lon"], origin["lat"]),
            (destination["lon"], destination["lat"]),
        )
    except mapbox.MapboxError as exc:
        raise AnalyzeError(str(exc), status=502) from exc

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

    # Corridor heatmap points: subsample recommended geometry later; for now use
    # evenly spaced points from the longest route for a shared corridor grid.
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
        raise AnalyzeError(str(exc), status=502) from exc

    # Attach weather + risk to route checkpoints.
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

    # Heatmap: for each corridor point, 0–48h risk intensity series.
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
