"""Polyline densification and checkpoint sampling along a route."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Sequence

EARTH_RADIUS_MILES = 3958.7613
METERS_PER_MILE = 1609.344


def haversine_miles(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def interpolate_along_line(
    coordinates: Sequence[Sequence[float]],
    target_miles: float,
) -> tuple[float, float, float] | None:
    """
    Return (lon, lat, actual_miles) at target distance along the polyline.
    coordinates are [lon, lat] pairs.
    """
    if not coordinates or target_miles < 0:
        return None

    if target_miles == 0:
        lon, lat = coordinates[0]
        return float(lon), float(lat), 0.0

    traveled = 0.0
    for i in range(1, len(coordinates)):
        lon1, lat1 = coordinates[i - 1]
        lon2, lat2 = coordinates[i]
        seg = haversine_miles(lon1, lat1, lon2, lat2)
        if seg == 0:
            continue
        if traveled + seg >= target_miles:
            t = (target_miles - traveled) / seg
            return _lerp(lon1, lon2, t), _lerp(lat1, lat2, t), target_miles
        traveled += seg

    lon, lat = coordinates[-1]
    return float(lon), float(lat), traveled


def sample_checkpoints(
    coordinates: Sequence[Sequence[float]],
    *,
    interval_miles: float,
    total_duration_seconds: float,
    departure_at: datetime,
    total_distance_miles: float | None = None,
) -> list[dict[str, Any]]:
    """
    Sample checkpoints every `interval_miles` along the route, including start and end.

    ETA at each checkpoint assumes constant average speed over the full route duration.
    """
    if interval_miles <= 0:
        raise ValueError("interval_miles must be positive")
    if len(coordinates) < 2:
        raise ValueError("coordinates require at least two points")

    if total_distance_miles is None:
        total_distance_miles = 0.0
        for i in range(1, len(coordinates)):
            lon1, lat1 = coordinates[i - 1]
            lon2, lat2 = coordinates[i]
            total_distance_miles += haversine_miles(lon1, lat1, lon2, lat2)

    total_distance_miles = max(total_distance_miles, 0.0)
    duration = max(total_duration_seconds, 0.0)

    targets: list[float] = [0.0]
    mile = float(interval_miles)
    while mile < total_distance_miles:
        targets.append(mile)
        mile += interval_miles
    if total_distance_miles > 0 and (
        not targets or abs(targets[-1] - total_distance_miles) > 1e-6
    ):
        targets.append(total_distance_miles)

    checkpoints: list[dict[str, Any]] = []
    for idx, target in enumerate(targets):
        point = interpolate_along_line(coordinates, target)
        if point is None:
            continue
        lon, lat, _ = point
        fraction = 0.0 if total_distance_miles == 0 else target / total_distance_miles
        eta = departure_at + timedelta(seconds=duration * fraction)
        checkpoints.append(
            {
                "index": idx,
                "lon": lon,
                "lat": lat,
                "miles_from_origin": round(target, 2),
                "eta": eta.isoformat(),
            }
        )
    return checkpoints


def segment_miles_between(
    prev_miles: float,
    next_miles: float,
) -> float:
    return max(next_miles - prev_miles, 0.0)
