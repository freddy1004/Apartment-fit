"""Grocery-coverage regression test.

Guards against the 'nearest grocery is implausibly far' problem (e.g. Capitol
Hill resolving to Safeway Queen Anne because central-Seattle stores were missing
from the fixture).
"""
import pytest

from app.analysis.geo import haversine_m, meters_to_miles
from app.providers.registry import Providers

PROV = Providers("fixture")
BBOX = [-122.42, 47.60, -122.27, 47.73]

# neighborhood center -> generous max distance (mi) to the nearest full-service store
NEIGHBORHOODS = {
    "Capitol Hill": (47.6234, -122.3211),
    "First Hill": (47.6090, -122.3250),
    "Downtown": (47.6090, -122.3380),
    "Belltown": (47.6150, -122.3450),
    "Central District": (47.6045, -122.3005),
    "South Lake Union": (47.6250, -122.3380),
    "Queen Anne": (47.6370, -122.3570),
    "Magnolia": (47.6500, -122.4000),
    "Ballard": (47.6680, -122.3840),
    "Fremont": (47.6510, -122.3500),
    "Wallingford": (47.6600, -122.3340),
    "Green Lake": (47.6800, -122.3280),
    "Northgate": (47.7050, -122.3280),
    "Lake City": (47.7200, -122.2960),
    "Greenwood": (47.6930, -122.3550),
    "U-District": (47.6600, -122.3140),
}


def _nearest(lat, lon):
    pois = PROV.find_pois("supermarket", BBOX)
    n = min(pois, key=lambda p: haversine_m(lat, lon, p.lat, p.lon))
    return n, meters_to_miles(haversine_m(lat, lon, n.lat, n.lon))


@pytest.mark.parametrize("name,coord", NEIGHBORHOODS.items())
def test_every_neighborhood_has_a_nearby_grocery(name, coord):
    _, dist = _nearest(*coord)
    assert dist <= 0.75, f"{name}: nearest grocery is {dist:.2f} mi away"


def test_capitol_hill_resolves_to_a_capitol_hill_store():
    # Regression: must NOT pick Safeway Queen Anne for Capitol Hill.
    n, dist = _nearest(47.6234, -122.3211)
    assert "Queen Anne" not in n.name
    assert dist < 0.2


def test_store_count_is_comprehensive():
    assert len(PROV.find_pois("supermarket", BBOX)) >= 30
