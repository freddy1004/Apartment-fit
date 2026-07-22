"""Tests for the real-Seattle-grounded crime / noise / terrain model."""
from app.data import seattle_real as R
from app.providers.registry import Providers

PROV = Providers("fixture")


def test_crime_higher_downtown_than_north_end():
    downtown = R.crime_index_at(47.605, -122.335)
    laurelhurst = R.crime_index_at(47.680, -122.278)
    assert downtown > laurelhurst
    assert 0 <= laurelhurst <= 100 and 0 <= downtown <= 100


def test_elevation_matches_known_hills():
    # Queen Anne Hill (~140 m) is much higher than the Fremont ship-canal (~10 m).
    qa = R.elevation_at(47.637, -122.357)
    fremont = R.elevation_at(47.651, -122.350)
    assert qa > 100
    assert fremont < 40
    assert qa > fremont


def test_noise_attenuates_with_distance_from_i5():
    on_i5 = R.noise_db_at(47.665, -122.3232)
    off_i5 = R.noise_db_at(47.665, -122.300)   # ~1.7 km east
    assert on_i5 > off_i5
    assert on_i5 >= 70          # right on the freeway
    assert off_i5 <= 60


def test_noise_floor_is_ambient():
    quiet = R.noise_db_at(47.685, -122.285)    # away from modeled arterials
    assert quiet >= R.AMBIENT_DB


def test_terrain_provider_uses_real_elevation():
    on_hill = PROV.terrain(47.637, -122.357)   # Queen Anne
    assert on_hill.elevation_m > 100
    assert on_hill.source == "seattle-idw-dem"
    assert on_hill.is_fallback is False
    assert on_hill.slope_pct >= 0
