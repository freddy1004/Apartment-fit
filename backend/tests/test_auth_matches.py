"""Auth ownership + saved-search matching.

Auth is opt-in; these tests exercise both the default (public, no-token) behavior
and the enabled path by flipping ``settings.auth_enabled`` on the running app
(no module reloads, so no cross-test pollution).
"""
from app.analysis.demo import seattle_demo_profile
from app.analysis.engine import run_city_analysis
from app.listings.matcher import LoggingNotifier, find_matches, run_alerts
from app.providers.registry import Providers

PROV = Providers("fixture")


def test_find_matches_only_hard_passers():
    p = seattle_demo_profile()
    analysis = run_city_analysis(p, PROV)
    listings = [
        {"id": "north", "address": "Fremont", "lat": 47.6510, "lon": -122.3500, "rent": 1900, "bedrooms": 2},
        {"id": "south", "address": "SoDo", "lat": 47.5700, "lon": -122.3300, "rent": 1500, "bedrooms": 1},
        {"id": "nogeo", "address": "unknown"},  # no lat/lon -> skipped
    ]
    matches = find_matches(p, listings, PROV, analysis)
    ids = {m["listing_id"] for m in matches}
    assert "north" in ids       # passes hard requirements
    assert "south" not in ids   # fails north-of gate
    assert "nogeo" not in ids   # ungeocoded


def test_run_alerts_uses_notifier():
    p = seattle_demo_profile()
    sent = {}

    class Spy(LoggingNotifier):
        def notify(self, profile, matches):
            sent["count"] = len(matches)

    listings = [{"id": "n", "address": "Fremont", "lat": 47.651, "lon": -122.35, "rent": 1900}]
    run_alerts(p, listings, PROV, None, Spy())
    assert sent["count"] == 1


def test_matches_endpoint(client):
    pid = client.post("/api/profiles/seed-demo").json()["id"]
    client.post(f"/api/analysis/{pid}/run")
    client.post(f"/api/profiles/{pid}/listings/manual", json={
        "address": "Fremont", "lat": 47.651, "lon": -122.35, "rent": 1900, "bedrooms": 2})
    client.post(f"/api/profiles/{pid}/listings/manual", json={
        "address": "SoDo", "lat": 47.57, "lon": -122.33, "rent": 1500})
    res = client.get(f"/api/profiles/{pid}/listings/matches").json()
    assert res["match_count"] >= 1
    assert all(m["combined_tier"] != "ineligible" for m in res["matches"])


def test_auth_status_default_public(client):
    assert client.get("/api/auth/status").json()["auth_enabled"] is False


def test_auth_enabled_flow(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "auth_enabled", True)  # auto-restored after test

    # No token -> 401 on a protected route
    assert client.get("/api/profiles").status_code == 401

    # Register -> token; /me echoes identity
    tok = client.post("/api/auth/register", json={"email": "owner@x.com"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/auth/me", headers=h).json()["email"] == "owner@x.com"

    # Owner creates a fresh, privately-owned profile
    pid = "owned-private-1"
    client.post("/api/profiles", headers=h, json={
        "id": pid, "name": "Private", "city": "Seattle",
        "center_lat": 47.66, "center_lon": -122.33})
    assert any(p["id"] == pid for p in client.get("/api/profiles", headers=h).json())

    # A different user is scoped out of it
    tok2 = client.post("/api/auth/register", json={"email": "other@y.com"}).json()["token"]
    h2 = {"Authorization": f"Bearer {tok2}"}
    assert client.get(f"/api/profiles/{pid}", headers=h2).status_code == 404
    assert not any(p["id"] == pid for p in client.get("/api/profiles", headers=h2).json())
    assert client.get("/api/auth/me").status_code == 401  # still requires token
