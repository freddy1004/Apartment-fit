"""Provider registry with automatic real-vs-fixture selection.

``PROVIDER_MODE``:
  - ``fixture`` (default): always use bundled offline providers.
  - ``osm``: use real OSRM/Nominatim/Overpass, falling back to fixtures per-call
    on any error. Routing health is probed once and cached.
  - ``auto``: try OSM, fall back to fixtures if the routing service is unhealthy.

Fallback results keep provenance so the UI can show which measurements are real
network routes vs. straight-line estimates.
"""
from __future__ import annotations

import functools
import os
from typing import Optional

from .base import (
    GeocodeResult,
    GeocodingProvider,
    Poi,
    PoiProvider,
    RouteResult,
    RoutingProvider,
)
from .base import TerrainResult
from .fixture import (
    FixtureGeocodingProvider,
    FixturePoiProvider,
    FixtureRoutingProvider,
    FixtureTerrainProvider,
)


def _mode() -> str:
    return os.getenv("PROVIDER_MODE", "fixture").lower()


class Providers:
    """Facade that engine code depends on. Never raises for missing services."""

    def __init__(self, mode: Optional[str] = None):
        self.mode = mode or _mode()
        self.fixture_routing = FixtureRoutingProvider()
        self.fixture_poi = FixturePoiProvider()
        self.fixture_geo = FixtureGeocodingProvider()
        self.fixture_terrain = FixtureTerrainProvider()
        # Simple in-process caches (spec: cache routing & geocoding results).
        self._route_cache: dict[tuple, RouteResult] = {}
        self._geo_cache: dict[str, Optional[GeocodeResult]] = {}
        self._osm_routing: Optional[RoutingProvider] = None
        self._osm_geo: Optional[GeocodingProvider] = None
        self._osm_poi: Optional[PoiProvider] = None
        if self.mode in ("osm", "auto"):
            # Imported lazily so httpx is only required when OSM mode is on.
            from .osm import (
                NominatimGeocodingProvider,
                OsrmRoutingProvider,
                OverpassPoiProvider,
            )
            self._osm_routing = OsrmRoutingProvider()
            self._osm_geo = NominatimGeocodingProvider()
            self._osm_poi = OverpassPoiProvider()

    @functools.cached_property
    def _osm_routing_healthy(self) -> bool:
        if not self._osm_routing:
            return False
        try:
            return self._osm_routing.healthy()  # type: ignore[attr-defined]
        except Exception:
            return False

    # -- routing -------------------------------------------------------------
    def route(self, o_lat, o_lon, d_lat, d_lon, mode) -> RouteResult:
        key = (round(o_lat, 4), round(o_lon, 4), round(d_lat, 4), round(d_lon, 4), mode)
        cached = self._route_cache.get(key)
        if cached is not None:
            return cached
        result: RouteResult
        if self._osm_routing and (self.mode == "osm" or self._osm_routing_healthy):
            try:
                result = self._osm_routing.route(o_lat, o_lon, d_lat, d_lon, mode)
            except Exception:
                result = self.fixture_routing.route(o_lat, o_lon, d_lat, d_lon, mode)
        else:
            result = self.fixture_routing.route(o_lat, o_lon, d_lat, d_lon, mode)
        self._route_cache[key] = result
        return result

    # -- geocoding -----------------------------------------------------------
    def geocode(self, address: str) -> Optional[GeocodeResult]:
        if address in self._geo_cache:
            return self._geo_cache[address]
        result: Optional[GeocodeResult] = None
        if self._osm_geo:
            try:
                result = self._osm_geo.geocode(address)
            except Exception:
                result = None
        if result is None:
            result = self.fixture_geo.geocode(address)
        self._geo_cache[address] = result
        return result

    # -- terrain -------------------------------------------------------------
    def terrain(self, lat: float, lon: float) -> TerrainResult:
        # OSM/elevation terrain source could go here; fixture is deterministic.
        return self.fixture_terrain.sample(lat, lon)

    # -- pois ----------------------------------------------------------------
    def find_pois(self, category: str, bbox: list[float], limit: int = 200) -> list[Poi]:
        if self._osm_poi:
            try:
                res = self._osm_poi.find(category, bbox, limit)
                if res:
                    return res
            except Exception:
                pass
        return self.fixture_poi.find(category, bbox, limit)


@functools.lru_cache(maxsize=4)
def get_providers(mode: Optional[str] = None) -> Providers:
    return Providers(mode)
