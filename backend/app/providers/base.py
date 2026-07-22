"""Provider interfaces.

All external capabilities (geocoding, routing, points-of-interest, transit,
listing ingestion) are accessed through these interfaces so real services can be
swapped for open-data or mock implementations without touching the engine.

Every result carries provenance: ``source``, ``confidence`` (0..1), and whether
a straight-line fallback was used. The scoring engine records this so the map
can label data limitations.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Optional


@dataclass
class GeocodeResult:
    lat: float
    lon: float
    display_name: str
    confidence: float
    source: str


@dataclass
class RouteResult:
    duration_s: float
    distance_m: float
    mode: str
    is_fallback: bool  # True => straight-line estimate, not a real network route
    confidence: float
    source: str


@dataclass
class Poi:
    lat: float
    lon: float
    name: str
    category: str
    source: str
    tags: Optional[dict] = None


class GeocodingProvider(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    def geocode(self, address: str) -> Optional[GeocodeResult]:
        ...


class RoutingProvider(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    def route(
        self, o_lat: float, o_lon: float, d_lat: float, d_lon: float, mode: str,
    ) -> RouteResult:
        ...


class PoiProvider(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    def find(
        self, category: str, bbox: list[float], limit: int = 200,
    ) -> list[Poi]:
        ...
