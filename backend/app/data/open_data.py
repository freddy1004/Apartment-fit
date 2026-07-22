"""Live open-data loaders for Seattle (used when the network allows).

Sources (all public, no key required):
- SPD crime      -> Socrata  https://data.seattle.gov/resource/tazs-3rd5.json
- Road geometry  -> OSM Overpass (major highways) for the noise model
- Elevation      -> USGS EPQS / OpenTopoData for terrain

Results are cached under ``data/cache/`` so a single fetch serves many runs.
When a source is unreachable (e.g. restricted network), callers fall back to the
bundled real-Seattle-grounded reference data in ``seattle_real.py``. Refresh the
bundle with ``scripts/fetch_seattle_data.py``.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from ..criteria.schema import Layer

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
_TIMEOUT = float(os.getenv("PROVIDER_TIMEOUT_S", "20"))

SOCRATA_CRIME = os.getenv(
    "SPD_CRIME_URL", "https://data.seattle.gov/resource/tazs-3rd5.json")
ELEVATION_URL = os.getenv(
    "ELEVATION_URL", "https://api.opentopodata.org/v1/ned10m")


def _cache_path(name: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, name)


def _read_cache(name: str) -> Optional[dict]:
    p = _cache_path(name)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return None


def _write_cache(name: str, data: dict) -> None:
    with open(_cache_path(name), "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def fetch_spd_crime_counts(bbox: list[float], months: int = 12,
                           limit: int = 50000) -> list[dict]:
    """Fetch recent SPD offenses with coordinates inside ``bbox`` (Socrata SoQL)."""
    import httpx

    min_lon, min_lat, max_lon, max_lat = bbox
    where = (f"latitude between {min_lat} and {max_lat} "
             f"and longitude between {min_lon} and {max_lon} "
             f"and offense_start_datetime > '{_months_ago(months)}'")
    r = httpx.get(SOCRATA_CRIME, params={
        "$select": "latitude,longitude,offense",
        "$where": where, "$limit": limit,
    }, timeout=_TIMEOUT)
    r.raise_for_status()
    rows = r.json()
    out = []
    for row in rows:
        try:
            out.append({"lat": float(row["latitude"]), "lon": float(row["longitude"])})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _months_ago(months: int) -> str:
    from datetime import datetime, timedelta, timezone
    dt = datetime.now(timezone.utc) - timedelta(days=30 * months)
    return dt.strftime("%Y-%m-%dT00:00:00")


def build_live_crime_layer(bbox: list[float], rows: int = 10, cols: int = 10) -> Layer:
    """Aggregate live SPD incidents into a normalized 0-100 choropleth grid."""
    incidents = fetch_spd_crime_counts(bbox)
    min_lon, min_lat, max_lon, max_lat = bbox
    dlat = (max_lat - min_lat) / rows
    dlon = (max_lon - min_lon) / cols
    counts = [[0] * cols for _ in range(rows)]
    for it in incidents:
        r = min(rows - 1, max(0, int((it["lat"] - min_lat) / dlat)))
        c = min(cols - 1, max(0, int((it["lon"] - min_lon) / dlon)))
        counts[r][c] += 1
    peak = max((max(row) for row in counts), default=0) or 1
    features = []
    for r in range(rows):
        for c in range(cols):
            lat0, lat1 = min_lat + r * dlat, min_lat + (r + 1) * dlat
            lon0, lon1 = min_lon + c * dlon, min_lon + (c + 1) * dlon
            idx = round(100.0 * counts[r][c] / peak, 1)
            features.append({
                "type": "Feature",
                "properties": {"crime_index": idx, "incidents": counts[r][c],
                               "name": f"grid r{r}c{c}"},
                "geometry": {"type": "Polygon", "coordinates": [[
                    [lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0],
                ]]},
            })
    fc = {"type": "FeatureCollection", "features": features}
    _write_cache("crime_live.json", fc)
    return Layer(id="crime", name="SPD reported incidents (live, last 12 mo)",
                 kind="choropleth", units="index", value_property="crime_index",
                 default_value=0.0, features=fc)


def fetch_elevations(points: list[tuple[float, float]]) -> list[float]:
    """Batch elevation lookups (lat, lon) via OpenTopoData/USGS."""
    import httpx

    locs = "|".join(f"{lat},{lon}" for lat, lon in points)
    r = httpx.get(ELEVATION_URL, params={"locations": locs}, timeout=_TIMEOUT)
    r.raise_for_status()
    return [pt.get("elevation") for pt in r.json().get("results", [])]


def load_cached_crime_layer() -> Optional[Layer]:
    fc = _read_cache("crime_live.json")
    if not fc:
        return None
    return Layer(id="crime", name="SPD reported incidents (cached live)",
                 kind="choropleth", units="index", value_property="crime_index",
                 default_value=0.0, features=fc)
