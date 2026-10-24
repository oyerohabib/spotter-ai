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


def _parse_trip_inputs(payload: dict[str, Any]) -> dict[str, Any]:
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

    return {
        "origin_q": origin_q,
        "dest_q": dest_q,
        "load_weight_lb": load_weight_lb,
        "interval": interval,
        "departure_at": departure_at,
        "origin_lon": _optional_float(payload, "origin_lon"),
        "origin_lat": _optional_float(payload, "origin_lat"),
        "dest_lon": _optional_float(payload, "destination_lon"),
        "dest_lat": _optional_float(payload, "destination_lat"),
        "origin_name": str(payload.get("origin_name") or "").strip() or None,
        "dest_name": str(payload.get("destination_name") or "").strip() or None,
    }


def plan_routes(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Geocode + Mapbox alternatives + checkpoint sampling (no weather).

    Returns a plan the browser can enrich with Open-Meteo, then POST to score_routes.
    """
    inputs = _parse_trip_inputs(payload)

    origin = _resolve_place(
        label="origin",
        field="origin",
        query=inputs["origin_q"],
        lon=inputs["origin_lon"],
        lat=inputs["origin_lat"],
        name=inputs["origin_name"],
    )
    destination = _resolve_place(
        label="destination",
        field="destination",
        query=inputs["dest_q"],
        lon=inputs["dest_lon"],
        lat=inputs["dest_lat"],
        name=inputs["dest_name"],
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

    interval = inputs["interval"]
    departure_at = inputs["departure_at"]
    routes_out: list[dict[str, Any]] = []
    weather_points: list[dict[str, float]] = []

    for route in raw_routes:
        coords = route["coordinates"]
        distance_miles = route["distance_meters"] / METERS_PER_MILE
        checkpoints = sample_checkpoints(
            coords,
            interval_miles=interval,
            total_duration_seconds=route["duration_seconds"],
            departure_at=departure_at,
            total_distance_miles=distance_miles,
        )
        for cp in checkpoints:
            weather_points.append({"lon": cp["lon"], "lat": cp["lat"]})
        routes_out.append(
            {
                "id": route["id"],
                "distance_miles": round(distance_miles, 2),
                "duration_seconds": route["duration_seconds"],
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
    heatmap_point_meta = [
        {
            "lon": p["lon"],
            "lat": p["lat"],
            "miles_from_origin": p["miles_from_origin"],
        }
        for p in heatmap_samples
    ]
    for point in heatmap_point_meta:
        weather_points.append({"lon": point["lon"], "lat": point["lat"]})

    return {
        "origin": origin,
        "destination": destination,
        "departure_at": departure_at.isoformat(),
        "load_weight_lb": inputs["load_weight_lb"],
        "sample_interval_miles": interval,
        "routes": routes_out,
        "heatmap": {
            "hours": 48,
            "points": heatmap_point_meta,
        },
        "weather_points": weather_points,
    }


def score_routes(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Attach client-fetched Open-Meteo series to a plan and compute risk + recommendation.
    """
    plan = payload.get("plan")
    if not isinstance(plan, dict):
        raise AnalyzeError("Plan payload is required.", field="plan")

    weather_series = payload.get("weather_series")
    if not isinstance(weather_series, list) or not weather_series:
        raise AnalyzeError(
            "Weather series from Open-Meteo is required.",
            field="weather_series",
        )

    routes_in = plan.get("routes")
    if not isinstance(routes_in, list) or not routes_in:
        raise AnalyzeError("Plan must include routes.", field="plan")

    heatmap = plan.get("heatmap") or {}
    heatmap_points = heatmap.get("points") if isinstance(heatmap, dict) else None
    if not isinstance(heatmap_points, list):
        heatmap_points = []

    try:
        load_weight_lb = float(plan.get("load_weight_lb"))
    except (TypeError, ValueError) as exc:
        raise AnalyzeError(
            "Load weight must be a number.",
            field="load_weight_lb",
        ) from exc

    checkpoint_count = sum(
        len(r.get("checkpoints") or []) for r in routes_in if isinstance(r, dict)
    )
    expected = checkpoint_count + len(heatmap_points)
    if len(weather_series) != expected:
        raise AnalyzeError(
            f"Expected {expected} weather series entries, got {len(weather_series)}.",
            field="weather_series",
        )

    series_idx = 0
    routes_out: list[dict[str, Any]] = []
    for route in routes_in:
        if not isinstance(route, dict):
            raise AnalyzeError("Invalid route in plan.", field="plan")
        checkpoints = route.get("checkpoints") or []
        if not isinstance(checkpoints, list):
            raise AnalyzeError("Invalid checkpoints in plan.", field="plan")

        scored_checkpoints: list[dict[str, Any]] = []
        for cp in checkpoints:
            if not isinstance(cp, dict):
                raise AnalyzeError("Invalid checkpoint in plan.", field="plan")
            series = weather_series[series_idx]
            series_idx += 1
            if not isinstance(series, dict):
                raise AnalyzeError("Invalid weather series entry.", field="weather_series")
            eta_raw = cp.get("eta")
            if not eta_raw:
                raise AnalyzeError("Checkpoint is missing ETA.", field="plan")
            when = datetime.fromisoformat(str(eta_raw).replace("Z", "+00:00"))
            wx = openmeteo.weather_at_time(series, when)
            risk = classify_checkpoint(
                wind_mph=wx["wind_mph"],
                rain_in_hr=wx["rain_in_hr"],
                snow_in_hr=wx["snow_in_hr"],
                load_weight_lb=load_weight_lb,
            )
            scored = {**cp, "weather": wx, **risk}
            scored_checkpoints.append(scored)

        summary = summarize_route_risk(scored_checkpoints)
        routes_out.append(
            {
                "id": route.get("id"),
                "distance_miles": route.get("distance_miles"),
                "duration_seconds": route.get("duration_seconds"),
                "duration_minutes": route.get("duration_minutes"),
                "geometry": route.get("geometry"),
                "checkpoints": scored_checkpoints,
                "summary": summary,
            }
        )

    recommended_id, reason = recommend_route(routes_out)

    heatmap_features: list[dict[str, Any]] = []
    for point in heatmap_points:
        if not isinstance(point, dict):
            raise AnalyzeError("Invalid heatmap point in plan.", field="plan")
        series = weather_series[series_idx]
        series_idx += 1
        if not isinstance(series, dict):
            raise AnalyzeError("Invalid weather series entry.", field="weather_series")
        hourly = openmeteo.build_heatmap_series(series, hours=49)
        heatmap_features.append(
            {
                "lon": point.get("lon"),
                "lat": point.get("lat"),
                "miles_from_origin": point.get("miles_from_origin"),
                "hourly": hourly,
            }
        )

    return {
        "origin": plan.get("origin"),
        "destination": plan.get("destination"),
        "departure_at": plan.get("departure_at"),
        "load_weight_lb": load_weight_lb,
        "sample_interval_miles": plan.get("sample_interval_miles"),
        "routes": routes_out,
        "recommended_route_id": recommended_id,
        "recommendation_reason": reason,
        "heatmap": {
            "hours": 48,
            "points": heatmap_features,
        },
    }
