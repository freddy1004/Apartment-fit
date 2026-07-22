from app.analysis.demo import seattle_demo_profile
from app.analysis.engine import run_city_analysis
from app.analysis.precompute import warm_routes
from app.providers.registry import Providers


def test_warm_routes_populates_cache():
    p = seattle_demo_profile()
    prov = Providers("fixture")
    assert len(prov._route_cache) == 0
    stats = warm_routes(p, prov)
    assert stats["route_calls"] > 0
    assert stats["cached_routes"] > 0
    assert len(prov._route_cache) == stats["cached_routes"]


def test_reruns_reuse_cached_routes_incrementally():
    """Editing a threshold must not recompute routes -- the cache is reused."""
    p = seattle_demo_profile()
    prov = Providers("fixture")
    run_city_analysis(p, prov)
    after_first = len(prov._route_cache)
    assert after_first > 0

    # Change a threshold (grading changes, measurements do not) and re-run.
    for c in p.criteria:
        if c.type.value == "commute":
            c.threshold = 45
    run_city_analysis(p, prov)
    after_second = len(prov._route_cache)
    # No new route keys: every route was served from cache.
    assert after_second == after_first


def test_precompute_makes_analysis_consistent():
    p = seattle_demo_profile()
    prov = Providers("fixture")
    warm_routes(p, prov)
    warm_count = len(prov._route_cache)
    r = run_city_analysis(p, prov)
    # Analysis reused warmed routes rather than adding many new ones.
    assert len(prov._route_cache) == warm_count
    assert len(r.cells) > 0
