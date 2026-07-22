"""Criteria domain model.

A *criterion* turns a vague preference ("close to work") into a measurable,
reproducible test ("bike commute <= 30 min to <address>"). Criteria come in two
scopes:

- ``area``    -> evaluated against a geographic unit (grid cell / block).
- ``listing`` -> evaluated against an individual apartment listing.

Every criterion is either a *hard* requirement (pass/fail gate) or a soft
*preference* (contributes a weighted 0..1 score). Strong preferences never
compensate for a failed hard requirement -- that rule lives in the scoring
engine, not here.
"""
from __future__ import annotations

import enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class Kind(str, enum.Enum):
    HARD = "hard"
    PREFERENCE = "preference"


class Scope(str, enum.Enum):
    AREA = "area"
    LISTING = "listing"


class Mode(str, enum.Enum):
    WALK = "walk"
    BIKE = "bike"
    DRIVE = "drive"
    TRANSIT = "transit"
    NONE = "none"  # non-travel criteria (rent, direction, boolean amenity, ...)


class Method(str, enum.Enum):
    """How the raw measurement is produced."""
    ROUTE = "route"              # real network travel time/distance to a destination
    STRAIGHT_LINE = "straight_line"  # geodesic distance fallback (clearly labeled)
    DIRECTION = "direction"      # e.g. "north of reference point"
    POI_DISTANCE = "poi_distance"  # nearest qualifying amenity
    NUMERIC = "numeric"          # a numeric listing field (rent, sqft, ...)
    BOOLEAN = "boolean"          # a yes/no listing field (parking, pets, ...)
    COUNT = "count"              # count of amenities within a radius


class Comparator(str, enum.Enum):
    LTE = "lte"   # measured <= threshold  (travel time, rent, distance)
    GTE = "gte"   # measured >= threshold  (bedrooms, sqft)
    EQ = "eq"
    TRUE = "true"  # boolean must be true
    NORTH_OF = "north_of"
    SOUTH_OF = "south_of"


class MissingDataBehavior(str, enum.Enum):
    FAIL = "fail"          # treat missing as a hard failure
    PASS = "pass"          # treat missing as satisfied
    NEUTRAL = "neutral"    # exclude from score, mark low confidence
    PENALIZE = "penalize"  # worst-case preference score


class CriterionType(str, enum.Enum):
    # area
    COMMUTE = "commute"
    GROCERIES = "groceries"
    TRANSIT = "transit"
    PARKS = "parks"
    FREEWAY_ACCESS = "freeway_access"
    AMENITIES = "amenities"
    TERRAIN = "terrain"
    BOUNDARY = "boundary"          # user-drawn inclusion/exclusion or direction
    GEOSPATIAL = "geospatial"      # imported geojson layer membership
    # listing
    RENT = "rent"
    FEES = "fees"
    BEDROOMS = "bedrooms"
    BATHROOMS = "bathrooms"
    SIZE = "size"
    PARKING = "parking"
    LAUNDRY = "laundry"
    PETS = "pets"
    LEASE_LENGTH = "lease_length"
    LISTING_AMENITIES = "listing_amenities"


class Destination(BaseModel):
    """A target location or amenity class the criterion measures against."""
    label: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    amenity_type: Optional[str] = None  # e.g. "supermarket", "park", "freeway_ramp"


class Criterion(BaseModel):
    id: str
    type: CriterionType
    scope: Scope
    kind: Kind
    label: str = ""

    threshold: Optional[float] = None
    units: str = ""
    comparator: Comparator = Comparator.LTE
    weight: float = 1.0
    mode: Mode = Mode.NONE
    method: Method = Method.NUMERIC
    destination: Optional[Destination] = None
    # For preference falloff: score decays to 0 by threshold * tolerance.
    tolerance: float = 1.5
    missing_data: MissingDataBehavior = MissingDataBehavior.NEUTRAL
    enabled: bool = True

    @field_validator("weight")
    @classmethod
    def _weight_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("weight must be >= 0")
        return v


class Profile(BaseModel):
    """A named, savable set of criteria plus city context."""
    id: str
    name: str
    city: str
    center_lat: float
    center_lon: float
    # Analysis bounding box + grid resolution (meters per cell).
    bbox: list[float] = Field(default_factory=list)  # [min_lon,min_lat,max_lon,max_lat]
    cell_size_m: float = 400.0
    criteria: list[Criterion] = Field(default_factory=list)

    def area_criteria(self) -> list[Criterion]:
        return [c for c in self.criteria if c.scope == Scope.AREA and c.enabled]

    def listing_criteria(self) -> list[Criterion]:
        return [c for c in self.criteria if c.scope == Scope.LISTING and c.enabled]
