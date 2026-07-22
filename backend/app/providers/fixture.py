"""Offline, deterministic providers backed by bundled open-data fixtures.

These make the whole product run and its tests pass with no network access,
no API keys, and no multi-GB OSM extract. Travel times are network-approximated
straight-line estimates (haversine * detour factor / mode speed) and are always
flagged ``is_fallback=True`` so the UI can label them.
"""
from __future__ import annotations

import functools
import json
import os
import re
from typing import Optional

import math

from ..analysis.geo import haversine_m
from .base import (
    GeocodeResult,
    GeocodingProvider,
    Poi,
    PoiProvider,
    RouteResult,
    RoutingProvider,
    TerrainProvider,
    TerrainResult,
)

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seattle.json")

# Effective speeds (m/s) including typical urban friction, and a detour factor
# that approximates real road/path networks from geodesic distance.
_MODE_SPEED_MPS = {"walk": 1.35, "bike": 4.8, "drive": 9.5, "transit": 5.0}
_DETOUR = {"walk": 1.25, "bike": 1.25, "drive": 1.35, "transit": 1.4}
_FIXED_OVERHEAD_S = {"walk": 0, "bike": 30, "drive": 60, "transit": 240}


@functools.lru_cache(maxsize=1)
def load_fixture() -> dict:
    with open(os.path.abspath(_DATA_PATH), "r", encoding="utf-8") as fh:
        return json.load(fh)


class FixtureRoutingProvider(RoutingProvider):
    name = "fixture-straightline"

    def route(self, o_lat, o_lon, d_lat, d_lon, mode) -> RouteResult:
        speed = _MODE_SPEED_MPS.get(mode, 1.35)
        detour = _DETOUR.get(mode, 1.3)
        straight = haversine_m(o_lat, o_lon, d_lat, d_lon)
        network_m = straight * detour
        duration = network_m / speed + _FIXED_OVERHEAD_S.get(mode, 0)
        return RouteResult(
            duration_s=duration,
            distance_m=network_m,
            mode=mode,
            is_fallback=True,
            confidence=0.6,
            source=self.name,
        )


class FixturePoiProvider(PoiProvider):
    name = "fixture-osm"

    def find(self, category: str, bbox: list[float], limit: int = 200) -> list[Poi]:
        data = load_fixture()
        items = data.get(category, [])
        min_lon, min_lat, max_lon, max_lat = bbox
        # Pad the box: the nearest amenity to a cell near the edge may sit just
        # outside the analysis bbox (e.g. a grocery one block south of it), so it
        # must still be a candidate for "nearest".
        pad = 0.05  # ~5.5 km
        out: list[Poi] = []
        for it in items:
            lat, lon = it["lat"], it["lon"]
            if (min_lat - pad) <= lat <= (max_lat + pad) and (min_lon - pad) <= lon <= (max_lon + pad):
                out.append(Poi(lat=lat, lon=lon, name=it["name"],
                               category=category, source=self.name))
        if not out:  # fall back to the full set rather than returning nothing
            for it in items:
                out.append(Poi(lat=it["lat"], lon=it["lon"], name=it["name"],
                               category=category, source=self.name))
        return out[:limit]


class FixtureTerrainProvider(TerrainProvider):
    """Terrain from real Seattle elevation reference points.

    Elevation is inverse-distance interpolated over real Seattle hill/lowland
    elevations (``data/seattle_real.ELEVATION_POINTS``); slope is the gradient
    magnitude over ~100 m, in percent. Real deployments can swap in a live
    elevation raster (SRTM/NED) via ``open_data.py``; this offline default is
    grounded in actual topography rather than a synthetic surface.
    """
    name = "seattle-idw-dem"

    def _elevation(self, lat: float, lon: float) -> float:
        from ..data.seattle_real import elevation_at
        return elevation_at(lat, lon)

    def sample(self, lat: float, lon: float) -> TerrainResult:
        d = 0.0009  # ~100m
        e = self._elevation(lat, lon)
        # central-difference gradient over ~100m in each direction
        de_lat = (self._elevation(lat + d, lon) - self._elevation(lat - d, lon)) / 2
        de_lon = (self._elevation(lat, lon + d) - self._elevation(lat, lon - d)) / 2
        run_m = 100.0
        rise = math.hypot(de_lat, de_lon)
        slope_pct = min(60.0, rise / run_m * 100.0)
        return TerrainResult(slope_pct=slope_pct, elevation_m=e, confidence=0.6,
                             source=self.name, is_fallback=False)


_LATLON_RE = re.compile(r"(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)")


class FixtureGeocodingProvider(GeocodingProvider):
    """Best-effort offline geocoder.

    Resolution order: explicit ``lat,lon`` in the string -> neighborhood name
    match -> known POI name match -> city center (low confidence). Real
    deployments use :class:`NominatimGeocodingProvider`.
    """
    name = "fixture-gazetteer"

    def geocode(self, address: str) -> Optional[GeocodeResult]:
        if not address:
            return None
        m = _LATLON_RE.search(address)
        if m:
            return GeocodeResult(float(m.group(1)), float(m.group(2)),
                                 address, 0.99, self.name)
        data = load_fixture()
        low = address.lower()
        for hood in data.get("neighborhoods", []):
            if hood["name"].lower() in low:
                return GeocodeResult(hood["lat"], hood["lon"], hood["name"],
                                     0.7, self.name)
        for cat in ("supermarket", "park", "transit_stop", "freeway_ramp"):
            for it in data.get(cat, []):
                if it["name"].lower() in low:
                    return GeocodeResult(it["lat"], it["lon"], it["name"],
                                         0.65, self.name)
        ref = data["downtown_reference"]
        return GeocodeResult(ref["lat"], ref["lon"],
                             f"{data['city']} (approx city center)", 0.25, self.name)
