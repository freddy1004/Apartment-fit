from app.criteria import builder as B
from app.criteria.schema import Comparator, MissingDataBehavior
from app.analysis.scoring import (
    Tier,
    aggregate,
    evaluate_area_criterion,
    evaluate_listing_criterion,
)
from app.providers.registry import Providers

PROV = Providers("fixture")
BBOX = [-122.42, 47.60, -122.27, 47.73]


def test_preference_never_compensates_failed_hard():
    # A cell far south fails the north-of hard requirement.
    hard = B.direction_boundary(reference_lat=47.61, comparator=Comparator.NORTH_OF)
    pref = B.parks(minutes=60, hard=False, weight=5.0)  # very lax, will score high
    results = [
        evaluate_area_criterion(hard, 47.50, -122.33, PROV, BBOX),  # south -> fail
        evaluate_area_criterion(pref, 47.50, -122.33, PROV, BBOX),
    ]
    score = aggregate(results)
    assert score.hard_passed is False
    assert score.tier == Tier.INELIGIBLE
    assert score.fit_score == 0.0  # preference cannot rescue it


def test_hard_pass_produces_score():
    hard = B.direction_boundary(reference_lat=47.61, comparator=Comparator.NORTH_OF)
    results = [evaluate_area_criterion(hard, 47.66, -122.33, PROV, BBOX)]
    score = aggregate(results)
    assert score.hard_passed is True
    assert score.tier != Tier.INELIGIBLE


def test_lte_preference_normalization():
    c = B.commute("dt", 47.62, -122.33, minutes=30, mode=B.Mode.BIKE, hard=False)
    c.tolerance = 2.0
    # At the reference point itself the ride is ~0 min -> full score.
    r = evaluate_area_criterion(c, 47.62, -122.33, PROV, BBOX)
    assert r.preference_score == 1.0


def test_missing_data_fail_behavior():
    c = B.groceries(miles=0.75, hard=True)
    c.destination.amenity_type = "does_not_exist"
    c.missing_data = MissingDataBehavior.FAIL
    r = evaluate_area_criterion(c, 47.66, -122.33, PROV, BBOX)
    assert r.missing is True
    assert r.passed is False


def test_missing_data_neutral_excluded_from_score():
    c = B.parks(minutes=10, hard=False)
    c.destination.amenity_type = "nope"
    c.missing_data = MissingDataBehavior.NEUTRAL
    r = evaluate_area_criterion(c, 47.66, -122.33, PROV, BBOX)
    assert r.missing is True
    assert r.preference_score is None  # excluded


def test_listing_hard_rent_gate():
    c = B.rent_max(2000, hard=True)
    ok = evaluate_listing_criterion(c, {"rent": 1800})
    bad = evaluate_listing_criterion(c, {"rent": 2500})
    assert ok.passed is True
    assert bad.passed is False


def test_listing_boolean_pets():
    c = B.boolean_feature(B.CriterionType.PETS, "Pets allowed", hard=True)
    assert evaluate_listing_criterion(c, {"pets": True}).passed is True
    assert evaluate_listing_criterion(c, {"pets": False}).passed is False


def test_insufficient_data_tier():
    # All criteria missing with neutral -> coverage 0 -> insufficient_data.
    c1 = B.parks(minutes=10, hard=False)
    c1.destination.amenity_type = "nope"
    c2 = B.transit(minutes=10, hard=False)
    c2.destination.amenity_type = "nope"
    results = [
        evaluate_area_criterion(c1, 47.66, -122.33, PROV, BBOX),
        evaluate_area_criterion(c2, 47.66, -122.33, PROV, BBOX),
    ]
    score = aggregate(results)
    assert score.tier == Tier.INSUFFICIENT_DATA
