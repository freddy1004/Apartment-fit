"""City-area analysis endpoints: run, results, layers, POIs, and exports."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import store
from ..analysis.engine import run_city_analysis
from ..analysis.exporters import area_results_to_csv, area_results_to_geojson
from ..config import settings
from ..db import get_session
from ..providers.registry import get_providers

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _load_or_run(db: Session, profile_id: str, force: bool = False):
    if not force:
        cached = store.get_cached_analysis(profile_id)
        if cached:
            return cached
    profile = store.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(404, "profile not found")
    providers = get_providers(settings.provider_mode)
    result = run_city_analysis(profile, providers)
    store.cache_analysis(profile_id, result)
    return result


@router.post("/{profile_id}/run")
def run(profile_id: str, db: Session = Depends(get_session)):
    result = _load_or_run(db, profile_id, force=True)
    return {
        "profile_id": profile_id,
        "cell_count": len(result.cells),
        "tier_counts": result.tier_counts,
        "zone_count": len(result.zones),
        "elimination": result.elimination,
        "bbox": result.bbox,
    }


@router.get("/{profile_id}/geojson")
def geojson(profile_id: str, db: Session = Depends(get_session)):
    return area_results_to_geojson(_load_or_run(db, profile_id))


@router.get("/{profile_id}/cells/{cell_id}")
def cell_detail(profile_id: str, cell_id: str, db: Session = Depends(get_session)):
    """Full explanation for one cell: which criteria passed/failed, raw values."""
    result = _load_or_run(db, profile_id)
    for cr in result.cells:
        if cr.cell.id == cell_id:
            s = cr.score
            return {
                "cell_id": cell_id,
                "center": {"lat": cr.cell.center_lat, "lon": cr.cell.center_lon},
                "tier": s.tier,
                "fit_score": round(s.fit_score, 1),
                "hard_passed": s.hard_passed,
                "confidence": round(s.confidence, 2),
                "criteria": [r.__dict__ for r in s.results],
            }
    raise HTTPException(404, "cell not found")


@router.get("/{profile_id}/zones")
def zones(profile_id: str, db: Session = Depends(get_session)):
    return _load_or_run(db, profile_id).zones


@router.get("/{profile_id}/elimination")
def elimination(profile_id: str, db: Session = Depends(get_session)):
    return _load_or_run(db, profile_id).elimination


@router.get("/{profile_id}/pois")
def pois(profile_id: str, db: Session = Depends(get_session)):
    """Destination + amenity markers referenced by the profile's area criteria."""
    profile = store.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(404, "profile not found")
    providers = get_providers(settings.provider_mode)
    bbox = profile.bbox or _load_or_run(db, profile_id).bbox
    layers: dict[str, list] = {}
    for c in profile.area_criteria():
        if c.destination and c.destination.amenity_type:
            cat = c.destination.amenity_type
            if cat in layers:
                continue
            layers[cat] = [
                {"lat": p.lat, "lon": p.lon, "name": p.name, "source": p.source}
                for p in providers.find_pois(cat, bbox)
            ]
        elif c.destination and c.destination.lat is not None:
            layers.setdefault("destinations", []).append({
                "lat": c.destination.lat, "lon": c.destination.lon,
                "name": c.destination.label, "source": "criterion",
            })
    return layers


@router.get("/{profile_id}/export.csv")
def export_csv(profile_id: str, db: Session = Depends(get_session)):
    csv_text = area_results_to_csv(_load_or_run(db, profile_id))
    return Response(csv_text, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{profile_id}-areas.csv"'})


@router.get("/{profile_id}/export.geojson")
def export_geojson(profile_id: str, db: Session = Depends(get_session)):
    import json
    gj = area_results_to_geojson(_load_or_run(db, profile_id))
    return Response(json.dumps(gj), media_type="application/geo+json",
                    headers={"Content-Disposition": f'attachment; filename="{profile_id}-areas.geojson"'})
