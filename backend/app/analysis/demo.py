"""Seattle demo profile.

Encodes the demo's editable hard requirements *as data*, using generic criteria
templates -- no Seattle-specific logic leaks into the engine. Duplicating this
profile for another city only means changing the center, bbox, and destinations.
"""
from __future__ import annotations

import uuid

from ..criteria import builder as B
from ..criteria.schema import Comparator, Profile
from ..providers.fixture import load_fixture
from .layers import seattle_layers


def seattle_demo_profile() -> Profile:
    fx = load_fixture()
    ref = fx["downtown_reference"]
    bbox = fx["default_bbox"]
    return Profile(
        id="demo-seattle",
        name="Seattle — North of Downtown (Demo)",
        city="Seattle",
        center_lat=47.665,
        center_lon=-122.335,
        bbox=fx["default_bbox"],
        cell_size_m=450.0,
        criteria=[
            # Hard requirements (all editable in the UI):
            B.direction_boundary(reference_lat=ref["lat"],
                                 comparator=Comparator.NORTH_OF,
                                 reference_label=ref["label"], hard=True, weight=1.0),
            B.commute(destination_label=ref["label"], lat=ref["lat"], lon=ref["lon"],
                      minutes=30, mode=B.Mode.BIKE, hard=True, weight=2.0),
            B.groceries(miles=0.75, hard=True, weight=1.5),
            B.freeway_access(minutes=10, hard=True, weight=1.0),
            # Area preferences that shape the fit score but never gate:
            B.transit(minutes=10, hard=False, weight=1.0),
            B.parks(minutes=15, hard=False, weight=0.8),
            # Measurable proxies for otherwise-vague concepts, backed by layers:
            #   "safe"  -> reported-incident index below a threshold
            #   "quiet" -> modeled traffic noise below a threshold
            B.layer_threshold("crime", "crime_index", 55, "index",
                              "Reported-incident index <= 55 (proxy for 'safe')",
                              comparator=Comparator.LTE, hard=False, weight=1.2),
            B.layer_threshold("noise", "noise_db", 60, "dB",
                              "Traffic noise <= 60 dB (proxy for 'quiet')",
                              comparator=Comparator.LTE, hard=False, weight=0.8),
            B.terrain_max(8.0, hard=False, weight=0.4),
            # Listing preferences (soft): applied when a listing supplies the
            # field, neutral/excluded when it doesn't.
            B.rent_max(2200, hard=False, weight=1.5),
            B.min_bedrooms(1, hard=False, weight=0.5),
        ],
        layers=seattle_layers(bbox),
    )


def new_profile_from(template: Profile, name: str, city: str,
                     center_lat: float, center_lon: float,
                     bbox: list[float] | None = None) -> Profile:
    """Duplicate a profile for another city, keeping the criteria structure."""
    clone = template.model_copy(deep=True)
    clone.id = f"profile-{uuid.uuid4().hex[:8]}"
    clone.name = name
    clone.city = city
    clone.center_lat = center_lat
    clone.center_lon = center_lon
    clone.bbox = bbox or []
    # Re-issue criterion ids so the copy is independent.
    for c in clone.criteria:
        c.id = uuid.uuid4().hex[:12]
    return clone
