"""Geospatial helpers: distances, grid generation, and zone grouping.

Geometry math is done in Python (haversine + optional shapely) so the core
engine is testable without a live PostGIS database. PostGIS is still used for
storage/serving in the Docker stack, but correctness does not depend on it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional

EARTH_RADIUS_M = 6_371_000.0
MILES_PER_METER = 1 / 1609.344


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def meters_to_miles(m: float) -> float:
    return m * MILES_PER_METER


@dataclass
class Cell:
    id: str
    row: int
    col: int
    center_lat: float
    center_lon: float
    # polygon ring as [[lon,lat], ...] (GeoJSON order), closed.
    ring: list[list[float]] = field(default_factory=list)

    def as_feature(self, properties: Optional[dict] = None) -> dict:
        return {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [self.ring]},
            "properties": {"cell_id": self.id, **(properties or {})},
        }


def _meters_per_degree(lat: float) -> tuple[float, float]:
    """Approx meters per degree of latitude and longitude at ``lat``."""
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat))
    return m_per_deg_lat, max(m_per_deg_lon, 1e-6)


def generate_grid(bbox: list[float], cell_size_m: float) -> list[Cell]:
    """Generate square-ish grid cells covering ``bbox`` = [minlon,minlat,maxlon,maxlat].

    Cells are approximately ``cell_size_m`` on a side, sized at the bbox's
    center latitude. This is a small-grid-cell decomposition (block level for
    small cell sizes) rather than a neighborhood partition.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    center_lat = (min_lat + max_lat) / 2
    m_lat, m_lon = _meters_per_degree(center_lat)
    dlat = cell_size_m / m_lat
    dlon = cell_size_m / m_lon

    cells: list[Cell] = []
    n_rows = max(1, int(math.ceil((max_lat - min_lat) / dlat)))
    n_cols = max(1, int(math.ceil((max_lon - min_lon) / dlon)))
    for r in range(n_rows):
        for c in range(n_cols):
            lat0 = min_lat + r * dlat
            lat1 = min(max_lat, lat0 + dlat)
            lon0 = min_lon + c * dlon
            lon1 = min(max_lon, lon0 + dlon)
            ring = [
                [lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0],
            ]
            cells.append(Cell(
                id=f"r{r}c{c}", row=r, col=c,
                center_lat=(lat0 + lat1) / 2, center_lon=(lon0 + lon1) / 2,
                ring=ring,
            ))
    return cells


def nearest(
    lat: float, lon: float, points: Iterable[tuple[float, float]],
) -> Optional[tuple[float, float, float]]:
    """Return (lat, lon, distance_m) of the nearest point, or None if empty."""
    best = None
    for plat, plon in points:
        d = haversine_m(lat, lon, plat, plon)
        if best is None or d < best[2]:
            best = (plat, plon, d)
    return best


def group_contiguous(
    qualifying_cells: list[Cell],
) -> list[list[Cell]]:
    """Group qualifying cells into contiguous clusters (4-connectivity on the grid).

    Returns a list of clusters, each a list of cells. Used to form practical
    "apartment-search zones" from individual qualifying cells.
    """
    by_rc = {(c.row, c.col): c for c in qualifying_cells}
    seen: set[tuple[int, int]] = set()
    clusters: list[list[Cell]] = []
    for key, cell in by_rc.items():
        if key in seen:
            continue
        stack = [key]
        cluster: list[Cell] = []
        seen.add(key)
        while stack:
            r, c = stack.pop()
            cluster.append(by_rc[(r, c)])
            for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if (nr, nc) in by_rc and (nr, nc) not in seen:
                    seen.add((nr, nc))
                    stack.append((nr, nc))
        clusters.append(cluster)
    clusters.sort(key=len, reverse=True)
    return clusters


def cluster_bounds(cluster: list[Cell]) -> dict:
    """Approximate street-boundary description of a cluster: bbox + centroid."""
    lats = [c.center_lat for c in cluster]
    lons = [c.center_lon for c in cluster]
    ring_lats = [pt[1] for c in cluster for pt in c.ring]
    ring_lons = [pt[0] for c in cluster for pt in c.ring]
    return {
        "cell_count": len(cluster),
        "min_lat": min(ring_lats), "max_lat": max(ring_lats),
        "min_lon": min(ring_lons), "max_lon": max(ring_lons),
        "centroid_lat": sum(lats) / len(lats),
        "centroid_lon": sum(lons) / len(lons),
    }
