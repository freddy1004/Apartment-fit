"""Listing ingestion from multiple sources.

Supported inputs:
- address entry     -> geocode only
- manual form       -> structured dict, validated
- listing URL       -> parse identifiers from the URL; the user supplies visible
                       fields (we do NOT scrape Zillow/other sites server-side)
- CSV / JSON import -> bulk
- browser extension -> posts the same structured payload as the manual form

Policy: Apartment Fit never performs unauthorized bulk scraping, uses private
APIs, bypasses CAPTCHAs, or circumvents anti-bot measures. The browser extension
captures only user-visible structured data from the page the user is viewing and
sends it here for confirmation.
"""
from __future__ import annotations

import csv
import io
import json
import re
import uuid
from typing import Any, Optional
from urllib.parse import urlparse

# Canonical listing fields the scoring engine understands.
LISTING_FIELDS = {
    "rent", "fees", "bedrooms", "bathrooms", "size", "parking", "laundry",
    "pets", "lease_length", "listing_amenities",
}
_BOOL_FIELDS = {"parking", "laundry", "pets"}
_NUM_FIELDS = {"rent", "fees", "bedrooms", "bathrooms", "size", "lease_length"}


def _coerce(field: str, value: Any) -> Any:
    if value is None or value == "":
        return None
    if field in _BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "y", "allowed", "in-unit", "included")
    if field in _NUM_FIELDS:
        try:
            return float(re.sub(r"[^0-9.\-]", "", str(value)))
        except ValueError:
            return None
    return value


def normalize_listing(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate + coerce a raw listing dict into canonical form."""
    out: dict[str, Any] = {
        "id": str(raw.get("id") or uuid.uuid4().hex[:10]),
        "address": (raw.get("address") or "").strip(),
        "source_url": raw.get("source_url") or raw.get("url") or "",
        "source": raw.get("source") or "manual",
        "title": raw.get("title") or "",
        "notes": raw.get("notes") or "",
        "favorite": bool(raw.get("favorite", False)),
    }
    if raw.get("lat") is not None and raw.get("lon") is not None:
        out["lat"] = float(raw["lat"])
        out["lon"] = float(raw["lon"])
    for f in LISTING_FIELDS:
        if f in raw:
            v = _coerce(f, raw[f])
            if v is not None:
                out[f] = v
    return out


def detect_listing_site(url: str) -> Optional[str]:
    if not url:
        return None
    host = (urlparse(url).hostname or "").lower()
    for site in ("zillow", "redfin", "apartments", "trulia", "craigslist", "hotpads"):
        if site in host:
            return site
    return host or None


def from_url_stub(url: str) -> dict[str, Any]:
    """Create a listing shell from a URL.

    We deliberately do not fetch or scrape the page server-side. The user (or the
    compliant browser extension viewing the page) supplies the visible fields.
    """
    site = detect_listing_site(url)
    return {
        "id": uuid.uuid4().hex[:10],
        "source_url": url,
        "source": site or "url",
        "needs_manual_confirmation": True,
    }


def from_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    return [normalize_listing(row) for row in reader]


def from_json(text: str) -> list[dict[str, Any]]:
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("listings", [data])
    return [normalize_listing(row) for row in data]
