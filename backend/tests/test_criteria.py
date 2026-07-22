from app.criteria import builder as B
from app.criteria.schema import Comparator, Kind, Mode, Scope


def test_flag_ambiguities():
    flags = B.flag_ambiguities("I want a safe and quiet but walkable place")
    terms = {f.term for f in flags}
    assert {"safe", "quiet", "walkable"} <= terms
    for f in flags:
        assert f.suggestions  # each offers measurable alternatives


def test_no_false_ambiguity():
    flags = B.flag_ambiguities("bike commute under 30 minutes to downtown")
    assert flags == []


def test_commute_template():
    c = B.commute("Downtown", 47.60, -122.33, minutes=30, mode=Mode.BIKE, hard=True)
    assert c.scope == Scope.AREA
    assert c.kind == Kind.HARD
    assert c.mode == Mode.BIKE
    assert c.threshold == 30
    assert c.comparator == Comparator.LTE
    assert c.destination.lat == 47.60


def test_groceries_template_units_miles():
    c = B.groceries(miles=0.75)
    assert c.units == "miles"
    assert c.destination.amenity_type == "supermarket"


def test_direction_boundary():
    c = B.direction_boundary(reference_lat=47.61, comparator=Comparator.NORTH_OF)
    assert c.comparator == Comparator.NORTH_OF
    assert c.threshold == 47.61


def test_listing_templates():
    assert B.rent_max(2000).comparator == Comparator.LTE
    assert B.min_bedrooms(2).comparator == Comparator.GTE
    assert B.boolean_feature(B.CriterionType.PARKING, "Parking").comparator == Comparator.TRUE
