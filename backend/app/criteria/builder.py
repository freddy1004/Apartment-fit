"""Interactive criteria builder.

Turns vague preferences into measurable :class:`Criterion` objects and flags
ambiguous concepts ("safe", "quiet", "walkable") that cannot be measured
directly, offering concrete measurable alternatives instead.

The builder is intentionally deterministic and rule-based so it is testable and
runs with no external services. It is the backend for the frontend's
"criteria builder" workflow.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from .schema import (
    Comparator,
    Criterion,
    CriterionType,
    Destination,
    Kind,
    Method,
    MissingDataBehavior,
    Mode,
    Scope,
)


@dataclass
class AmbiguityFlag:
    term: str
    reason: str
    suggestions: list[dict] = field(default_factory=list)


# Concepts that are not directly measurable. Each maps to measurable proxies the
# user can pick from.
AMBIGUOUS_TERMS: dict[str, AmbiguityFlag] = {
    "safe": AmbiguityFlag(
        term="safe",
        reason="'Safe' is subjective and not directly measurable. Choose a measurable proxy.",
        suggestions=[
            {"label": "Reported crime rate below a threshold (imported geospatial layer)",
             "type": CriterionType.GEOSPATIAL.value},
            {"label": "Well-lit / distance to nearest police or fire station",
             "type": CriterionType.AMENITIES.value},
        ],
    ),
    "quiet": AmbiguityFlag(
        term="quiet",
        reason="'Quiet' is subjective. Pick a measurable proxy for noise.",
        suggestions=[
            {"label": "Minimum distance from freeways / arterials (straight-line buffer)",
             "type": CriterionType.BOUNDARY.value},
            {"label": "Imported noise-contour geospatial layer threshold",
             "type": CriterionType.GEOSPATIAL.value},
        ],
    ),
    "walkable": AmbiguityFlag(
        term="walkable",
        reason="'Walkable' means different things. Decompose into measurable walk criteria.",
        suggestions=[
            {"label": "Walk <= 0.75 mi to a full-service grocery store",
             "type": CriterionType.GROCERIES.value},
            {"label": "Count of amenities (cafe, pharmacy, restaurant) within a 15-min walk",
             "type": CriterionType.AMENITIES.value},
        ],
    ),
    "convenient": AmbiguityFlag(
        term="convenient",
        reason="'Convenient' is vague. Specify what needs to be near and how near.",
        suggestions=[
            {"label": "Transit stop within an X-minute walk", "type": CriterionType.TRANSIT.value},
            {"label": "Grocery within an X-minute walk", "type": CriterionType.GROCERIES.value},
        ],
    ),
    "nice": AmbiguityFlag(
        term="nice",
        reason="'Nice' is not measurable. Choose concrete amenities or area attributes.",
        suggestions=[
            {"label": "Park within an X-minute walk", "type": CriterionType.PARKS.value},
        ],
    ),
}


def flag_ambiguities(text: str) -> list[AmbiguityFlag]:
    """Return ambiguity flags for any vague terms present in ``text``."""
    lowered = text.lower()
    return [flag for term, flag in AMBIGUOUS_TERMS.items() if term in lowered]


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---- Templates: map an intent to a fully-formed measurable criterion. --------

def commute(
    destination_label: str,
    lat: float,
    lon: float,
    minutes: float = 30,
    mode: Mode = Mode.BIKE,
    hard: bool = True,
    weight: float = 1.0,
) -> Criterion:
    return Criterion(
        id=_new_id(),
        type=CriterionType.COMMUTE,
        scope=Scope.AREA,
        kind=Kind.HARD if hard else Kind.PREFERENCE,
        label=f"{mode.value.title()} commute <= {minutes} min to {destination_label}",
        threshold=minutes,
        units="minutes",
        comparator=Comparator.LTE,
        weight=weight,
        mode=mode,
        method=Method.ROUTE,
        destination=Destination(label=destination_label, lat=lat, lon=lon),
        missing_data=MissingDataBehavior.FAIL if hard else MissingDataBehavior.NEUTRAL,
    )


def groceries(
    miles: float = 0.75, hard: bool = True, weight: float = 1.0,
    amenity_type: str = "supermarket",
) -> Criterion:
    return Criterion(
        id=_new_id(),
        type=CriterionType.GROCERIES,
        scope=Scope.AREA,
        kind=Kind.HARD if hard else Kind.PREFERENCE,
        label=f"Walk <= {miles} mi to a full-service grocery store",
        threshold=miles,
        units="miles",
        comparator=Comparator.LTE,
        weight=weight,
        mode=Mode.WALK,
        method=Method.POI_DISTANCE,
        destination=Destination(label="grocery store", amenity_type=amenity_type),
        missing_data=MissingDataBehavior.FAIL if hard else MissingDataBehavior.NEUTRAL,
    )


def freeway_access(
    minutes: float = 10, hard: bool = True, weight: float = 1.0,
    amenity_type: str = "freeway_ramp",
) -> Criterion:
    return Criterion(
        id=_new_id(),
        type=CriterionType.FREEWAY_ACCESS,
        scope=Scope.AREA,
        kind=Kind.HARD if hard else Kind.PREFERENCE,
        label=f"Drive <= {minutes} min to a freeway entrance",
        threshold=minutes,
        units="minutes",
        comparator=Comparator.LTE,
        weight=weight,
        mode=Mode.DRIVE,
        method=Method.ROUTE,
        destination=Destination(label="freeway entrance", amenity_type=amenity_type),
        missing_data=MissingDataBehavior.FAIL if hard else MissingDataBehavior.NEUTRAL,
    )


def direction_boundary(
    reference_lat: float,
    comparator: Comparator = Comparator.NORTH_OF,
    reference_label: str = "downtown reference point",
    hard: bool = True,
    weight: float = 1.0,
) -> Criterion:
    return Criterion(
        id=_new_id(),
        type=CriterionType.BOUNDARY,
        scope=Scope.AREA,
        kind=Kind.HARD if hard else Kind.PREFERENCE,
        label=f"Located {comparator.value.replace('_', ' ')} {reference_label}",
        threshold=reference_lat,
        units="latitude",
        comparator=comparator,
        weight=weight,
        mode=Mode.NONE,
        method=Method.DIRECTION,
        destination=Destination(label=reference_label, lat=reference_lat),
        missing_data=MissingDataBehavior.FAIL,
    )


def inclusion_zone(geometry: list, label: str = "inside drawn area",
                   hard: bool = True, weight: float = 1.0) -> Criterion:
    """User-drawn area the location must be *inside* of."""
    return Criterion(
        id=_new_id(), type=CriterionType.BOUNDARY, scope=Scope.AREA,
        kind=Kind.HARD if hard else Kind.PREFERENCE, label=label,
        comparator=Comparator.WITHIN, weight=weight, method=Method.POLYGON,
        units="zone", geometry=geometry, missing_data=MissingDataBehavior.FAIL,
    )


def exclusion_zone(geometry: list, label: str = "outside drawn area",
                   hard: bool = True, weight: float = 1.0) -> Criterion:
    """User-drawn area the location must be *outside* of (e.g. flood zone)."""
    return Criterion(
        id=_new_id(), type=CriterionType.BOUNDARY, scope=Scope.AREA,
        kind=Kind.HARD if hard else Kind.PREFERENCE, label=label,
        comparator=Comparator.OUTSIDE, weight=weight, method=Method.POLYGON,
        units="zone", geometry=geometry, missing_data=MissingDataBehavior.FAIL,
    )


def layer_threshold(layer_id: str, layer_property: str, threshold: float,
                    units: str, label: str, comparator: Comparator = Comparator.LTE,
                    hard: bool = False, weight: float = 1.0) -> Criterion:
    """Compare a value sampled from an imported geospatial layer (crime, noise…)."""
    return Criterion(
        id=_new_id(), type=CriterionType.GEOSPATIAL, scope=Scope.AREA,
        kind=Kind.HARD if hard else Kind.PREFERENCE, label=label,
        threshold=threshold, units=units, comparator=comparator, weight=weight,
        method=Method.LAYER_VALUE, layer_id=layer_id, layer_property=layer_property,
        missing_data=MissingDataBehavior.NEUTRAL,
    )


def terrain_max(slope_pct: float = 8.0, hard: bool = False, weight: float = 1.0) -> Criterion:
    return Criterion(
        id=_new_id(), type=CriterionType.TERRAIN, scope=Scope.AREA,
        kind=Kind.HARD if hard else Kind.PREFERENCE,
        label=f"Local slope <= {slope_pct:g}%", threshold=slope_pct, units="percent",
        comparator=Comparator.LTE, weight=weight, method=Method.TERRAIN,
        missing_data=MissingDataBehavior.NEUTRAL,
    )


def transit(minutes: float = 10, hard: bool = False, weight: float = 1.0) -> Criterion:
    """Option 1: nearest *major transit station* (light rail / transit center)."""
    return Criterion(
        id=_new_id(),
        type=CriterionType.TRANSIT,
        scope=Scope.AREA,
        kind=Kind.HARD if hard else Kind.PREFERENCE,
        label=f"Walk <= {minutes} min to a major transit station",
        threshold=minutes,
        units="minutes",
        comparator=Comparator.LTE,
        weight=weight,
        mode=Mode.WALK,
        method=Method.POI_DISTANCE,
        destination=Destination(label="major transit station", amenity_type="transit_stop"),
        missing_data=MissingDataBehavior.NEUTRAL,
    )


def transit_any(minutes: float = 10, hard: bool = False, weight: float = 1.0) -> Criterion:
    """Option 2: nearest transit stop of *any* kind, including ordinary bus stops."""
    return Criterion(
        id=_new_id(),
        type=CriterionType.TRANSIT,
        scope=Scope.AREA,
        kind=Kind.HARD if hard else Kind.PREFERENCE,
        label=f"Walk <= {minutes} min to any transit stop (incl. bus)",
        threshold=minutes,
        units="minutes",
        comparator=Comparator.LTE,
        weight=weight,
        mode=Mode.WALK,
        method=Method.POI_DISTANCE,
        destination=Destination(label="transit stop (incl. bus)", amenity_type="transit_any"),
        missing_data=MissingDataBehavior.NEUTRAL,
    )


def parks(minutes: float = 15, hard: bool = False, weight: float = 1.0) -> Criterion:
    return Criterion(
        id=_new_id(),
        type=CriterionType.PARKS,
        scope=Scope.AREA,
        kind=Kind.HARD if hard else Kind.PREFERENCE,
        label=f"Walk <= {minutes} min to a park",
        threshold=minutes,
        units="minutes",
        comparator=Comparator.LTE,
        weight=weight,
        mode=Mode.WALK,
        method=Method.POI_DISTANCE,
        destination=Destination(label="park", amenity_type="park"),
        missing_data=MissingDataBehavior.NEUTRAL,
    )


# ---- Listing criteria templates ---------------------------------------------

def rent_max(amount: float, hard: bool = True, weight: float = 1.0) -> Criterion:
    return Criterion(
        id=_new_id(), type=CriterionType.RENT, scope=Scope.LISTING,
        kind=Kind.HARD if hard else Kind.PREFERENCE,
        label=f"Rent <= ${amount:.0f}/mo", threshold=amount, units="usd_per_month",
        comparator=Comparator.LTE, weight=weight, method=Method.NUMERIC,
        missing_data=MissingDataBehavior.FAIL if hard else MissingDataBehavior.NEUTRAL,
    )


def min_bedrooms(n: float, hard: bool = True, weight: float = 1.0) -> Criterion:
    return Criterion(
        id=_new_id(), type=CriterionType.BEDROOMS, scope=Scope.LISTING,
        kind=Kind.HARD if hard else Kind.PREFERENCE,
        label=f"Bedrooms >= {n:g}", threshold=n, units="rooms",
        comparator=Comparator.GTE, weight=weight, method=Method.NUMERIC,
        missing_data=MissingDataBehavior.FAIL if hard else MissingDataBehavior.NEUTRAL,
    )


def min_bathrooms(n: float, hard: bool = False, weight: float = 1.0) -> Criterion:
    return Criterion(
        id=_new_id(), type=CriterionType.BATHROOMS, scope=Scope.LISTING,
        kind=Kind.HARD if hard else Kind.PREFERENCE,
        label=f"Bathrooms >= {n:g}", threshold=n, units="rooms",
        comparator=Comparator.GTE, weight=weight, method=Method.NUMERIC,
        missing_data=MissingDataBehavior.NEUTRAL,
    )


def min_size(sqft: float, hard: bool = False, weight: float = 1.0) -> Criterion:
    return Criterion(
        id=_new_id(), type=CriterionType.SIZE, scope=Scope.LISTING,
        kind=Kind.HARD if hard else Kind.PREFERENCE,
        label=f"Size >= {sqft:g} sqft", threshold=sqft, units="sqft",
        comparator=Comparator.GTE, weight=weight, method=Method.NUMERIC,
        missing_data=MissingDataBehavior.NEUTRAL,
    )


def boolean_feature(
    ctype: CriterionType, label: str, hard: bool = False, weight: float = 1.0,
) -> Criterion:
    return Criterion(
        id=_new_id(), type=ctype, scope=Scope.LISTING,
        kind=Kind.HARD if hard else Kind.PREFERENCE,
        label=label, comparator=Comparator.TRUE, weight=weight, method=Method.BOOLEAN,
        units="bool",
        missing_data=MissingDataBehavior.NEUTRAL,
    )
