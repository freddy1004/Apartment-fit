from app.analysis.geo import (
    Cell,
    generate_grid,
    group_contiguous,
    haversine_m,
    meters_to_miles,
    nearest,
)


def test_haversine_known_distance():
    # ~1 km north
    d = haversine_m(47.60, -122.33, 47.609, -122.33)
    assert 950 < d < 1050


def test_meters_to_miles():
    assert abs(meters_to_miles(1609.344) - 1.0) < 1e-6


def test_generate_grid_covers_bbox():
    bbox = [-122.42, 47.60, -122.27, 47.73]
    cells = generate_grid(bbox, 450)
    assert len(cells) > 100
    for c in cells:
        assert bbox[0] - 0.01 <= c.center_lon <= bbox[2] + 0.01
        assert bbox[1] - 0.01 <= c.center_lat <= bbox[3] + 0.01
        assert len(c.ring) == 5  # closed ring


def test_nearest_picks_closest():
    res = nearest(0, 0, [(0, 1), (0, 0.1), (1, 1)])
    assert res is not None
    assert abs(res[0]) < 1e-9 and abs(res[1] - 0.1) < 1e-9


def test_group_contiguous_splits_clusters():
    cells = [
        Cell(id="a", row=0, col=0, center_lat=0, center_lon=0),
        Cell(id="b", row=0, col=1, center_lat=0, center_lon=0),  # adjacent to a
        Cell(id="c", row=5, col=5, center_lat=0, center_lon=0),  # separate
    ]
    clusters = group_contiguous(cells)
    assert len(clusters) == 2
    assert len(clusters[0]) == 2  # largest first
    assert len(clusters[1]) == 1
