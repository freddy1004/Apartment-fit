"""Travel-time / isochrone precompute.

Warms the provider route cache for every grid cell × routed destination so the
expensive routing work happens once. Subsequent analyses -- including those that
only change thresholds or weights -- reuse the cached routes, making re-runs
effectively incremental. With real OSRM this converts thousands of on-demand HTTP
calls into a single batched warm-up.
"""
from __future__ import annotations

from ..criteria.schema import Method, Mode, Profile
from ..providers.registry import Providers, get_providers
from .engine import _default_bbox
from .geo import generate_grid, haversine_m

DEFAULT_BANDS = [10, 20, 30, 45]


def warm_routes(profile: Profile, providers: Providers | None = None) -> dict:
    """Precompute routed measurements across the grid. Returns warm-up stats."""
    providers = providers or get_providers()
    bbox = profile.bbox or _default_bbox(profile)
    cells = generate_grid(bbox, profile.cell_size_m)

    routed = [c for c in profile.area_criteria() if c.method in (Method.ROUTE, Method.POI_DISTANCE)]
    calls = 0
    for c in routed:
        mode = c.mode.value if c.mode != Mode.NONE else "walk"
        for cell in cells:
            if c.destination and c.destination.lat is not None:
                dlat, dlon = c.destination.lat, c.destination.lon
            elif c.destination and c.destination.amenity_type:
                pois = providers.find_pois(c.destination.amenity_type, bbox)
                if not pois:
                    continue
                nearest = min(pois, key=lambda p: haversine_m(
                    cell.center_lat, cell.center_lon, p.lat, p.lon))
                dlat, dlon = nearest.lat, nearest.lon
            else:
                continue
            providers.route(cell.center_lat, cell.center_lon, dlat, dlon, mode)
            calls += 1

    return {
        "cells": len(cells),
        "routed_criteria": len(routed),
        "route_calls": calls,
        "cached_routes": len(providers._route_cache),
    }


def _resolve_destination(c, cell, providers, bbox):
    if c.destination and c.destination.lat is not None:
        return c.destination.lat, c.destination.lon, c.destination.label
    if c.destination and c.destination.amenity_type:
        pois = providers.find_pois(c.destination.amenity_type, bbox)
        if not pois:
            return None
        p = min(pois, key=lambda p: haversine_m(cell.center_lat, cell.center_lon, p.lat, p.lon))
        return p.lat, p.lon, p.name
    return None


def build_isochrones(profile: Profile, providers: Providers | None = None,
                     bands: list[int] | None = None) -> dict:
    """Per-destination travel-time surfaces as banded GeoJSON.

    For every routed area criterion, computes each cell's travel time to its
    destination and buckets cells into minute bands (an isochrone map). Reuses
    the cached routes warmed by :func:`warm_routes`.
    """
    providers = providers or get_providers()
    bands = sorted(bands or DEFAULT_BANDS)
    bbox = profile.bbox or _default_bbox(profile)
    cells = generate_grid(bbox, profile.cell_size_m)

    surfaces = []
    for c in profile.area_criteria():
        if c.method not in (Method.ROUTE, Method.POI_DISTANCE):
            continue
        mode = c.mode.value if c.mode != Mode.NONE else "walk"
        features = []
        for cell in cells:
            dest = _resolve_destination(c, cell, providers, bbox)
            if not dest:
                continue
            route = providers.route(cell.center_lat, cell.center_lon, dest[0], dest[1], mode)
            minutes = route.duration_s / 60.0
            band = next((b for b in bands if minutes <= b), None)
            if band is None:
                continue  # beyond the largest band
            features.append(cell.as_feature({
                "minutes": round(minutes, 1), "band": band,
                "is_fallback": route.is_fallback,
            }))
        surfaces.append({
            "criterion_id": c.id, "label": c.label, "mode": mode, "bands": bands,
            "geojson": {"type": "FeatureCollection", "features": features},
        })
    return {"profile_id": profile.id, "bands": bands, "surfaces": surfaces}
