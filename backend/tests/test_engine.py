from app.analysis.demo import new_profile_from, seattle_demo_profile
from app.analysis.engine import run_city_analysis, score_listing
from app.analysis.scoring import Tier
from app.providers.registry import Providers

PROV = Providers("fixture")


def test_city_analysis_runs_and_produces_tiers():
    profile = seattle_demo_profile()
    result = run_city_analysis(profile, PROV)
    assert len(result.cells) > 50
    # Some cells qualify, some are ineligible (north-of + commute gates bite).
    assert result.tier_counts.get(Tier.INELIGIBLE, 0) > 0
    qualifying = sum(result.tier_counts.get(t, 0)
                     for t in (Tier.STRONG_FIT, Tier.QUALIFYING, Tier.BORDERLINE))
    assert qualifying > 0


def test_south_cells_are_ineligible():
    profile = seattle_demo_profile()
    result = run_city_analysis(profile, PROV)
    ref_lat = 47.6062
    for cr in result.cells:
        if cr.cell.center_lat < ref_lat - 0.01:
            # south of downtown must fail the north-of hard requirement
            assert cr.score.hard_passed is False


def test_elimination_ranking_present():
    profile = seattle_demo_profile()
    result = run_city_analysis(profile, PROV)
    assert result.elimination
    # sorted descending by eliminated count
    counts = [e["eliminated"] for e in result.elimination]
    assert counts == sorted(counts, reverse=True)


def test_zones_have_neighborhoods():
    profile = seattle_demo_profile()
    result = run_city_analysis(profile, PROV)
    assert result.zones
    for z in result.zones:
        assert "nearby_neighborhoods" in z
        assert z["cell_count"] >= 1


def test_listing_scoring_combined_gate():
    profile = seattle_demo_profile()
    analysis = run_city_analysis(profile, PROV)
    # A north-Seattle listing near Green Lake with good listing fields.
    good = {"id": "L1", "address": "Green Lake", "lat": 47.6806, "lon": -122.3286,
            "rent": 1800, "bedrooms": 2}
    sc = score_listing(profile, good, PROV, analysis)
    assert sc.area.hard_passed in (True, False)  # computed
    assert 0 <= sc.combined_fit <= 100

    # A south listing fails the north-of gate -> ineligible combined.
    south = {"id": "L2", "address": "SoDo", "lat": 47.57, "lon": -122.33, "rent": 1500}
    sc2 = score_listing(profile, south, PROV, analysis)
    assert sc2.area.hard_passed is False
    assert sc2.combined_tier == Tier.INELIGIBLE
    assert sc2.combined_fit == 0.0


def test_duplicate_profile_independent():
    profile = seattle_demo_profile()
    clone = new_profile_from(profile, "Portland test", "Portland", 45.52, -122.68,
                             [-122.75, 45.48, -122.6, 45.58])
    assert clone.id != profile.id
    assert clone.city == "Portland"
    assert {c.id for c in clone.criteria}.isdisjoint({c.id for c in profile.criteria})
    # Runs for another city without Seattle-specific hard-coding.
    result = run_city_analysis(clone, PROV)
    assert len(result.cells) > 10
