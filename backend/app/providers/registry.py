"""Provider registry with automatic real-vs-fixture selection.

``PROVIDER_MODE``:
  - ``auto`` (default): use each live OSM service that is reachable, falling back
    to the bundled offline provider otherwise. In a plain ``docker compose up``
    that means **live POIs from Overpass** (public API) while routing/geocoding
    use offline estimates (OSRM/Nominatim aren't running unless you start the
    ``osm`` profile). Health is probed once per process and cached.
  - ``osm``: force the live services (assume you run OSRM/Nominatim/Overpass);
    still falls back per-call on error.
  - ``fixture``: always use the bundled offline providers (fully deterministic,
    used by the test suite).

POI lookups are cached per (category, bbox) so a whole city analysis makes one
Overpass request per amenity type, not one per grid cell. Every result keeps its
provenance so the UI can show live-vs-estimate.
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
    TerrainResult,
)
from .fixture import (
    FixtureGeocodingProvider,
    FixturePoiProvider,
    FixtureRoutingProvider,
    FixtureTerrainProvider,
)


def _mode() -> str:
    return os.getenv("PROVIDER_MODE", "auto").lower()


class Providers:
    """Facade that engine code depends on. Never raises for missing services."""

    def __init__(self, mode: Optional[str] = None):
        self.mode = mode or _mode()
        self.fixture_routing = FixtureRoutingProvider()
        self.fixture_poi = FixturePoiProvider()
        self.fixture_geo = FixtureGeocodingProvider()
        self.fixture_terrain = FixtureTerrainProvider()
        # Caches (spec: cache routing/geocoding; POIs cached to avoid per-cell hits).
        self._route_cache: dict[tuple, RouteResult] = {}
        self._geo_cache: dict[str, Optional[GeocodeResult]] = {}
        self._poi_cache: dict[tuple, list[Poi]] = {}
        self._osm_routing: Optional[RoutingProvider] = None
        self._osm_geo: Optional[GeocodingProvider] = None
        self._osm_poi: Optional[PoiProvider] = None
        if self.mode in ("osm", "auto"):
            # Imported lazily so httpx is only required when a live mode is on.
            from .osm import (
                NominatimGeocodingProvider,
                OsrmRoutingProvider,
                OverpassPoiProvider,
            )
            self._osm_routing = OsrmRoutingProvider()
            self._osm_geo = NominatimGeocodingProvider()
            self._osm_poi = OverpassPoiProvider()

    # -- health probes (run once, cached) ------------------------------------
    def _healthy(self, provider) -> bool:
        if not provider:
            return False
        try:
            return bool(provider.healthy())  # type: ignore[attr-defined]
        except Exception:
            return False

    @functools.cached_property
    def _routing_ok(self) -> bool:
        return self.mode == "osm" or self._healthy(self._osm_routing)

    @functools.cached_property
    def _geo_ok(self) -> bool:
        return self.mode == "osm" or self._healthy(self._osm_geo)

    @functools.cached_property
    def _poi_ok(self) -> bool:
        return self.mode == "osm" or self._healthy(self._osm_poi)

    # -- routing -------------------------------------------------------------
    def route(self, o_lat, o_lon, d_lat, d_lon, mode) -> RouteResult:
        key = (round(o_lat, 4), round(o_lon, 4), round(d_lat, 4), round(d_lon, 4), mode)
        cached = self._route_cache.get(key)
        if cached is not None:
            return cached
        result: Optional[RouteResult] = None
        if self._osm_routing and self._routing_ok:
            try:
                result = self._osm_routing.route(o_lat, o_lon, d_lat, d_lon, mode)
            except Exception:
                result = None
        if result is None:
            result = self.fixture_routing.route(o_lat, o_lon, d_lat, d_lon, mode)
        self._route_cache[key] = result
        return result

    # -- geocoding -----------------------------------------------------------
    def geocode(self, address: str) -> Optional[GeocodeResult]:
        if address in self._geo_cache:
            return self._geo_cache[address]
        result: Optional[GeocodeResult] = None
        if self._osm_geo and self._geo_ok:
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
        key = (category, tuple(round(x, 3) for x in bbox), limit)
        cached = self._poi_cache.get(key)
        if cached is not None:
            return cached
        result: Optional[list[Poi]] = None
        if self._osm_poi and self._poi_ok:
            try:
                res = self._osm_poi.find(category, bbox, limit)
                if res:
                    result = res
            except Exception:
                result = None
        if result is None:
            result = self.fixture_poi.find(category, bbox, limit)
        self._poi_cache[key] = result
        return result

    def status(self) -> dict:
        """Which source each capability is actually using (for /health & UI)."""
        return {
            "mode": self.mode,
            "routing": "osrm" if (self._osm_routing and self._routing_ok) else "fixture",
            "geocoding": "nominatim" if (self._osm_geo and self._geo_ok) else "fixture",
            "pois": "overpass" if (self._osm_poi and self._poi_ok) else "fixture",
        }


@functools.lru_cache(maxsize=4)
def get_providers(mode: Optional[str] = None) -> Providers:
    return Providers(mode)
