"""Profile CRUD, demo seeding, and duplication."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import store
from ..analysis.demo import new_profile_from, seattle_demo_profile
from ..criteria.schema import Profile
from ..db import get_session

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("")
def list_all(db: Session = Depends(get_session)):
    return [p.model_dump(mode="json") for p in store.list_profiles(db)]


@router.post("/seed-demo")
def seed_demo(db: Session = Depends(get_session)):
    profile = seattle_demo_profile()
    store.save_profile(db, profile)
    return profile.model_dump(mode="json")


@router.get("/{profile_id}")
def get_one(profile_id: str, db: Session = Depends(get_session)):
    p = store.get_profile(db, profile_id)
    if not p:
        raise HTTPException(404, "profile not found")
    return p.model_dump(mode="json")


@router.put("/{profile_id}")
def upsert(profile_id: str, body: Profile, db: Session = Depends(get_session)):
    body.id = profile_id
    store.save_profile(db, body)
    store.invalidate_analysis(profile_id)  # thresholds/weights may have changed
    return body.model_dump(mode="json")


@router.post("")
def create(body: Profile, db: Session = Depends(get_session)):
    store.save_profile(db, body)
    return body.model_dump(mode="json")


@router.delete("/{profile_id}")
def remove(profile_id: str, db: Session = Depends(get_session)):
    if not store.delete_profile(db, profile_id):
        raise HTTPException(404, "profile not found")
    return {"deleted": profile_id}


class DuplicateIn(BaseModel):
    name: str
    city: str
    center_lat: float
    center_lon: float
    bbox: list[float] | None = None


@router.post("/{profile_id}/duplicate")
def duplicate(profile_id: str, body: DuplicateIn, db: Session = Depends(get_session)):
    src = store.get_profile(db, profile_id)
    if not src:
        raise HTTPException(404, "profile not found")
    clone = new_profile_from(src, body.name, body.city, body.center_lat,
                             body.center_lon, body.bbox)
    store.save_profile(db, clone)
    return clone.model_dump(mode="json")
