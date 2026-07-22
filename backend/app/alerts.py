"""Saved-search alert runs: detect NEW matches and dispatch notifications.

A "new match" is a listing that satisfies every hard requirement and hasn't been
alerted for this profile before (tracked in ``AlertStateRow``). This is the
foundation for "notify me when a new listing matches" — run it on a schedule
(see the optional scheduler in ``main.py``) or on demand via the API.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from . import store
from .config import settings
from .db import AlertStateRow
from .listings.matcher import Notifier, build_notifier, find_matches
from .providers.registry import get_providers


def run_profile_alerts(db: Session, profile_id: str,
                       notifier: Optional[Notifier] = None) -> dict:
    profile = store.get_profile(db, profile_id)
    if not profile:
        return {"profile_id": profile_id, "error": "not found"}
    providers = get_providers(settings.provider_mode)
    analysis = store.get_cached_analysis(profile_id)
    listings = store.list_listings(db, profile_id)
    matches = find_matches(profile, listings, providers, analysis)

    row = db.get(AlertStateRow, profile_id)
    seen = set(row.seen_listing_ids or []) if row else set()
    new_matches = [m for m in matches if m["listing_id"] not in seen]

    if new_matches:
        (notifier or build_notifier()).notify(profile, new_matches)

    all_ids = [m["listing_id"] for m in matches]
    if row is None:
        db.add(AlertStateRow(profile_id=profile_id, seen_listing_ids=all_ids,
                             last_run=datetime.now(timezone.utc)))
    else:
        row.seen_listing_ids = all_ids
        row.last_run = datetime.now(timezone.utc)
    db.commit()

    return {
        "profile_id": profile_id,
        "total_matches": len(matches),
        "new_matches": new_matches,
        "notified": len(new_matches),
    }


def run_all_alerts(db: Session, notifier: Optional[Notifier] = None) -> list[dict]:
    return [run_profile_alerts(db, p.id, notifier) for p in store.list_profiles(db)]
