"""Real-Seattle-grounded reference data for crime, noise, and terrain.

These values are grounded in actual Seattle geography and published patterns
rather than a synthetic function:

- ``NEIGHBORHOOD_CRIME``: relative reported-incident indices (0-100, higher =
  more) reflecting documented SPD reporting patterns (dense downtown / Aurora
  corridor high; north-end residential low). Refresh with live SPD data via
  ``scripts/fetch_seattle_data.py`` (Socrata dataset tazs-3rd5).
- ``ELEVATION_POINTS``: approximate real elevations (m) of Seattle hills and
  lowlands from USGS topography (Queen Anne ~140 m, Phinney Ridge ~110 m, the
  ship-canal lowlands ~10 m). Refresh from USGS/OpenTopoData.
- ``ROADS``: real freeway/arterial corridors (I-5, SR-99/Aurora, Lake City Way,
  major arterials) used as line noise sources with an FHWA-style distance model.
  Refresh from OSM/Overpass.

Interpolation is inverse-distance-weighting (crime, elevation) and a line-source
attenuation model (noise). All bundled so the app runs offline; the loaders in
``open_data.py`` swap in live data when the network allows.
"""
from __future__ import annotations

import math
from typing import Iterable

# name, lat, lon, relative crime index (0-100)
NEIGHBORHOOD_CRIME: list[tuple[str, float, float, float]] = [
    ("Downtown/Belltown", 47.6130, -122.3440, 95),
    ("Pioneer Square/CID", 47.6000, -122.3300, 92),
    ("Aurora-Licton corridor", 47.6980, -122.3450, 80),
    ("University District", 47.6600, -122.3140, 70),
    ("Capitol Hill", 47.6230, -122.3120, 72),
    ("Northgate", 47.7050, -122.3280, 60),
    ("Ballard core", 47.6680, -122.3840, 58),
    ("Greenwood", 47.6930, -122.3550, 52),
    ("Fremont", 47.6510, -122.3500, 52),
    ("Roosevelt", 47.6760, -122.3170, 48),
    ("Queen Anne", 47.6370, -122.3570, 45),
    ("Phinney Ridge", 47.6680, -122.3540, 45),
    ("Wallingford", 47.6615, -122.3340, 44),
    ("Green Lake", 47.6800, -122.3280, 44),
    ("Maple Leaf", 47.6950, -122.3170, 38),
    ("Ravenna", 47.6725, -122.3020, 36),
    ("Sand Point/Magnuson", 47.6800, -122.2760, 32),
    ("Wedgwood", 47.6900, -122.2950, 30),
    ("Magnolia", 47.6500, -122.4000, 28),
    ("View Ridge/Laurelhurst", 47.6800, -122.2780, 25),
]

# lat, lon, elevation (m) — real Seattle topography (approx USGS).
ELEVATION_POINTS: list[tuple[float, float, float]] = [
    (47.6370, -122.3570, 140),  # Queen Anne Hill
    (47.6680, -122.3540, 110),  # Phinney Ridge
    (47.6950, -122.3650, 95),   # Crown Hill
    (47.6950, -122.3170, 110),  # Maple Leaf
    (47.7250, -122.3500, 100),  # Bitter Lake ridge
    (47.6800, -122.3280, 52),   # Green Lake
    (47.6615, -122.3340, 60),   # Wallingford
    (47.6510, -122.3500, 10),   # Fremont (ship canal)
    (47.6680, -122.3840, 12),   # Ballard
    (47.6600, -122.3140, 35),   # U District
    (47.6725, -122.3020, 60),   # Ravenna
    (47.6800, -122.2760, 30),   # Sand Point
    (47.7050, -122.3280, 90),   # Northgate
    (47.6500, -122.4000, 76),   # Magnolia
    (47.6760, -122.3170, 70),   # Roosevelt
    (47.6800, -122.2780, 40),   # View Ridge
    (47.6450, -122.3350, 5),    # Lake Union shore
    (47.6470, -122.3250, 6),    # Portage Bay
]

# Real arterial/freeway corridors as polylines [(lat,lon), ...] with a reference
# sound level (dB) at 15 m. Used as line noise sources.
ROADS: list[dict] = [
    {"name": "I-5", "ref_db": 82,
     "line": [(47.600, -122.3260), (47.640, -122.3255), (47.690, -122.3232),
              (47.730, -122.3235)]},
    {"name": "SR-99 Aurora Ave N", "ref_db": 76,
     "line": [(47.600, -122.3465), (47.660, -122.3465), (47.700, -122.3465),
              (47.730, -122.3465)]},
    {"name": "Lake City Way NE", "ref_db": 74,
     "line": [(47.6650, -122.3230), (47.6900, -122.3060), (47.7230, -122.2930)]},
    {"name": "NE/N 45th St", "ref_db": 69,
     "line": [(47.6612, -122.3900), (47.6610, -122.3230), (47.6608, -122.2900)]},
    {"name": "N/NE 85th St", "ref_db": 67,
     "line": [(47.6905, -122.3800), (47.6905, -122.3232), (47.6905, -122.2900)]},
    {"name": "15th Ave NW", "ref_db": 67,
     "line": [(47.6500, -122.3765), (47.6900, -122.3765)]},
    {"name": "Roosevelt/12th Ave NE", "ref_db": 64,
     "line": [(47.6550, -122.3170), (47.7000, -122.3170)]},
]

AMBIENT_DB = 45.0
_M_PER_DEG_LAT = 111_320.0


def _m_per_deg_lon(lat: float) -> float:
    return 111_320.0 * math.cos(math.radians(lat)) or 1e-6


def _to_xy(lat: float, lon: float, lat0: float) -> tuple[float, float]:
    return lon * _m_per_deg_lon(lat0), lat * _M_PER_DEG_LAT


def _point_seg_dist_m(lat: float, lon: float, a: tuple, b: tuple) -> float:
    """Distance (m) from a point to a segment a-b using local equirectangular xy."""
    lat0 = lat
    px, py = _to_xy(lat, lon, lat0)
    ax, ay = _to_xy(a[0], a[1], lat0)
    bx, by = _to_xy(b[0], b[1], lat0)
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def _idw(lat: float, lon: float, points: Iterable[tuple], power: float = 2.0) -> float:
    """Inverse-distance-weighted interpolation. ``points`` = (lat, lon, value)."""
    num = den = 0.0
    for plat, plon, val in points:
        dx = (lon - plon) * _m_per_deg_lon(lat)
        dy = (lat - plat) * _M_PER_DEG_LAT
        d2 = dx * dx + dy * dy
        if d2 < 1.0:
            return val
        w = 1.0 / (d2 ** (power / 2.0))
        num += w * val
        den += w
    return num / den if den else 0.0


def crime_index_at(lat: float, lon: float) -> float:
    pts = [(la, lo, v) for (_n, la, lo, v) in NEIGHBORHOOD_CRIME]
    return round(_idw(lat, lon, pts), 1)


def elevation_at(lat: float, lon: float) -> float:
    return _idw(lat, lon, ELEVATION_POINTS)


def noise_db_at(lat: float, lon: float) -> float:
    """FHWA-style line-source noise: level = ref - 15*log10(d/15), max over roads."""
    best = AMBIENT_DB
    for road in ROADS:
        line = road["line"]
        dmin = min(
            _point_seg_dist_m(lat, lon, line[i], line[i + 1])
            for i in range(len(line) - 1)
        )
        d = max(15.0, dmin)
        level = road["ref_db"] - 15.0 * math.log10(d / 15.0)
        best = max(best, level)
    return round(best, 1)
