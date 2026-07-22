"""Persistence helpers and an in-process analysis cache."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from .analysis.engine import AnalysisResult
from .criteria.schema import Profile
from .db import ListingRow, ProfileRow, SnapshotRow


def save_profile(db: Session, profile: Profile, owner_id: str = "public") -> Profile:
    row = db.get(ProfileRow, profile.id)
    payload = profile.model_dump(mode="json")
    if row is None:
        row = ProfileRow(id=profile.id, name=profile.name, city=profile.city,
                         owner_id=owner_id, data=payload)
        db.add(row)
    else:
        row.name, row.city, row.data = profile.name, profile.city, payload
    db.commit()
    return profile


def get_profile(db: Session, profile_id: str) -> Optional[Profile]:
    row = db.get(ProfileRow, profile_id)
    return Profile.model_validate(row.data) if row else None


def profile_owner(db: Session, profile_id: str) -> Optional[str]:
    row = db.get(ProfileRow, profile_id)
    return row.owner_id if row else None


def list_profiles(db: Session, owner_id: Optional[str] = None) -> list[Profile]:
    q = db.query(ProfileRow)
    if owner_id is not None:
        q = q.filter(ProfileRow.owner_id == owner_id)
    return [Profile.model_validate(r.data) for r in q.all()]


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


# --- in-memory analysis cache (keyed by profile id) ------------------------ #
_ANALYSIS_CACHE: dict[str, AnalysisResult] = {}


def cache_analysis(profile_id: str, result: AnalysisResult) -> None:
    _ANALYSIS_CACHE[profile_id] = result


def get_cached_analysis(profile_id: str) -> Optional[AnalysisResult]:
    return _ANALYSIS_CACHE.get(profile_id)


def invalidate_analysis(profile_id: str) -> None:
    _ANALYSIS_CACHE.pop(profile_id, None)


# --- persisted snapshots (history, keyed by criteria signature) ------------ #

def record_snapshot(db: Session, result: AnalysisResult) -> None:
    """Persist a run's summary. Deduped by (profile_id, signature): if the latest
    snapshot already has this signature, don't add a duplicate row."""
    latest = (db.query(SnapshotRow)
              .filter(SnapshotRow.profile_id == result.profile_id)
              .order_by(SnapshotRow.id.desc()).first())
    if latest and latest.signature == result.signature:
        return
    db.add(SnapshotRow(profile_id=result.profile_id, signature=result.signature,
                       summary=result.summary()))
    db.commit()


def list_snapshots(db: Session, profile_id: str, limit: int = 20) -> list[dict]:
    rows = (db.query(SnapshotRow)
            .filter(SnapshotRow.profile_id == profile_id)
            .order_by(SnapshotRow.id.desc()).limit(limit).all())
    return [
        {"id": r.id, "signature": r.signature,
         "created_at": r.created_at.isoformat() if r.created_at else None,
         "tier_counts": r.summary.get("tier_counts"),
         "zone_count": r.summary.get("zone_count"),
         "cell_count": r.summary.get("cell_count")}
        for r in rows
    ]
