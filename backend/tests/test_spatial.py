from app.analysis.layers import crime_layer, noise_layer, seattle_layers
from app.analysis.scoring import evaluate_area_criterion
from app.analysis.spatial import (
    point_in_geometry,
    point_in_polygon,
    point_in_ring,
    sample_layer_value,
)
from app.criteria import builder as B
from app.criteria.schema import Comparator
from app.providers.registry import Providers

PROV = Providers("fixture")
BBOX = [-122.42, 47.60, -122.27, 47.73]
SQUARE = [[-122.35, 47.65], [-122.30, 47.65], [-122.30, 47.70], [-122.35, 47.70], [-122.35, 47.65]]


def test_point_in_ring():
    assert point_in_ring(-122.32, 47.67, SQUARE) is True
    assert point_in_ring(-122.40, 47.67, SQUARE) is False


def test_point_in_polygon_with_hole():
    outer = [[-122.40, 47.60], [-122.30, 47.60], [-122.30, 47.70], [-122.40, 47.70], [-122.40, 47.60]]
    hole = [[-122.37, 47.63], [-122.33, 47.63], [-122.33, 47.67], [-122.37, 47.67], [-122.37, 47.63]]
    assert point_in_polygon(-122.31, 47.61, [outer, hole]) is True   # inside outer, outside hole
    assert point_in_polygon(-122.35, 47.65, [outer, hole]) is False  # inside the hole


def test_point_in_geometry_multipolygon():
    poly1 = [SQUARE]
    poly2 = [[[-122.29, 47.60], [-122.28, 47.60], [-122.28, 47.61], [-122.29, 47.61], [-122.29, 47.60]]]
    multi = [poly1, poly2]
    assert point_in_geometry(-122.32, 47.67, multi) is True
    assert point_in_geometry(-122.285, 47.605, multi) is True
    assert point_in_geometry(-122.10, 47.10, multi) is False


def test_inclusion_zone_criterion():
    c = B.inclusion_zone(SQUARE, hard=True)
    inside = evaluate_area_criterion(c, 47.67, -122.32, PROV, BBOX)
    outside = evaluate_area_criterion(c, 47.61, -122.40, PROV, BBOX)
    assert inside.passed is True
    assert outside.passed is False


def test_exclusion_zone_criterion():
    c = B.exclusion_zone(SQUARE, hard=True)
    inside = evaluate_area_criterion(c, 47.67, -122.32, PROV, BBOX)
    assert inside.passed is False  # inside exclusion zone -> fails


def test_crime_layer_sampling():
    layer = crime_layer(BBOX)
    val, name = sample_layer_value(-122.33, 47.61, layer.features, "crime_index", 50.0)
    val_n, _ = sample_layer_value(-122.33, 47.72, layer.features, "crime_index", 50.0)
    assert val is not None and val_n is not None
    assert val > val_n  # south (near downtown) is higher index than far north


def test_layer_criterion_evaluation():
    layers = {l.id: l for l in seattle_layers(BBOX)}
    c = B.layer_threshold("crime", "crime_index", 55, "index", "safe proxy",
                          comparator=Comparator.LTE, hard=True)
    north = evaluate_area_criterion(c, 47.71, -122.33, PROV, BBOX, layers)
    assert north.raw_value is not None
    assert north.source == "layer:crime"


def test_terrain_criterion():
    c = B.terrain_max(8.0, hard=False)
    r = evaluate_area_criterion(c, 47.66, -122.33, PROV, BBOX)
    assert r.raw_value is not None
    assert 0 <= r.raw_value <= 60
    assert r.units == "percent"


def test_noise_layer_near_ramp_is_loud():
    layer = noise_layer()
    # I-5 @ NE 45th ramp coordinates from the fixture
    val, _ = sample_layer_value(-122.3235, 47.6610, layer.features, "noise_db", 48.0)
    assert val == 72.0
