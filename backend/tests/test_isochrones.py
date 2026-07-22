from app.analysis.demo import seattle_demo_profile
from app.analysis.engine import (
    measurement_cache_stats,
    reset_measurement_cache,
    run_city_analysis,
)
from app.analysis.precompute import build_isochrones
from app.analysis.scoring import measurement_signature, regrade
from app.criteria import builder as B
from app.providers.registry import Providers

PROV = Providers("fixture")


def test_measurement_signature_ignores_threshold_and_weight():
    c1 = B.commute("dt", 47.62, -122.33, minutes=30, mode=B.Mode.BIKE)
    c2 = c1.model_copy(deep=True)
    c2.threshold = 45
    c2.weight = 3.0
    assert measurement_signature(c1) == measurement_signature(c2)


def test_measurement_signature_sensitive_to_destination():
    c1 = B.commute("a", 47.62, -122.33, minutes=30)
    c2 = B.commute("b", 47.70, -122.30, minutes=30)
    assert measurement_signature(c1) != measurement_signature(c2)


def test_regrade_reuses_raw_measurement():
    p = seattle_demo_profile()
    reset_measurement_cache()
    run_city_analysis(p, PROV)
    after_first = measurement_cache_stats()
    assert after_first["misses"] > 0
    assert after_first["hits"] == 0

    # Change only thresholds -> re-run should be ALL cache hits, no new misses.
    for c in p.criteria:
        if c.type.value in ("commute", "groceries"):
            c.threshold = (c.threshold or 10) * 1.3
    run_city_analysis(p, PROV)
    after_second = measurement_cache_stats()
    assert after_second["hits"] > after_first["hits"]
    assert after_second["misses"] == after_first["misses"]  # nothing re-measured


def test_regrade_changes_verdict_with_new_threshold():
    c = B.commute("dt", 47.62, -122.33, minutes=1, mode=B.Mode.BIKE, hard=True)
    from app.analysis.scoring import evaluate_area_criterion
    base = evaluate_area_criterion(c, 47.70, -122.30, PROV, [-122.42, 47.60, -122.27, 47.73])
    assert base.passed is False   # 1-minute bike threshold is impossible here
    c.threshold = 999
    reg = regrade(c, base)
    assert reg.passed is True     # same raw measurement, looser threshold
    assert reg.raw_value == base.raw_value


def test_build_isochrones():
    p = seattle_demo_profile()
    iso = build_isochrones(p, PROV, bands=[10, 20, 30])
    assert iso["bands"] == [10, 20, 30]
    assert iso["surfaces"]
    # the bike-commute criterion should produce a banded surface
    commute = next((s for s in iso["surfaces"] if "commute" in s["label"].lower()), None)
    assert commute is not None
    feats = commute["geojson"]["features"]
    assert feats
    for f in feats:
        assert f["properties"]["band"] in (10, 20, 30)
        assert f["properties"]["minutes"] <= 30
