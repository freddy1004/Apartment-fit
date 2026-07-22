"""Export area results as CSV and GeoJSON, and listing scores as CSV."""
from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import AnalysisResult, ListingScore


def area_results_to_geojson(result: "AnalysisResult") -> dict:
    features = []
    for cr in result.cells:
        s = cr.score
        features.append(cr.cell.as_feature({
            "tier": s.tier,
            "fit_score": round(s.fit_score, 1),
            "hard_passed": s.hard_passed,
            "confidence": round(s.confidence, 2),
            "failed_hard": [r.label for r in s.failed_hard()],
        }))
    return {"type": "FeatureCollection", "features": features}


def area_results_to_csv(result: "AnalysisResult") -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["cell_id", "center_lat", "center_lon", "tier", "fit_score",
                "hard_passed", "confidence", "failed_hard_criteria"])
    for cr in result.cells:
        s = cr.score
        w.writerow([
            cr.cell.id, round(cr.cell.center_lat, 6), round(cr.cell.center_lon, 6),
            s.tier, round(s.fit_score, 1), s.hard_passed, round(s.confidence, 2),
            "; ".join(r.label for r in s.failed_hard()),
        ])
    return buf.getvalue()


def listing_scores_to_csv(scores: list["ListingScore"],
                          listings_by_id: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["listing_id", "address", "rent", "bedrooms", "combined_fit",
                "combined_tier", "area_fit", "area_hard_passed",
                "listing_fit", "listing_hard_passed", "matched_zone"])
    for sc in scores:
        li = listings_by_id.get(sc.listing_id, {})
        w.writerow([
            sc.listing_id, li.get("address", ""), li.get("rent", ""),
            li.get("bedrooms", ""), sc.combined_fit, sc.combined_tier,
            round(sc.area.fit_score, 1), sc.area.hard_passed,
            round(sc.listing.fit_score, 1), sc.listing.hard_passed,
            sc.matched_zone or "",
        ])
    return buf.getvalue()
