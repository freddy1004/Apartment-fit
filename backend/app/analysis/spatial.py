"""Pure-Python spatial predicates for polygon / layer criteria.

No shapely dependency: point-in-polygon uses the ray-casting algorithm, which is
exact for simple polygons and fast enough for grid-scale analysis. Coordinates
are GeoJSON order ``[lon, lat]`` throughout.
"""
from __future__ import annotations

from typing import Optional


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon for a single ring ([[lon,lat], ...])."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersect = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-15) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def point_in_polygon(lon: float, lat: float, rings: list[list[list[float]]]) -> bool:
    """Polygon with holes: first ring is outer, the rest are holes."""
    if not rings:
        return False
    if not point_in_ring(lon, lat, rings[0]):
        return False
    for hole in rings[1:]:
        if point_in_ring(lon, lat, hole):
            return False
    return True


def point_in_geometry(lon: float, lat: float, geometry: list) -> bool:
    """Accept either a single polygon (list of rings) or a MultiPolygon
    (list of polygons). We detect MultiPolygon by nesting depth."""
    if not geometry:
        return False
    # geometry[0][0] is a coordinate pair for a Polygon ring, or a ring for a
    # MultiPolygon. Distinguish by checking the innermost element type.
    first = geometry[0]
    if first and isinstance(first[0], (int, float)):
        # geometry is a single ring
        return point_in_ring(lon, lat, geometry)
    if first and isinstance(first[0][0], (int, float)):
        # geometry is a polygon (list of rings)
        return point_in_polygon(lon, lat, geometry)
    # geometry is a MultiPolygon (list of polygons)
    return any(point_in_polygon(lon, lat, poly) for poly in geometry)


def _feature_rings(feature: dict) -> list:
    geom = feature.get("geometry", {})
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    if gtype == "Polygon":
        return [coords]          # -> list with one polygon (list of rings)
    if gtype == "MultiPolygon":
        return coords            # -> list of polygons
    return []


def sample_layer_value(
    lon: float, lat: float, feature_collection: dict, value_property: str,
    default: Optional[float] = None,
) -> tuple[Optional[float], Optional[str]]:
    """Return (value, feature_name) for the first feature containing the point.

    Falls back to ``default`` (and name None) when no feature contains it.
    """
    for feat in feature_collection.get("features", []):
        for poly in _feature_rings(feat):
            if point_in_polygon(lon, lat, poly):
                props = feat.get("properties", {})
                val = props.get(value_property)
                if val is not None:
                    return float(val), props.get("name")
    return default, None


def point_in_any_feature(lon: float, lat: float, feature_collection: dict) -> Optional[str]:
    """Return the name of the first feature containing the point, else None."""
    for feat in feature_collection.get("features", []):
        for poly in _feature_rings(feat):
            if point_in_polygon(lon, lat, poly):
                return feat.get("properties", {}).get("name", "zone")
    return None
