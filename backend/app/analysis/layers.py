"""Geospatial layers backed by real-Seattle-grounded data.

Crime and noise are choropleth grids computed from the reference data in
``data/seattle_real.py`` (real neighborhood crime patterns via inverse-distance
weighting; a line-source noise model over real freeway/arterial geometry). For
live data, ``scripts/fetch_seattle_data.py`` regenerates the reference data from
SPD (Socrata), USGS elevation, and OSM/Overpass, and ``open_data.py`` can load
cached live layers directly.
"""
from __future__ import annotations

from ..criteria.schema import Layer
from ..data import seattle_real as R


def _grid_features(bbox: list[float], value_fn, prop: str,
                   rows: int = 10, cols: int = 10) -> list[dict]:
    min_lon, min_lat, max_lon, max_lat = bbox
    dlat = (max_lat - min_lat) / rows
    dlon = (max_lon - min_lon) / cols
    features = []
    for r in range(rows):
        for c in range(cols):
            lat0, lat1 = min_lat + r * dlat, min_lat + (r + 1) * dlat
            lon0, lon1 = min_lon + c * dlon, min_lon + (c + 1) * dlon
            val = value_fn((lat0 + lat1) / 2, (lon0 + lon1) / 2)
            features.append({
                "type": "Feature",
                "properties": {prop: val, "name": f"grid r{r}c{c}"},
                "geometry": {"type": "Polygon", "coordinates": [[
                    [lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0],
                ]]},
            })
    return features


def crime_layer(bbox: list[float], rows: int = 10, cols: int = 10) -> Layer:
    feats = _grid_features(bbox, R.crime_index_at, "crime_index", rows, cols)
    return Layer(
        id="crime", name="Reported-incident index (SPD-grounded)", kind="choropleth",
        units="index", value_property="crime_index", default_value=50.0,
        features={"type": "FeatureCollection", "features": feats},
    )


def noise_layer(bbox: list[float] | None = None, rows: int = 12, cols: int = 12) -> Layer:
    bbox = bbox or [-122.42, 47.60, -122.27, 47.73]
    feats = _grid_features(bbox, R.noise_db_at, "noise_db", rows, cols)
    return Layer(
        id="noise", name="Traffic noise (FHWA model over real arterials)", kind="choropleth",
        units="dB", value_property="noise_db", default_value=R.AMBIENT_DB,
        features={"type": "FeatureCollection", "features": feats},
    )


def seattle_layers(bbox: list[float]) -> list[Layer]:
    # Prefer a cached live SPD crime layer (from scripts/fetch_seattle_data.py)
    # when present; otherwise use the bundled real-grounded model.
    from ..data.open_data import load_cached_crime_layer
    live_crime = load_cached_crime_layer()
    return [live_crime or crime_layer(bbox), noise_layer(bbox)]
