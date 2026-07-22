"""Generated geospatial fixture layers (crime index, noise contours).

These stand in for real open-data layers (police-report densities, DOT noise
models) so the "safe" and "quiet" proxies suggested by the ambiguity flagger are
actually computable offline. Swap in real GeoJSON via the layer-import endpoint
for production; the schema and evaluation are identical.
"""
from __future__ import annotations

import math

from ..criteria.schema import Layer
from ..providers.fixture import load_fixture


def _square(lat: float, lon: float, half_m: float) -> list[list[float]]:
    dlat = half_m / 111_320.0
    dlon = half_m / (111_320.0 * math.cos(math.radians(lat)) or 1e-6)
    return [
        [lon - dlon, lat - dlat], [lon + dlon, lat - dlat],
        [lon + dlon, lat + dlat], [lon - dlon, lat + dlat], [lon - dlon, lat - dlat],
    ]


def crime_layer(bbox: list[float], rows: int = 6, cols: int = 6) -> Layer:
    """A choropleth grid with a synthetic ``crime_index`` (0-100, lower = safer).

    Deterministic: higher toward the south/downtown, lower to the north — a
    stand-in for a real reported-incident density surface.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    dlat = (max_lat - min_lat) / rows
    dlon = (max_lon - min_lon) / cols
    ref_lat = load_fixture()["downtown_reference"]["lat"]
    features = []
    for r in range(rows):
        for c in range(cols):
            lat0, lat1 = min_lat + r * dlat, min_lat + (r + 1) * dlat
            lon0, lon1 = min_lon + c * dlon, min_lon + (c + 1) * dlon
            clat = (lat0 + lat1) / 2
            # index falls off ~10 points per 0.02deg north of downtown
            idx = max(5.0, min(95.0, 60.0 - (clat - ref_lat) * 500.0
                               + 8.0 * math.sin(c * 1.3)))
            features.append({
                "type": "Feature",
                "properties": {"crime_index": round(idx, 1),
                               "name": f"grid r{r}c{c}"},
                "geometry": {"type": "Polygon", "coordinates": [[
                    [lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0],
                ]]},
            })
    return Layer(
        id="crime", name="Reported-incident index (synthetic)", kind="choropleth",
        units="index", value_property="crime_index", default_value=50.0,
        features={"type": "FeatureCollection", "features": features},
    )


def noise_layer() -> Layer:
    """Noise contours (``noise_db``) as buffers around freeway ramps / I-5."""
    fx = load_fixture()
    features = []
    for ramp in fx.get("freeway_ramp", []):
        features.append({
            "type": "Feature",
            "properties": {"noise_db": 72.0, "name": f"near {ramp['name']}"},
            "geometry": {"type": "Polygon",
                         "coordinates": [_square(ramp["lat"], ramp["lon"], 350)]},
        })
    return Layer(
        id="noise", name="Traffic noise contours (synthetic)", kind="choropleth",
        units="dB", value_property="noise_db", default_value=48.0,
        features={"type": "FeatureCollection", "features": features},
    )


def seattle_layers(bbox: list[float]) -> list[Layer]:
    return [crime_layer(bbox), noise_layer()]
