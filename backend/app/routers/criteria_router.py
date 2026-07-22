"""Criteria builder endpoints: ambiguity flagging + templates."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..criteria import builder
from ..criteria.schema import CriterionType, Mode, Scope

router = APIRouter(prefix="/api/criteria", tags=["criteria"])


class TextIn(BaseModel):
    text: str


@router.post("/flag-ambiguities")
def flag(body: TextIn):
    flags = builder.flag_ambiguities(body.text)
    return {
        "flags": [
            {"term": f.term, "reason": f.reason, "suggestions": f.suggestions}
            for f in flags
        ]
    }


@router.get("/vocabulary")
def vocabulary():
    """Enumerate supported criterion types, modes, and scopes for the UI."""
    return {
        "area_types": [
            CriterionType.COMMUTE.value, CriterionType.GROCERIES.value,
            CriterionType.TRANSIT.value, CriterionType.PARKS.value,
            CriterionType.FREEWAY_ACCESS.value, CriterionType.AMENITIES.value,
            CriterionType.TERRAIN.value, CriterionType.BOUNDARY.value,
            CriterionType.GEOSPATIAL.value,
        ],
        "listing_types": [
            CriterionType.RENT.value, CriterionType.FEES.value,
            CriterionType.BEDROOMS.value, CriterionType.BATHROOMS.value,
            CriterionType.SIZE.value, CriterionType.PARKING.value,
            CriterionType.LAUNDRY.value, CriterionType.PETS.value,
            CriterionType.LEASE_LENGTH.value, CriterionType.LISTING_AMENITIES.value,
        ],
        "modes": [m.value for m in Mode],
        "scopes": [s.value for s in Scope],
        "ambiguous_terms": list(builder.AMBIGUOUS_TERMS.keys()),
    }
