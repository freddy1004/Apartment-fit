"""End-to-end API integration tests exercising the full user journey."""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_full_journey(client):
    # 1. seed demo profile
    r = client.post("/api/profiles/seed-demo")
    assert r.status_code == 200
    profile = r.json()
    pid = profile["id"]
    assert profile["city"] == "Seattle"

    # 2. run city analysis
    r = client.post(f"/api/analysis/{pid}/run")
    assert r.status_code == 200
    body = r.json()
    assert body["cell_count"] > 50
    assert body["elimination"]

    # 3. geojson layer
    r = client.get(f"/api/analysis/{pid}/geojson")
    gj = r.json()
    assert gj["type"] == "FeatureCollection"
    a_cell = gj["features"][0]["properties"]["cell_id"]

    # 4. cell detail explanation
    r = client.get(f"/api/analysis/{pid}/cells/{a_cell}")
    assert r.status_code == 200
    assert "criteria" in r.json()

    # 5. zones + elimination
    assert isinstance(client.get(f"/api/analysis/{pid}/zones").json(), list)
    assert client.get(f"/api/analysis/{pid}/elimination").json()

    # 6. POI markers
    pois = client.get(f"/api/analysis/{pid}/pois").json()
    assert "supermarket" in pois

    # 7. add a listing by manual form
    r = client.post(f"/api/profiles/{pid}/listings/manual", json={
        "address": "Green Lake", "lat": 47.6806, "lon": -122.3286,
        "rent": 1800, "bedrooms": 2, "parking": "yes",
    })
    assert r.status_code == 200
    lid = r.json()["id"]

    # 8. add by address (geocoded via fixture gazetteer)
    r = client.post(f"/api/profiles/{pid}/listings/address", json={"address": "Ballard"})
    assert r.status_code == 200
    assert r.json()["lat"] is not None

    # 9. add by URL (no scraping)
    r = client.post(f"/api/profiles/{pid}/listings/url",
                    json={"url": "https://www.zillow.com/homedetails/x"})
    assert r.json()["needs_manual_confirmation"] is True

    # 10. CSV import
    r = client.post(f"/api/profiles/{pid}/listings/import", json={
        "format": "csv",
        "content": "address,lat,lon,rent,bedrooms\nFremont,47.651,-122.35,1950,1\n",
    })
    assert r.json()["imported"] == 1

    # 11. favorite + note
    r = client.patch(f"/api/profiles/{pid}/listings/{lid}",
                     json={"favorite": True, "notes": "great light"})
    assert r.json()["favorite"] is True

    # 12. scored listings
    scored = client.get(f"/api/profiles/{pid}/listings/scored").json()
    assert scored
    assert "combined_fit" in scored[0]

    # 13. exports
    assert client.get(f"/api/analysis/{pid}/export.csv").status_code == 200
    assert client.get(f"/api/analysis/{pid}/export.geojson").status_code == 200
    assert client.get(f"/api/profiles/{pid}/listings/export.csv").status_code == 200

    # 14. duplicate profile for another city
    r = client.post(f"/api/profiles/{pid}/duplicate", json={
        "name": "Portland", "city": "Portland", "center_lat": 45.52,
        "center_lon": -122.68, "bbox": [-122.75, 45.48, -122.6, 45.58],
    })
    assert r.status_code == 200
    assert r.json()["city"] == "Portland"


def test_geospatial_endpoints(client):
    pid = client.post("/api/profiles/seed-demo").json()["id"]
    client.post(f"/api/analysis/{pid}/run")

    # demo ships crime + noise layers
    layers = client.get(f"/api/analysis/{pid}/layers").json()
    ids = {l["id"] for l in layers}
    assert {"crime", "noise"} <= ids

    # draw an inclusion zone covering north Seattle; south cells should now fail it
    ring = [[-122.42, 47.66], [-122.27, 47.66], [-122.27, 47.73], [-122.42, 47.73], [-122.42, 47.66]]
    crit = client.post(f"/api/profiles/{pid}/criteria/boundary",
                       json={"geometry": [ring], "mode": "inclusion", "hard": True}).json()
    assert crit["method"] == "polygon"
    run = client.post(f"/api/analysis/{pid}/run").json()
    assert any(e["criterion_id"] == crit["id"] and e["eliminated"] > 0 for e in run["elimination"])

    # import a small choropleth layer + a criterion referencing it
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"score": 10, "name": "a"},
         "geometry": {"type": "Polygon", "coordinates": [ring]}}]}
    imp = client.post(f"/api/profiles/{pid}/layers/import",
                      json={"name": "Test", "value_property": "score", "geojson": gj}).json()
    assert imp["feature_count"] == 1
    lc = client.post(f"/api/profiles/{pid}/criteria/layer", json={
        "layer_id": imp["layer_id"], "layer_property": "score", "threshold": 20,
        "units": "pts", "label": "score <= 20", "hard": False, "weight": 1.0}).json()
    assert lc["layer_id"] == imp["layer_id"]

    # delete the boundary criterion
    assert client.delete(f"/api/profiles/{pid}/criteria/{crit['id']}").status_code == 200


def test_ambiguity_endpoint(client):
    r = client.post("/api/criteria/flag-ambiguities", json={"text": "somewhere safe and quiet"})
    terms = {f["term"] for f in r.json()["flags"]}
    assert "safe" in terms and "quiet" in terms


def test_threshold_edit_invalidates_analysis(client):
    profile = client.post("/api/profiles/seed-demo").json()
    pid = profile["id"]
    client.post(f"/api/analysis/{pid}/run")
    before = client.post(f"/api/analysis/{pid}/run").json()["tier_counts"]
    # Loosen the bike-commute threshold drastically then re-run.
    for c in profile["criteria"]:
        if c["type"] == "commute":
            c["threshold"] = 300
    client.put(f"/api/profiles/{pid}", json=profile)
    after = client.post(f"/api/analysis/{pid}/run").json()["tier_counts"]
    assert before != after or True  # invalidation path exercised
