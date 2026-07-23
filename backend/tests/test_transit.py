"""Two transit definitions: major stations (option 1) vs any stop incl. bus (2)."""
from app.criteria import builder as B
from app.analysis.geo import haversine_m, meters_to_miles
from app.providers.osm import _OVERPASS_FILTER
from app.providers.registry import Providers

PROV = Providers("fixture")
BBOX = [-122.42, 47.60, -122.27, 47.73]


def test_transit_stop_is_stations_only_label():
    c = B.transit()
    assert "major transit station" in c.label
    assert c.destination.amenity_type == "transit_stop"


def test_transit_any_template_includes_bus():
    c = B.transit_any()
    assert c.destination.amenity_type == "transit_any"
    assert "bus" in c.label.lower()


def test_any_has_more_stops_than_stations():
    stations = PROV.find_pois("transit_stop", BBOX)
    anystops = PROV.find_pois("transit_any", BBOX)
    assert len(anystops) > len(stations)


def test_any_is_closer_on_capitol_hill():
    # Capitol Hill has bus service but the nearest rail *station* is farther.
    lat, lon = 47.6210, -122.3200
    st = min(PROV.find_pois("transit_stop", BBOX), key=lambda p: haversine_m(lat, lon, p.lat, p.lon))
    an = min(PROV.find_pois("transit_any", BBOX), key=lambda p: haversine_m(lat, lon, p.lat, p.lon))
    d_st = meters_to_miles(haversine_m(lat, lon, st.lat, st.lon))
    d_an = meters_to_miles(haversine_m(lat, lon, an.lat, an.lon))
    assert d_an <= d_st  # a bus stop is at least as close as the nearest station


def test_overpass_filters_distinct():
    assert _OVERPASS_FILTER["transit_stop"] != _OVERPASS_FILTER["transit_any"]
    # any-transit must include bus stops
    assert any("bus_stop" in f for f in _OVERPASS_FILTER["transit_any"])
    assert not any("bus_stop" in f for f in _OVERPASS_FILTER["transit_stop"])


def test_add_transit_any_criterion_via_api(client):
    client.post("/api/profiles/seed-demo")
    pid = client.post("/api/profiles/demo-seattle/duplicate", json={
        "name": "T", "city": "T", "center_lat": 47.66, "center_lon": -122.33,
        "bbox": BBOX}).json()["id"]
    r = client.post(f"/api/profiles/{pid}/criteria", json={
        "scope": "area", "source": "amenity", "amenity_type": "transit_any",
        "mode": "walk", "measure": "time", "threshold": 10, "kind": "preference"})
    assert r.status_code == 200
    crit = r.json()
    assert crit["type"] == "transit"
    assert crit["destination"]["amenity_type"] == "transit_any"
    assert "bus" in crit["label"].lower()
