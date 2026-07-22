"""Real self-hosted OpenStreetMap provider adapters.

These talk to standard open-source OSM services that ship in the Docker stack:

- OSRM         (routing)   -> /route/v1/{profile}/{coords}
- Nominatim    (geocoding) -> /search
- Overpass API (POIs)      -> /api/interpreter

Each adapter degrades gracefully: on any error it raises, and the registry
falls back to the bundled fixture providers (with a confidence downgrade), so
the app keeps working offline. OSRM commonly runs one profile per instance, so
routing base URLs are configurable per travel mode.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

from .base import (
    GeocodeResult,
    GeocodingProvider,
    Poi,
    PoiProvider,
    RouteResult,
    RoutingProvider,
)

_TIMEOUT = float(os.getenv("PROVIDER_TIMEOUT_S", "8"))

# Map our modes to OSRM profiles / per-mode base URLs.
_OSRM_PROFILE = {"walk": "foot", "bike": "bike", "drive": "driving", "transit": "driving"}


def _osrm_base(mode: str) -> str:
    # Allow one instance per profile, else a single shared instance.
    per_mode = os.getenv(f"OSRM_URL_{mode.upper()}")
    return per_mode or os.getenv("OSRM_URL", "http://osrm:5000")


class OsrmRoutingProvider(RoutingProvider):
    name = "osrm"

    def route(self, o_lat, o_lon, d_lat, d_lon, mode) -> RouteResult:
        profile = _OSRM_PROFILE.get(mode, "driving")
        base = _osrm_base(mode)
        url = (f"{base}/route/v1/{profile}/"
               f"{o_lon},{o_lat};{d_lon},{d_lat}")
        r = httpx.get(url, params={"overview": "false"}, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            raise RuntimeError(f"OSRM no route: {data.get('code')}")
        route = data["routes"][0]
        return RouteResult(
            duration_s=float(route["duration"]),
            distance_m=float(route["distance"]),
            mode=mode,
            is_fallback=False,
            confidence=0.95,
            source=self.name,
        )

    def healthy(self) -> bool:
        try:
            base = _osrm_base("drive")
            httpx.get(f"{base}/route/v1/driving/-122.33,47.60;-122.34,47.61",
                      params={"overview": "false"}, timeout=3).raise_for_status()
            return True
        except Exception:
            return False


class NominatimGeocodingProvider(GeocodingProvider):
    name = "nominatim"

    def geocode(self, address: str) -> Optional[GeocodeResult]:
        base = os.getenv("NOMINATIM_URL", "http://nominatim:8080")
        r = httpx.get(
            f"{base}/search",
            params={"q": address, "format": "jsonv2", "limit": 1},
            headers={"User-Agent": "apartment-fit/0.1"},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        results = r.json()
        if not results:
            return None
        top = results[0]
        importance = float(top.get("importance", 0.5) or 0.5)
        return GeocodeResult(
            lat=float(top["lat"]),
            lon=float(top["lon"]),
            display_name=top.get("display_name", address),
            confidence=min(0.99, 0.6 + importance * 0.4),
            source=self.name,
        )


# OSM tag filters per amenity category for Overpass.
_OVERPASS_FILTER = {
    "supermarket": '["shop"="supermarket"]',
    "park": '["leisure"="park"]',
    "transit_stop": '["public_transport"="station"]',
    "freeway_ramp": '["highway"="motorway_junction"]',
}


class OverpassPoiProvider(PoiProvider):
    name = "overpass"

    def find(self, category: str, bbox: list[float], limit: int = 200) -> list[Poi]:
        tag = _OVERPASS_FILTER.get(category)
        if not tag:
            return []
        base = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
        min_lon, min_lat, max_lon, max_lat = bbox
        bbox_str = f"{min_lat},{min_lon},{max_lat},{max_lon}"
        query = (f"[out:json][timeout:25];"
                 f"(node{tag}({bbox_str});way{tag}({bbox_str}););out center {limit};")
        r = httpx.post(base, data={"data": query}, timeout=_TIMEOUT * 3)
        r.raise_for_status()
        out: list[Poi] = []
        for el in r.json().get("elements", []):
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue
            name = (el.get("tags") or {}).get("name", category)
            out.append(Poi(lat=lat, lon=lon, name=name, category=category,
                           source=self.name, tags=el.get("tags")))
        return out
