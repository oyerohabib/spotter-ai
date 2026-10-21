"""Mapbox Geocoding and Directions clients."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from django.conf import settings

GEOCODE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"
DIRECTIONS_URL = "https://api.mapbox.com/directions/v5/mapbox/driving/{coords}"


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


def get_route_alternatives(
    origin: tuple[float, float],
    destination: tuple[float, float],
    *,
    alternatives: bool = True,
) -> list[dict[str, Any]]:
    """
    Fetch driving routes with geometry. Returns up to 3 alternatives.
    origin/destination are (lon, lat).
    """
    o_lon, o_lat = origin
    d_lon, d_lat = destination
    coords = f"{o_lon},{o_lat};{d_lon},{d_lat}"
    url = DIRECTIONS_URL.format(coords=coords)
    params = {
        "access_token": _token(),
        "alternatives": "true" if alternatives else "false",
        "geometries": "geojson",
        "overview": "full",
        "steps": "false",
    }
    with httpx.Client(timeout=45.0) as client:
        resp = client.get(url, params=params)
    if resp.status_code >= 400:
        raise MapboxError(f"Directions failed ({resp.status_code}): {resp.text[:200]}")

    data = resp.json()
    if data.get("code") != "Ok":
        raise MapboxError(
            f"Directions error: {data.get('code')} — {data.get('message')}"
        )

    routes = data.get("routes") or []
    if not routes:
        raise MapboxError("No routes found between the given points.")

    results: list[dict[str, Any]] = []
    for idx, route in enumerate(routes[:3]):
        geometry = route.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        results.append(
            {
                "id": f"route-{idx + 1}",
                "distance_meters": float(route.get("distance") or 0),
                "duration_seconds": float(route.get("duration") or 0),
                "coordinates": coordinates,
            }
        )
    return results
