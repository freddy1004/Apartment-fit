"""Profile CRUD, demo seeding, and duplication."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import store
from ..analysis.demo import new_profile_from, seattle_demo_profile
from ..auth import Principal, current_user
from ..config import settings
from ..criteria import builder as B
from ..criteria.schema import (
    Comparator,
    Criterion,
    CriterionType,
    Destination,
    Kind,
    Layer,
    Method,
    MissingDataBehavior,
    Mode,
    Profile,
    Scope,
)
from ..db import get_session
from ..providers.registry import get_providers

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _owned(db: Session, profile_id: str, user: Principal) -> Profile:
    """Fetch a profile, enforcing ownership when auth is enabled."""
    owner = store.profile_owner(db, profile_id)
    if owner is None:
        raise HTTPException(404, "profile not found")
    if owner != user.id and owner != "public":
        raise HTTPException(404, "profile not found")
    return store.get_profile(db, profile_id)  # type: ignore[return-value]


@router.get("")
def list_all(db: Session = Depends(get_session), user: Principal = Depends(current_user)):
    owned = store.list_profiles(db, owner_id=user.id)
    shared = [p for p in store.list_profiles(db, owner_id="public") if user.id != "public"]
    seen = {p.id for p in owned}
    profiles = owned + [p for p in shared if p.id not in seen]
    return [p.model_dump(mode="json") for p in profiles]


@router.post("/seed-demo")
def seed_demo(db: Session = Depends(get_session), user: Principal = Depends(current_user)):
    profile = seattle_demo_profile()
    store.save_profile(db, profile, owner_id=user.id)
    return profile.model_dump(mode="json")


@router.get("/{profile_id}")
def get_one(profile_id: str, db: Session = Depends(get_session),
            user: Principal = Depends(current_user)):
    return _owned(db, profile_id, user).model_dump(mode="json")


@router.put("/{profile_id}")
def upsert(profile_id: str, body: Profile, db: Session = Depends(get_session),
           user: Principal = Depends(current_user)):
    _owned(db, profile_id, user)  # ownership guard (404 if not yours)
    body.id = profile_id
    store.save_profile(db, body, owner_id=user.id)
    store.invalidate_analysis(profile_id)  # thresholds/weights may have changed
    return body.model_dump(mode="json")


@router.post("")
def create(body: Profile, db: Session = Depends(get_session),
           user: Principal = Depends(current_user)):
    store.save_profile(db, body, owner_id=user.id)
    return body.model_dump(mode="json")


@router.delete("/{profile_id}")
def remove(profile_id: str, db: Session = Depends(get_session),
           user: Principal = Depends(current_user)):
    _owned(db, profile_id, user)
    store.delete_profile(db, profile_id)
    return {"deleted": profile_id}


class DuplicateIn(BaseModel):
    name: str
    city: str
    center_lat: float
    center_lon: float
    bbox: list[float] | None = None


@router.post("/{profile_id}/duplicate")
def duplicate(profile_id: str, body: DuplicateIn, db: Session = Depends(get_session),
              user: Principal = Depends(current_user)):
    src = _owned(db, profile_id, user)
    clone = new_profile_from(src, body.name, body.city, body.center_lat,
                             body.center_lon, body.bbox)
    store.save_profile(db, clone, owner_id=user.id)
    return clone.model_dump(mode="json")


# --------------------------------------------------------------------------- #
#  Geospatial: import layers, draw boundary zones, add layer criteria
# --------------------------------------------------------------------------- #

class LayerImportIn(BaseModel):
    name: str
    value_property: str | None = None
    units: str = ""
    default_value: float | None = None
    kind: str = "choropleth"
    geojson: dict  # a GeoJSON FeatureCollection


def _save_and_refresh(db: Session, profile: Profile):
    store.save_profile(db, profile)
    store.invalidate_analysis(profile.id)


@router.post("/{profile_id}/layers/import")
def import_layer(profile_id: str, body: LayerImportIn, db: Session = Depends(get_session)):
    profile = store.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(404, "profile not found")
    lid = f"layer-{len(profile.layers) + 1}-{body.name.lower().replace(' ', '-')[:20]}"
    layer = Layer(
        id=lid, name=body.name, kind=body.kind, units=body.units,
        value_property=body.value_property, default_value=body.default_value,
        features=body.geojson,
    )
    profile.layers.append(layer)
    _save_and_refresh(db, profile)
    return {"layer_id": lid, "feature_count": len(body.geojson.get("features", []))}


_AMENITY_TYPE = {
    "supermarket": CriterionType.GROCERIES,
    "park": CriterionType.PARKS,
    "transit_stop": CriterionType.TRANSIT,
    "freeway_ramp": CriterionType.FREEWAY_ACCESS,
}
_LISTING_NUMERIC = {
    "rent": (CriterionType.RENT, Comparator.LTE, "usd_per_month"),
    "fees": (CriterionType.FEES, Comparator.LTE, "usd"),
    "bedrooms": (CriterionType.BEDROOMS, Comparator.GTE, "rooms"),
    "bathrooms": (CriterionType.BATHROOMS, Comparator.GTE, "rooms"),
    "size": (CriterionType.SIZE, Comparator.GTE, "sqft"),
    "lease_length": (CriterionType.LEASE_LENGTH, Comparator.GTE, "months"),
}
_LISTING_BOOL = {
    "parking": CriterionType.PARKING,
    "laundry": CriterionType.LAUNDRY,
    "pets": CriterionType.PETS,
}


class NewCriterionIn(BaseModel):
    scope: str                      # "area" | "listing"
    kind: str = "preference"        # "hard" | "preference"
    weight: float = 1.0
    label: str | None = None
    # --- area (travel to a destination or amenity) ---
    source: str | None = None       # "amenity" | "place"
    amenity_type: str | None = None  # supermarket | park | transit_stop | freeway_ramp
    dest_address: str | None = None  # geocoded server-side to a point
    dest_lat: float | None = None
    dest_lon: float | None = None
    mode: str = "walk"              # walk | bike | drive | transit
    measure: str = "time"          # "time" (minutes) | "distance" (miles)
    threshold: float | None = None
    # --- listing ---
    field: str | None = None        # rent | bedrooms | ... | parking | laundry | pets


@router.post("/{profile_id}/criteria")
def add_criterion(profile_id: str, body: NewCriterionIn, db: Session = Depends(get_session)):
    """Define a brand-new criterion (area travel/amenity, or a listing field)."""
    profile = store.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(404, "profile not found")
    hard = body.kind == "hard"
    missing = MissingDataBehavior.FAIL if hard else MissingDataBehavior.NEUTRAL
    resolved = None

    if body.scope == "area":
        units = "miles" if body.measure == "distance" else "minutes"
        try:
            mode = Mode(body.mode)
        except ValueError:
            raise HTTPException(400, f"invalid mode '{body.mode}'")

        if body.source == "amenity" or body.amenity_type:
            if not body.amenity_type:
                raise HTTPException(400, "amenity_type required for an amenity criterion")
            ctype = _AMENITY_TYPE.get(body.amenity_type, CriterionType.AMENITIES)
            dest = Destination(label=body.amenity_type.replace("_", " "),
                               amenity_type=body.amenity_type)
            method = Method.POI_DISTANCE
            dest_desc = dest.label
        else:  # a specific place
            lat, lon = body.dest_lat, body.dest_lon
            place_label = body.dest_address or "place"
            if lat is None or lon is None:
                if not body.dest_address:
                    raise HTTPException(400, "dest_address or dest_lat/lon required")
                geo = get_providers(settings.provider_mode).geocode(body.dest_address)
                if not geo:
                    raise HTTPException(400, f"could not geocode '{body.dest_address}'")
                lat, lon, place_label = geo.lat, geo.lon, geo.display_name
                resolved = {"lat": geo.lat, "lon": geo.lon,
                            "display_name": geo.display_name, "confidence": geo.confidence}
            ctype = CriterionType.COMMUTE
            dest = Destination(label=place_label, lat=lat, lon=lon)
            method = Method.ROUTE
            dest_desc = place_label

        if body.threshold is None:
            raise HTTPException(400, "threshold required")
        label = body.label or (f"{body.mode.title()} <= {body.threshold:g} {units} to {dest_desc}")
        crit = Criterion(
            id=B._new_id(), type=ctype, scope=Scope.AREA,
            kind=Kind.HARD if hard else Kind.PREFERENCE, label=label,
            threshold=body.threshold, units=units, comparator=Comparator.LTE,
            weight=body.weight, mode=mode, method=method, destination=dest,
            missing_data=missing,
        )

    elif body.scope == "listing":
        if not body.field:
            raise HTTPException(400, "field required for a listing criterion")
        if body.field in _LISTING_BOOL:
            ctype = _LISTING_BOOL[body.field]
            label = body.label or f"{body.field.title()} available"
            crit = Criterion(
                id=B._new_id(), type=ctype, scope=Scope.LISTING,
                kind=Kind.HARD if hard else Kind.PREFERENCE, label=label,
                comparator=Comparator.TRUE, weight=body.weight, method=Method.BOOLEAN,
                units="bool", missing_data=missing,
            )
        elif body.field in _LISTING_NUMERIC:
            ctype, comp, units = _LISTING_NUMERIC[body.field]
            if body.threshold is None:
                raise HTTPException(400, "threshold required")
            sign = "<=" if comp == Comparator.LTE else ">="
            label = body.label or f"{body.field.title()} {sign} {body.threshold:g} {units}"
            crit = Criterion(
                id=B._new_id(), type=ctype, scope=Scope.LISTING,
                kind=Kind.HARD if hard else Kind.PREFERENCE, label=label,
                threshold=body.threshold, units=units, comparator=comp,
                weight=body.weight, method=Method.NUMERIC, missing_data=missing,
            )
        else:
            raise HTTPException(400, f"unknown listing field '{body.field}'")
    else:
        raise HTTPException(400, "scope must be 'area' or 'listing'")

    profile.criteria.append(crit)
    _save_and_refresh(db, profile)
    return {**crit.model_dump(mode="json"), "resolved_destination": resolved}


class BoundaryIn(BaseModel):
    geometry: list  # polygon rings [[[lon,lat],...]] or MultiPolygon
    mode: str = "inclusion"  # inclusion | exclusion
    label: str | None = None
    hard: bool = True
    weight: float = 1.0


@router.post("/{profile_id}/criteria/boundary")
def add_boundary(profile_id: str, body: BoundaryIn, db: Session = Depends(get_session)):
    profile = store.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(404, "profile not found")
    if body.mode == "exclusion":
        crit = B.exclusion_zone(body.geometry, body.label or "Outside drawn exclusion zone",
                                hard=body.hard, weight=body.weight)
    else:
        crit = B.inclusion_zone(body.geometry, body.label or "Inside drawn inclusion zone",
                                hard=body.hard, weight=body.weight)
    profile.criteria.append(crit)
    _save_and_refresh(db, profile)
    return crit.model_dump(mode="json")


class LayerCriterionIn(BaseModel):
    layer_id: str
    layer_property: str
    threshold: float
    units: str = ""
    comparator: str = "lte"
    label: str
    hard: bool = False
    weight: float = 1.0


@router.post("/{profile_id}/criteria/layer")
def add_layer_criterion(profile_id: str, body: LayerCriterionIn, db: Session = Depends(get_session)):
    profile = store.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(404, "profile not found")
    if not profile.layer(body.layer_id):
        raise HTTPException(400, f"layer '{body.layer_id}' not in profile")
    crit = B.layer_threshold(
        body.layer_id, body.layer_property, body.threshold, body.units, body.label,
        comparator=Comparator(body.comparator), hard=body.hard, weight=body.weight)
    profile.criteria.append(crit)
    _save_and_refresh(db, profile)
    return crit.model_dump(mode="json")


@router.delete("/{profile_id}/criteria/{criterion_id}")
def delete_criterion(profile_id: str, criterion_id: str, db: Session = Depends(get_session)):
    profile = store.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(404, "profile not found")
    before = len(profile.criteria)
    profile.criteria = [c for c in profile.criteria if c.id != criterion_id]
    if len(profile.criteria) == before:
        raise HTTPException(404, "criterion not found")
    _save_and_refresh(db, profile)
    return {"deleted": criterion_id}
