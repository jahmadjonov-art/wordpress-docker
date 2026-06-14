"""Geocoding + driving distance, with a no-key fallback.

Priority for distance:
  1. OpenRouteService (driving-hgv truck profile) if ORS_API_KEY is set
  2. Self-hosted OSRM if OSRM_URL is set
  3. Haversine great-circle * 1.2 road factor (always available)

Geocoding uses ORS/Pelias when a key is present, otherwise the free OSM
Nominatim service. Coordinates are (lat, lng).
"""
import math
import httpx

from .. import config

ROAD_FACTOR = 1.2  # straight-line miles -> typical road miles
_TIMEOUT = 15.0
_UA = {"User-Agent": "freight-dispatcher/1.0 (load scorer)"}


def haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    r = 3958.7613  # earth radius, miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def geocode(city: str, state: str) -> tuple[float, float] | None:
    """Return (lat, lng) for a US city/state, or None."""
    query = f"{city}, {state}, USA"
    try:
        if config.ORS_API_KEY:
            r = httpx.get(
                "https://api.openrouteservice.org/geocode/search",
                params={"api_key": config.ORS_API_KEY, "text": query,
                        "boundary.country": "US", "size": 1},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            feats = r.json().get("features") or []
            if feats:
                lng, lat = feats[0]["geometry"]["coordinates"]
                return (lat, lng)
        # Fallback: free OSM Nominatim
        r = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"city": city, "state": state, "country": "USA",
                    "format": "json", "limit": 1},
            headers=_UA,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        rows = r.json()
        if rows:
            return (float(rows[0]["lat"]), float(rows[0]["lon"]))
    except (httpx.HTTPError, KeyError, ValueError, IndexError):
        return None
    return None


def _ors_miles(origin: tuple[float, float], dest: tuple[float, float]) -> float | None:
    try:
        r = httpx.post(
            "https://api.openrouteservice.org/v2/directions/driving-hgv",
            headers={"Authorization": config.ORS_API_KEY},
            json={"coordinates": [[origin[1], origin[0]], [dest[1], dest[0]]]},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        meters = r.json()["routes"][0]["summary"]["distance"]
        return meters / 1609.344
    except (httpx.HTTPError, KeyError, ValueError, IndexError):
        return None


def _osrm_miles(origin: tuple[float, float], dest: tuple[float, float]) -> float | None:
    try:
        url = (f"{config.OSRM_URL}/route/v1/driving/"
               f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}")
        r = httpx.get(url, params={"overview": "false"}, timeout=_TIMEOUT)
        r.raise_for_status()
        meters = r.json()["routes"][0]["distance"]
        return meters / 1609.344
    except (httpx.HTTPError, KeyError, ValueError, IndexError):
        return None


def road_miles(origin: tuple[float, float], dest: tuple[float, float]) -> tuple[float, str]:
    """Return (miles, source). Source is one of ors|osrm|haversine."""
    if config.ORS_API_KEY:
        m = _ors_miles(origin, dest)
        if m is not None:
            return (m, "ors")
    if config.OSRM_URL:
        m = _osrm_miles(origin, dest)
        if m is not None:
            return (m, "osrm")
    return (haversine_miles(origin, dest) * ROAD_FACTOR, "haversine")
