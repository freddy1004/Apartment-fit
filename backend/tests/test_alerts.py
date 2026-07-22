from app.analysis.demo import seattle_demo_profile
from app.listings.matcher import (
    EmailNotifier,
    LoggingNotifier,
    WebhookNotifier,
    build_notifier,
)


def test_webhook_notifier_posts_payload():
    calls = []
    n = WebhookNotifier("http://example.test/hook", poster=lambda url, json: calls.append((url, json)))
    p = seattle_demo_profile()
    n.notify(p, [{"listing_id": "L1", "address": "Fremont", "combined_fit": 88, "combined_tier": "strong_fit"}])
    assert len(calls) == 1
    url, payload = calls[0]
    assert url == "http://example.test/hook"
    assert payload["match_count"] == 1
    assert payload["matches"][0]["listing_id"] == "L1"


def test_webhook_notifier_skips_empty():
    calls = []
    n = WebhookNotifier("http://x", poster=lambda url, json: calls.append(1))
    n.notify(seattle_demo_profile(), [])
    assert calls == []


def test_email_notifier_unconfigured_is_safe():
    # No SMTP host -> should not raise, just log.
    EmailNotifier().notify(seattle_demo_profile(), [{"listing_id": "L1", "address": "x", "combined_fit": 80, "combined_tier": "qualifying"}])


def test_build_notifier_selects_by_env(monkeypatch):
    monkeypatch.setenv("ALERT_NOTIFIER", "webhook")
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "http://hook")
    assert isinstance(build_notifier(), WebhookNotifier)
    monkeypatch.setenv("ALERT_NOTIFIER", "email")
    assert isinstance(build_notifier(), EmailNotifier)
    monkeypatch.setenv("ALERT_NOTIFIER", "console")
    assert isinstance(build_notifier(), LoggingNotifier)


def test_new_match_detection_via_api(client):
    # Isolated profile so alert state is clean.
    client.post("/api/profiles/seed-demo")
    pid = client.post("/api/profiles/demo-seattle/duplicate", json={
        "name": "Alert test", "city": "Testville", "center_lat": 47.66,
        "center_lon": -122.33, "bbox": [-122.42, 47.60, -122.27, 47.73],
    }).json()["id"]
    client.post(f"/api/analysis/{pid}/run")
    client.post(f"/api/profiles/{pid}/listings/manual", json={
        "address": "Fremont", "lat": 47.651, "lon": -122.35, "rent": 1900, "bedrooms": 2})

    first = client.post(f"/api/profiles/{pid}/listings/alerts/run").json()
    assert first["total_matches"] >= 1
    assert first["notified"] == first["total_matches"]  # all new the first time

    # Second run: same listings -> nothing new.
    second = client.post(f"/api/profiles/{pid}/listings/alerts/run").json()
    assert second["notified"] == 0

    # Add another matching listing -> exactly one new alert.
    client.post(f"/api/profiles/{pid}/listings/manual", json={
        "address": "Wallingford", "lat": 47.66, "lon": -122.334, "rent": 1800, "bedrooms": 1})
    third = client.post(f"/api/profiles/{pid}/listings/alerts/run").json()
    assert third["notified"] == 1
