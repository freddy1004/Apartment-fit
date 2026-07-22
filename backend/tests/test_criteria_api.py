"""Tests for defining new criteria via the builder API."""


def _fresh_profile(client):
    client.post("/api/profiles/seed-demo")
    return client.post("/api/profiles/demo-seattle/duplicate", json={
        "name": "Builder test", "city": "Testville", "center_lat": 47.66,
        "center_lon": -122.33, "bbox": [-122.42, 47.60, -122.27, 47.73],
    }).json()["id"]


def test_add_amenity_distance_criterion_miles(client):
    pid = _fresh_profile(client)
    r = client.post(f"/api/profiles/{pid}/criteria", json={
        "scope": "area", "source": "amenity", "amenity_type": "park",
        "mode": "walk", "measure": "distance", "threshold": 0.5,
        "kind": "hard", "weight": 2.0,
    })
    assert r.status_code == 200
    crit = r.json()
    assert crit["units"] == "miles"       # distance, not minutes
    assert crit["method"] == "poi_distance"
    assert crit["kind"] == "hard"
    # it now appears in the profile
    prof = client.get(f"/api/profiles/{pid}").json()
    assert any(c["id"] == crit["id"] for c in prof["criteria"])


def test_add_place_criterion_geocodes(client):
    pid = _fresh_profile(client)
    r = client.post(f"/api/profiles/{pid}/criteria", json={
        "scope": "area", "source": "place", "dest_address": "Green Lake",
        "mode": "bike", "measure": "time", "threshold": 15, "kind": "preference",
    })
    assert r.status_code == 200
    crit = r.json()
    assert crit["method"] == "route"
    assert crit["units"] == "minutes"
    assert crit["destination"]["lat"] is not None      # geocoded
    assert crit["resolved_destination"] is not None


def test_add_place_by_latlon(client):
    pid = _fresh_profile(client)
    r = client.post(f"/api/profiles/{pid}/criteria", json={
        "scope": "area", "source": "place", "dest_lat": 47.6806, "dest_lon": -122.3286,
        "label": "Close to my office", "mode": "drive", "measure": "distance",
        "threshold": 3, "kind": "preference", "weight": 1.5,
    })
    assert r.status_code == 200
    crit = r.json()
    assert crit["label"] == "Close to my office"
    assert crit["destination"]["lat"] == 47.6806


def test_add_listing_criteria(client):
    pid = _fresh_profile(client)
    rent = client.post(f"/api/profiles/{pid}/criteria", json={
        "scope": "listing", "field": "rent", "threshold": 2500, "kind": "hard"}).json()
    assert rent["comparator"] == "lte" and rent["scope"] == "listing"
    beds = client.post(f"/api/profiles/{pid}/criteria", json={
        "scope": "listing", "field": "bedrooms", "threshold": 2}).json()
    assert beds["comparator"] == "gte"
    pets = client.post(f"/api/profiles/{pid}/criteria", json={
        "scope": "listing", "field": "pets", "kind": "hard"}).json()
    assert pets["comparator"] == "true" and pets["method"] == "boolean"


def test_delete_defined_criterion(client):
    pid = _fresh_profile(client)
    crit = client.post(f"/api/profiles/{pid}/criteria", json={
        "scope": "listing", "field": "size", "threshold": 700}).json()
    assert client.delete(f"/api/profiles/{pid}/criteria/{crit['id']}").status_code == 200
    prof = client.get(f"/api/profiles/{pid}").json()
    assert not any(c["id"] == crit["id"] for c in prof["criteria"])


def test_bad_requests(client):
    pid = _fresh_profile(client)
    # amenity scope without amenity_type
    assert client.post(f"/api/profiles/{pid}/criteria", json={
        "scope": "area", "source": "amenity", "threshold": 1}).status_code == 400
    # listing without field
    assert client.post(f"/api/profiles/{pid}/criteria", json={
        "scope": "listing", "threshold": 1}).status_code == 400
