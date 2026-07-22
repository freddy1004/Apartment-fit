"""Scoring engine.

Evaluates area and listing criteria into raw measurements, hard pass/fail, and
weighted preference scores, then combines them into a 0..100 fit score and a
tier. The central rule: **a failed hard requirement makes a unit ineligible no
matter how strong its preferences** -- preferences can never compensate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..criteria.schema import (
    Comparator,
    Criterion,
    Kind,
    Method,
    MissingDataBehavior,
    Mode,
)
from ..providers.registry import Providers
from .geo import haversine_m, meters_to_miles
from .spatial import point_in_geometry, sample_layer_value

# Tier thresholds on the 0..100 preference score (only for hard-passing units).
STRONG_FIT = 80.0
QUALIFYING = 55.0
# If the fraction of criteria with usable data is below this, the unit is
# reported as insufficient-data rather than scored with false confidence.
MIN_DATA_COVERAGE = 0.5


class Tier:
    STRONG_FIT = "strong_fit"
    QUALIFYING = "qualifying"
    BORDERLINE = "borderline"
    INELIGIBLE = "ineligible"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class CriterionResult:
    criterion_id: str
    label: str
    kind: str
    passed: bool                 # hard gate result (True for preferences that don't gate)
    preference_score: Optional[float]  # 0..1, None if excluded from scoring
    raw_value: Optional[float]
    units: str
    threshold: Optional[float]
    weight: float
    confidence: float
    source: str
    is_fallback: bool
    missing: bool
    explanation: str
    detail: dict = field(default_factory=dict)


@dataclass
class UnitScore:
    hard_passed: bool
    fit_score: float             # 0..100
    tier: str
    confidence: float
    results: list[CriterionResult]

    def failed_hard(self) -> list[CriterionResult]:
        return [r for r in self.results if r.kind == Kind.HARD.value and not r.passed]

    def to_dict(self) -> dict:
        return {
            "hard_passed": self.hard_passed,
            "fit_score": round(self.fit_score, 1),
            "tier": self.tier,
            "confidence": round(self.confidence, 2),
            "results": [r.__dict__ for r in self.results],
        }


# --------------------------------------------------------------------------- #
#  Preference normalization
# --------------------------------------------------------------------------- #

def _pref_score(c: Criterion, measured: float) -> float:
    """Map a raw measurement to a 0..1 preference score using threshold + tolerance."""
    t = c.threshold
    if t is None:
        return 0.0
    span = max(1e-9, t * (c.tolerance - 1.0))
    if c.comparator == Comparator.LTE:
        if measured <= t:
            return 1.0
        return max(0.0, 1.0 - (measured - t) / span)
    if c.comparator == Comparator.GTE:
        if measured >= t:
            return 1.0
        return max(0.0, 1.0 - (t - measured) / span)
    if c.comparator == Comparator.EQ:
        return 1.0 if abs(measured - t) < 1e-9 else 0.0
    if c.comparator in (Comparator.NORTH_OF, Comparator.SOUTH_OF):
        return 1.0 if _direction_ok(c, measured) else 0.0
    return 0.0


def _hard_ok(c: Criterion, measured: float) -> bool:
    t = c.threshold
    if t is None:
        return True
    if c.comparator == Comparator.LTE:
        return measured <= t
    if c.comparator == Comparator.GTE:
        return measured >= t
    if c.comparator == Comparator.EQ:
        return abs(measured - t) < 1e-9
    if c.comparator in (Comparator.NORTH_OF, Comparator.SOUTH_OF):
        return _direction_ok(c, measured)
    return True


def _direction_ok(c: Criterion, lat: float) -> bool:
    if c.comparator == Comparator.NORTH_OF:
        return lat >= (c.threshold or 0)
    if c.comparator == Comparator.SOUTH_OF:
        return lat <= (c.threshold or 0)
    return True


def _missing_result(c: Criterion, reason: str) -> CriterionResult:
    """Build a result for a criterion whose measurement could not be produced."""
    b = c.missing_data
    if b == MissingDataBehavior.FAIL:
        passed, pref = (c.kind != Kind.HARD), None
        # hard fails; preference contributes worst score
        if c.kind == Kind.HARD:
            passed = False
        else:
            pref = 0.0
    elif b == MissingDataBehavior.PASS:
        passed, pref = True, (1.0 if c.kind == Kind.PREFERENCE else None)
    elif b == MissingDataBehavior.PENALIZE:
        passed = c.kind != Kind.HARD
        pref = 0.0 if c.kind == Kind.PREFERENCE else None
        if c.kind == Kind.HARD:
            passed = False
    else:  # NEUTRAL -> excluded, never gates
        passed, pref = True, None
    return CriterionResult(
        criterion_id=c.id, label=c.label, kind=c.kind.value, passed=passed,
        preference_score=pref, raw_value=None, units=c.units, threshold=c.threshold,
        weight=c.weight, confidence=0.1, source="none", is_fallback=True,
        missing=True, explanation=f"Missing data ({reason}); applied '{b.value}' policy.",
    )


# --------------------------------------------------------------------------- #
#  Area criteria
# --------------------------------------------------------------------------- #

def _boolean_result(c: Criterion, ok: bool, raw: float, confidence: float,
                    source: str, explanation: str, fallback: bool = False,
                    detail: Optional[dict] = None) -> CriterionResult:
    passed = ok if c.kind == Kind.HARD else True
    pref = (1.0 if ok else 0.0) if c.kind == Kind.PREFERENCE else None
    return CriterionResult(
        criterion_id=c.id, label=c.label, kind=c.kind.value, passed=passed,
        preference_score=pref, raw_value=raw, units=c.units, threshold=c.threshold,
        weight=c.weight, confidence=confidence, source=source, is_fallback=fallback,
        missing=False, explanation=explanation, detail=detail or {},
    )


def _evaluate_polygon(c: Criterion, lat: float, lon: float) -> CriterionResult:
    """User-drawn inclusion/exclusion zone (BOUNDARY criterion)."""
    if not c.geometry:
        return _missing_result(c, "no geometry drawn")
    inside = point_in_geometry(lon, lat, c.geometry)
    want_inside = c.comparator != Comparator.OUTSIDE  # WITHIN by default
    ok = inside if want_inside else (not inside)
    zone = "inclusion" if want_inside else "exclusion"
    return _boolean_result(
        c, ok, 1.0 if inside else 0.0, 1.0, "geometry",
        f"Point is {'inside' if inside else 'outside'} the {zone} zone "
        f"({'passes' if ok else 'fails'}).",
    )


def _evaluate_layer(c: Criterion, lat: float, lon: float, layers: dict) -> CriterionResult:
    """Sample a numeric value from an imported geospatial layer and compare it."""
    layer = layers.get(c.layer_id) if c.layer_id else None
    if not layer:
        return _missing_result(c, f"layer '{c.layer_id}' not found")
    prop = c.layer_property or layer.value_property
    value, feat_name = sample_layer_value(
        lon, lat, layer.features, prop, layer.default_value)
    if value is None:
        return _missing_result(c, f"no '{prop}' value at this location")
    passed = _hard_ok(c, value) if c.kind == Kind.HARD else True
    pref = _pref_score(c, value) if c.kind == Kind.PREFERENCE else None
    verb = "meets" if _hard_ok(c, value) else "exceeds"
    return CriterionResult(
        criterion_id=c.id, label=c.label, kind=c.kind.value, passed=passed,
        preference_score=pref, raw_value=round(value, 3), units=c.units,
        threshold=c.threshold, weight=c.weight, confidence=0.7,
        source=f"layer:{layer.id}", is_fallback=False, missing=False,
        explanation=f"{layer.name} {prop}={value:g} {verb} threshold {c.threshold} "
                    f"({c.comparator.value}){f' at {feat_name}' if feat_name else ''}.",
        detail={"layer": layer.id, "feature": feat_name},
    )


def _evaluate_terrain(c: Criterion, lat: float, lon: float,
                      providers: Providers) -> CriterionResult:
    t = providers.terrain(lat, lon)
    measured = t.slope_pct
    passed = _hard_ok(c, measured) if c.kind == Kind.HARD else True
    pref = _pref_score(c, measured) if c.kind == Kind.PREFERENCE else None
    verb = "within" if _hard_ok(c, measured) else "exceeds"
    return CriterionResult(
        criterion_id=c.id, label=c.label, kind=c.kind.value, passed=passed,
        preference_score=pref, raw_value=round(measured, 2), units=c.units or "percent",
        threshold=c.threshold, weight=c.weight, confidence=t.confidence,
        source=t.source, is_fallback=t.is_fallback, missing=False,
        explanation=f"Local slope {measured:.1f}% {verb} threshold {c.threshold}% "
                    f"(elevation {t.elevation_m:.0f} m).",
        detail={"elevation_m": round(t.elevation_m, 1)},
    )


def evaluate_area_criterion(
    c: Criterion, lat: float, lon: float, providers: Providers, bbox: list[float],
    layers: Optional[dict] = None,
) -> CriterionResult:
    if c.method == Method.POLYGON:
        return _evaluate_polygon(c, lat, lon)
    if c.method == Method.LAYER_VALUE:
        return _evaluate_layer(c, lat, lon, layers or {})
    if c.method == Method.TERRAIN:
        return _evaluate_terrain(c, lat, lon, providers)

    if c.method == Method.DIRECTION:
        measured = lat
        passed = _hard_ok(c, measured) if c.kind == Kind.HARD else True
        pref = _pref_score(c, measured) if c.kind == Kind.PREFERENCE else None
        ok = _direction_ok(c, measured)
        return CriterionResult(
            criterion_id=c.id, label=c.label, kind=c.kind.value, passed=passed,
            preference_score=pref, raw_value=round(measured, 5), units=c.units,
            threshold=c.threshold, weight=c.weight, confidence=1.0,
            source="geometry", is_fallback=False, missing=False,
            explanation=("Passes" if ok else "Fails") + f" direction test ({c.comparator.value}).",
        )

    # Resolve a destination point.
    dest_lat = dest_lon = None
    dest_name = ""
    if c.destination and c.destination.lat is not None:
        dest_lat, dest_lon = c.destination.lat, c.destination.lon
        dest_name = c.destination.label
    elif c.destination and c.destination.amenity_type:
        pois = providers.find_pois(c.destination.amenity_type, bbox)
        if not pois:
            return _missing_result(c, f"no '{c.destination.amenity_type}' found")
        # nearest by straight-line first
        nearest_poi = min(pois, key=lambda p: haversine_m(lat, lon, p.lat, p.lon))
        dest_lat, dest_lon, dest_name = nearest_poi.lat, nearest_poi.lon, nearest_poi.name
    else:
        return _missing_result(c, "no destination configured")

    mode = c.mode.value if c.mode != Mode.NONE else "walk"
    route = providers.route(lat, lon, dest_lat, dest_lon, mode)

    if c.units == "miles":
        measured = meters_to_miles(route.distance_m)
    elif c.units == "minutes":
        measured = route.duration_s / 60.0
    else:
        measured = route.distance_m

    passed = _hard_ok(c, measured) if c.kind == Kind.HARD else True
    pref = _pref_score(c, measured) if c.kind == Kind.PREFERENCE else None
    verb = "passes" if _hard_ok(c, measured) else "exceeds"
    fb = " (straight-line estimate)" if route.is_fallback else " (network route)"
    return CriterionResult(
        criterion_id=c.id, label=c.label, kind=c.kind.value, passed=passed,
        preference_score=pref, raw_value=round(measured, 3), units=c.units,
        threshold=c.threshold, weight=c.weight, confidence=route.confidence,
        source=route.source, is_fallback=route.is_fallback, missing=False,
        explanation=(f"{mode.title()} to {dest_name}: {measured:.2f} {c.units} "
                     f"{verb} threshold {c.threshold}{fb}."),
        detail={"destination": dest_name, "dest_lat": dest_lat, "dest_lon": dest_lon,
                "distance_m": round(route.distance_m, 1),
                "duration_min": round(route.duration_s / 60.0, 2)},
    )


# --------------------------------------------------------------------------- #
#  Listing criteria
# --------------------------------------------------------------------------- #

def evaluate_listing_criterion(c: Criterion, fields: dict[str, Any]) -> CriterionResult:
    key = c.type.value  # e.g. "rent", "bedrooms", "parking"
    value = fields.get(key)
    if value is None:
        return _missing_result(c, f"listing has no '{key}'")

    if c.method == Method.BOOLEAN:
        truthy = bool(value)
        passed = truthy if c.kind == Kind.HARD else True
        pref = (1.0 if truthy else 0.0) if c.kind == Kind.PREFERENCE else None
        return CriterionResult(
            criterion_id=c.id, label=c.label, kind=c.kind.value, passed=passed,
            preference_score=pref, raw_value=1.0 if truthy else 0.0, units=c.units,
            threshold=c.threshold, weight=c.weight, confidence=0.9,
            source="listing", is_fallback=False, missing=False,
            explanation=f"{key}={truthy}; " + ("meets" if truthy else "does not meet") + " requirement.",
        )

    try:
        measured = float(value)
    except (TypeError, ValueError):
        return _missing_result(c, f"'{key}' not numeric")

    passed = _hard_ok(c, measured) if c.kind == Kind.HARD else True
    pref = _pref_score(c, measured) if c.kind == Kind.PREFERENCE else None
    verb = "meets" if _hard_ok(c, measured) else "violates"
    return CriterionResult(
        criterion_id=c.id, label=c.label, kind=c.kind.value, passed=passed,
        preference_score=pref, raw_value=measured, units=c.units,
        threshold=c.threshold, weight=c.weight, confidence=0.9,
        source="listing", is_fallback=False, missing=False,
        explanation=f"{key}={measured:g} {verb} threshold {c.threshold} ({c.comparator.value}).",
    )


# --------------------------------------------------------------------------- #
#  Aggregation
# --------------------------------------------------------------------------- #

def aggregate(results: list[CriterionResult]) -> UnitScore:
    hard = [r for r in results if r.kind == Kind.HARD.value]
    hard_passed = all(r.passed for r in hard)

    scored = [r for r in results if r.preference_score is not None and r.weight > 0]
    total_w = sum(r.weight for r in scored)
    if total_w > 0:
        pref = sum(r.preference_score * r.weight for r in scored) / total_w * 100.0
    else:
        pref = 0.0

    # Data coverage: fraction of enabled criteria that produced a usable value.
    usable = [r for r in results if not r.missing]
    coverage = (len(usable) / len(results)) if results else 0.0
    confidence = (sum(r.confidence for r in results) / len(results)) if results else 0.0

    if coverage < MIN_DATA_COVERAGE:
        tier = Tier.INSUFFICIENT_DATA
    elif not hard_passed:
        tier = Tier.INELIGIBLE
    elif pref >= STRONG_FIT:
        tier = Tier.STRONG_FIT
    elif pref >= QUALIFYING:
        tier = Tier.QUALIFYING
    else:
        tier = Tier.BORDERLINE

    # Ineligible units keep their computed preference score for transparency,
    # but it must never promote them out of ineligibility (enforced above).
    fit = pref if hard_passed else 0.0
    return UnitScore(hard_passed=hard_passed, fit_score=fit, tier=tier,
                     confidence=confidence, results=results)
