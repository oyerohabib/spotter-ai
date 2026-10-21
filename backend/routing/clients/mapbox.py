"""Mapbox Geocoding and Directions clients."""

from __future__ import annotations

import logging
import math
from typing import Any
from urllib.parse import quote

import httpx
from django.conf import settings

GEOCODE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"
DIRECTIONS_URL = "https://api.mapbox.com/directions/v5/mapbox/driving/{coords}"

MAX_ROUTES = 3
_DEDUP_TOLERANCE = 0.02  # 2% distance/duration similarity
logger = logging.getLogger(__name__)


class MapboxError(Exception):
    pass


def _token() -> str:
    token = getattr(settings, "MAPBOX_ACCESS_TOKEN", "") or ""
    if not token:
        raise MapboxError(
            "MAPBOX_ACCESS_TOKEN is not configured. Add it to your .env file."
        )
    return token


def _geocode_features(query: str, *, limit: int = 1) -> list[dict[str, Any]]:
    """Return raw Mapbox geocoding features for a query."""
    q = query.strip()
    if not q:
        raise MapboxError("Origin/destination query cannot be empty.")

    url = GEOCODE_URL.format(query=quote(q))
    params = {
        "access_token": _token(),
        "limit": limit,
        "types": "place,locality,neighborhood,address,poi",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, params=params)
    if resp.status_code >= 400:
        raise MapboxError(f"Geocoding failed ({resp.status_code}): {resp.text[:200]}")

    data = resp.json()
    return list(data.get("features") or [])


def suggest_places(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """
    Return place suggestions for autocomplete.
    Empty list when nothing matches (not an error).
    """
    features = _geocode_features(query, limit=limit)
    results: list[dict[str, Any]] = []
    for feature in features:
        center = feature.get("center") or [None, None]
        lon, lat = center[0], center[1]
        if lon is None or lat is None:
            continue
        results.append(
            {
                "id": str(feature.get("id") or f"{lon},{lat}"),
                "name": feature.get("place_name") or query.strip(),
                "lon": float(lon),
                "lat": float(lat),
            }
        )
    return results


def geocode(query: str, *, limit: int = 1) -> dict[str, Any]:
    """Geocode a free-text place into lon/lat and place name."""
    q = query.strip()
    features = _geocode_features(q, limit=limit)
    if not features:
        raise MapboxError(f"No geocoding results for '{q}'.")

    feature = features[0]
    lon, lat = feature["center"]
    return {
        "query": q,
        "name": feature.get("place_name") or q,
        "lon": float(lon),
        "lat": float(lat),
    }


def _parse_route(route: dict[str, Any]) -> dict[str, Any]:
    geometry = route.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    return {
        "distance_meters": float(route.get("distance") or 0),
        "duration_seconds": float(route.get("duration") or 0),
        "coordinates": coordinates,
    }


def _routes_similar(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """True when distance and duration are within the dedupe tolerance."""
    for key in ("distance_meters", "duration_seconds"):
        av = float(a.get(key) or 0)
        bv = float(b.get(key) or 0)
        if av <= 0 and bv <= 0:
            continue
        base = max(av, bv, 1.0)
        if abs(av - bv) / base > _DEDUP_TOLERANCE:
            return False
    return True


def _merge_unique(
    collected: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    for candidate in candidates:
        if len(collected) >= MAX_ROUTES:
            break
        if any(_routes_similar(candidate, existing) for existing in collected):
            continue
        collected.append(candidate)
    return collected


def _fetch_directions(
    coords: str,
    *,
    alternatives: bool = True,
    exclude: str | None = None,
    raise_on_error: bool = True,
) -> list[dict[str, Any]]:
    """Call Mapbox Directions and return parsed route dicts (no ids)."""
    url = DIRECTIONS_URL.format(coords=coords)
    params: dict[str, str] = {
        "access_token": _token(),
        "alternatives": "true" if alternatives else "false",
        "geometries": "geojson",
        "overview": "full",
        "steps": "false",
    }
    if exclude:
        params["exclude"] = exclude

    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.get(url, params=params)
        if resp.status_code >= 400:
            msg = f"Directions failed ({resp.status_code}): {resp.text[:200]}"
            if raise_on_error:
                raise MapboxError(msg)
            logger.warning(msg)
            return []

        data = resp.json()
        if data.get("code") != "Ok":
            msg = f"Directions error: {data.get('code')} — {data.get('message')}"
            if raise_on_error:
                raise MapboxError(msg)
            logger.warning(msg)
            return []

        return [_parse_route(r) for r in (data.get("routes") or [])]
    except MapboxError:
        raise
    except Exception as exc:  # noqa: BLE001 — soft-fail fill-in calls
        if raise_on_error:
            raise MapboxError(f"Directions request failed: {exc}") from exc
        logger.warning("Directions request failed: %s", exc)
        return []


def _offset_midpoint(
    origin: tuple[float, float],
    destination: tuple[float, float],
    *,
    fraction: float = 0.35,
) -> tuple[float, float]:
    """Midpoint of OD corridor, offset perpendicular (~fraction degrees)."""
    o_lon, o_lat = origin
    d_lon, d_lat = destination
    mid_lon = (o_lon + d_lon) / 2.0
    mid_lat = (o_lat + d_lat) / 2.0
    dx = d_lon - o_lon
    dy = d_lat - o_lat
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return mid_lon + fraction, mid_lat
    # Unit perpendicular in lon/lat space
    px, py = -dy / length, dx / length
    return mid_lon + px * fraction, mid_lat + py * fraction


def get_route_alternatives(
    origin: tuple[float, float],
    destination: tuple[float, float],
    *,
    alternatives: bool = True,
) -> list[dict[str, Any]]:
    """
    Fetch driving routes with geometry. Aims for up to 3 distinct options.

    Starts with Mapbox alternatives, then fills gaps via exclude=motorway/toll
    and a via-waypoint offset when fewer than 3 unique routes are returned.
    origin/destination are (lon, lat).
    """
    o_lon, o_lat = origin
    d_lon, d_lat = destination
    base_coords = f"{o_lon},{o_lat};{d_lon},{d_lat}"

    primary = _fetch_directions(base_coords, alternatives=alternatives, raise_on_error=True)
    if not primary:
        raise MapboxError("No routes found between the given points.")

    collected = _merge_unique([], primary)

    if len(collected) < MAX_ROUTES:
        for exclude in ("motorway", "toll"):
            if len(collected) >= MAX_ROUTES:
                break
            extra = _fetch_directions(
                base_coords,
                alternatives=True,
                exclude=exclude,
                raise_on_error=False,
            )
            _merge_unique(collected, extra)

    if len(collected) < MAX_ROUTES:
        via_lon, via_lat = _offset_midpoint(origin, destination)
        via_coords = f"{o_lon},{o_lat};{via_lon},{via_lat};{d_lon},{d_lat}"
        via_routes = _fetch_directions(
            via_coords, alternatives=True, raise_on_error=False
        )
        _merge_unique(collected, via_routes)

    if len(collected) < MAX_ROUTES:
        # Opposite-side offset for a second distinct corridor
        via_lon, via_lat = _offset_midpoint(origin, destination, fraction=-0.35)
        via_coords = f"{o_lon},{o_lat};{via_lon},{via_lat};{d_lon},{d_lat}"
        via_routes = _fetch_directions(
            via_coords, alternatives=False, raise_on_error=False
        )
        _merge_unique(collected, via_routes)

    results: list[dict[str, Any]] = []
    for idx, route in enumerate(collected[:MAX_ROUTES]):
        results.append(
            {
                "id": f"route-{idx + 1}",
                "distance_meters": route["distance_meters"],
                "duration_seconds": route["duration_seconds"],
                "coordinates": route["coordinates"],
            }
        )
    return results
