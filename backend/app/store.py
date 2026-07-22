"""Persistence helpers and an in-process analysis cache."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from .analysis.engine import AnalysisResult
from .criteria.schema import Profile
from .db import ListingRow, ProfileRow


def save_profile(db: Session, profile: Profile) -> Profile:
    row = db.get(ProfileRow, profile.id)
    payload = profile.model_dump(mode="json")
    if row is None:
        row = ProfileRow(id=profile.id, name=profile.name, city=profile.city, data=payload)
        db.add(row)
    else:
        row.name, row.city, row.data = profile.name, profile.city, payload
    db.commit()
    return profile


def get_profile(db: Session, profile_id: str) -> Optional[Profile]:
    row = db.get(ProfileRow, profile_id)
    return Profile.model_validate(row.data) if row else None


def list_profiles(db: Session) -> list[Profile]:
    return [Profile.model_validate(r.data) for r in db.query(ProfileRow).all()]


def delete_profile(db: Session, profile_id: str) -> bool:
    row = db.get(ProfileRow, profile_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def save_listing(db: Session, profile_id: str, listing: dict) -> dict:
    row = db.get(ListingRow, listing["id"])
    if row is None:
        row = ListingRow(id=listing["id"], profile_id=profile_id, data=listing)
        db.add(row)
    else:
        row.profile_id, row.data = profile_id, listing
    db.commit()
    return listing


def list_listings(db: Session, profile_id: str) -> list[dict]:
    return [r.data for r in db.query(ListingRow).filter(ListingRow.profile_id == profile_id).all()]


def get_listing(db: Session, listing_id: str) -> Optional[dict]:
    row = db.get(ListingRow, listing_id)
    return row.data if row else None


# --- simple analysis cache (keyed by profile id) --------------------------- #
_ANALYSIS_CACHE: dict[str, AnalysisResult] = {}


def cache_analysis(profile_id: str, result: AnalysisResult) -> None:
    _ANALYSIS_CACHE[profile_id] = result


def get_cached_analysis(profile_id: str) -> Optional[AnalysisResult]:
    return _ANALYSIS_CACHE.get(profile_id)


def invalidate_analysis(profile_id: str) -> None:
    _ANALYSIS_CACHE.pop(profile_id, None)
