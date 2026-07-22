from app.analysis.demo import seattle_demo_profile
from app.analysis.engine import analysis_signature, run_city_analysis
from app.providers.registry import Providers

PROV = Providers("fixture")


def test_signature_stable_and_sensitive():
    p = seattle_demo_profile()
    s1 = analysis_signature(p)
    s2 = analysis_signature(seattle_demo_profile())
    assert s1 == s2  # identical profiles -> identical signature
    # changing a threshold changes the signature
    for c in p.criteria:
        if c.type.value == "commute":
            c.threshold = 45
    assert analysis_signature(p) != s1


def test_signature_ignores_listing_only_changes():
    p = seattle_demo_profile()
    s1 = analysis_signature(p)
    # editing a listing-scope criterion must not change the AREA signature
    for c in p.criteria:
        if c.scope.value == "listing":
            c.weight = 4.2
    assert analysis_signature(p) == s1


def test_result_carries_signature():
    p = seattle_demo_profile()
    r = run_city_analysis(p, PROV)
    assert r.signature == analysis_signature(p)
    assert r.summary()["signature"] == r.signature


def test_zones_sorted_by_size_then_confidence():
    r = run_city_analysis(seattle_demo_profile(), PROV)
    sizes = [z["cell_count"] for z in r.zones]
    assert sizes == sorted(sizes, reverse=True)
    for z in r.zones:
        assert "avg_confidence" in z


def test_snapshot_api_records_history(client):
    # Use a freshly duplicated profile so its snapshot history is isolated.
    client.post("/api/profiles/seed-demo")
    pid = client.post("/api/profiles/demo-seattle/duplicate", json={
        "name": "Snap test", "city": "Testville", "center_lat": 47.66,
        "center_lon": -122.33, "bbox": [-122.42, 47.60, -122.27, 47.73],
    }).json()["id"]

    client.post(f"/api/analysis/{pid}/run")
    client.post(f"/api/analysis/{pid}/run")  # same signature -> deduped
    snaps = client.get(f"/api/analysis/{pid}/snapshots").json()
    assert len(snaps) == 1

    # change a threshold -> new signature -> new snapshot
    profile = client.get(f"/api/profiles/{pid}").json()
    for c in profile["criteria"]:
        if c["type"] == "groceries":
            c["threshold"] = 2.0
    client.put(f"/api/profiles/{pid}", json=profile)
    client.post(f"/api/analysis/{pid}/run")
    snaps2 = client.get(f"/api/analysis/{pid}/snapshots").json()
    assert len(snaps2) == 2
    assert snaps2[0]["signature"] != snaps2[1]["signature"]
