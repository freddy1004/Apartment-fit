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
