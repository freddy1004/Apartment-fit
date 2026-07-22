"""Listing ingestion, scoring, comparison, and export endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import store
from ..analysis.engine import score_listing
from ..analysis.exporters import listing_scores_to_csv
from ..config import settings
from ..db import get_session
from ..listings import ingest
from ..listings.matcher import run_alerts
from ..providers.registry import get_providers

router = APIRouter(prefix="/api/profiles/{profile_id}/listings", tags=["listings"])


class AddressIn(BaseModel):
    address: str


class UrlIn(BaseModel):
    url: str


class ImportIn(BaseModel):
    format: str  # "csv" | "json"
    content: str


def _require_profile(db: Session, profile_id: str):
    p = store.get_profile(db, profile_id)
    if not p:
        raise HTTPException(404, "profile not found")
    return p


def _geocode_if_needed(listing: dict) -> dict:
    if listing.get("lat") is None or listing.get("lon") is None:
        providers = get_providers(settings.provider_mode)
        addr = listing.get("address") or ""
        geo = providers.geocode(addr) if addr else None
        if geo:
            listing["lat"], listing["lon"] = geo.lat, geo.lon
            listing["geocode_source"] = geo.source
            listing["geocode_confidence"] = geo.confidence
    return listing


@router.get("")
def list_all(profile_id: str, db: Session = Depends(get_session)):
    _require_profile(db, profile_id)
    return store.list_listings(db, profile_id)


@router.post("/address")
def add_address(profile_id: str, body: AddressIn, db: Session = Depends(get_session)):
    _require_profile(db, profile_id)
    listing = ingest.normalize_listing({"address": body.address, "source": "address"})
    listing = _geocode_if_needed(listing)
    store.save_listing(db, profile_id, listing)
    return listing


@router.post("/manual")
def add_manual(profile_id: str, body: dict, db: Session = Depends(get_session)):
    _require_profile(db, profile_id)
    listing = ingest.normalize_listing({**body, "source": body.get("source", "manual")})
    listing = _geocode_if_needed(listing)
    store.save_listing(db, profile_id, listing)
    return listing


@router.post("/url")
def add_url(profile_id: str, body: UrlIn, db: Session = Depends(get_session)):
    _require_profile(db, profile_id)
    stub = ingest.from_url_stub(body.url)
    listing = ingest.normalize_listing(stub)
    store.save_listing(db, profile_id, listing)
    return {**listing, "needs_manual_confirmation": True,
            "message": "URL saved. Provide visible fields via the form or extension; "
                       "server-side scraping is intentionally not performed."}


@router.post("/extension")
def add_from_extension(profile_id: str, body: dict, db: Session = Depends(get_session)):
    """Endpoint the browser extension posts user-visible structured data to."""
    _require_profile(db, profile_id)
    listing = ingest.normalize_listing({**body, "source": body.get("source", "extension")})
    listing = _geocode_if_needed(listing)
    store.save_listing(db, profile_id, listing)
    return listing


@router.post("/import")
def bulk_import(profile_id: str, body: ImportIn, db: Session = Depends(get_session)):
    _require_profile(db, profile_id)
    rows = ingest.from_csv(body.content) if body.format == "csv" else ingest.from_json(body.content)
    saved = []
    for row in rows:
        row = _geocode_if_needed(row)
        store.save_listing(db, profile_id, row)
        saved.append(row)
    return {"imported": len(saved), "listings": saved}


class UpdateIn(BaseModel):
    favorite: bool | None = None
    notes: str | None = None


@router.patch("/{listing_id}")
def update_listing(profile_id: str, listing_id: str, body: UpdateIn,
                   db: Session = Depends(get_session)):
    listing = store.get_listing(db, listing_id)
    if not listing:
        raise HTTPException(404, "listing not found")
    if body.favorite is not None:
        listing["favorite"] = body.favorite
    if body.notes is not None:
        listing["notes"] = body.notes
    store.save_listing(db, profile_id, listing)
    return listing


@router.delete("/{listing_id}")
def delete_listing(profile_id: str, listing_id: str, db: Session = Depends(get_session)):
    row = store.get_listing(db, listing_id)
    if not row:
        raise HTTPException(404, "listing not found")
    from ..db import ListingRow
    obj = db.get(ListingRow, listing_id)
    db.delete(obj)
    db.commit()
    return {"deleted": listing_id}


def _score_all(db: Session, profile_id: str):
    profile = _require_profile(db, profile_id)
    providers = get_providers(settings.provider_mode)
    analysis = store.get_cached_analysis(profile_id)
    listings = store.list_listings(db, profile_id)
    scored = []
    for li in listings:
        if li.get("lat") is None or li.get("lon") is None:
            continue
        scored.append(score_listing(profile, li, providers, analysis))
    return listings, scored


@router.get("/scored")
def scored(profile_id: str, db: Session = Depends(get_session)):
    listings, scores = _score_all(db, profile_id)
    by_id = {li["id"]: li for li in listings}
    return [
        {
            "listing": by_id.get(sc.listing_id),
            "combined_fit": sc.combined_fit,
            "combined_tier": sc.combined_tier,
            "matched_zone": sc.matched_zone,
            "confidence": sc.confidence,
            "area": sc.area.to_dict(),
            "listing_score": sc.listing.to_dict(),
        }
        for sc in scores
    ]


@router.get("/export.csv")
def export_csv(profile_id: str, db: Session = Depends(get_session)):
    listings, scores = _score_all(db, profile_id)
    by_id = {li["id"]: li for li in listings}
    csv_text = listing_scores_to_csv(scores, by_id)
    return Response(csv_text, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{profile_id}-listings.csv"'})


@router.post("/alerts/run")
def run_alerts_now(profile_id: str, db: Session = Depends(get_session)):
    """Run saved-search alerts once: notify on NEW matches and record them."""
    from ..alerts import run_profile_alerts
    _require_profile(db, profile_id)
    return run_profile_alerts(db, profile_id)


@router.get("/matches")
def matches(profile_id: str, db: Session = Depends(get_session)):
    """Saved-search matches: stored listings passing every hard requirement.

    Runs them through the alert notifier (logging by default) -- the foundation
    for "notify me when a new listing matches this profile".
    """
    profile = _require_profile(db, profile_id)
    providers = get_providers(settings.provider_mode)
    analysis = store.get_cached_analysis(profile_id)
    listings = store.list_listings(db, profile_id)
    matched = run_alerts(profile, listings, providers, analysis)
    return {"profile_id": profile_id, "match_count": len(matched), "matches": matched}
