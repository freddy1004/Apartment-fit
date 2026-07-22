"""City-area analysis and listing scoring orchestration."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from ..criteria.schema import Kind, Profile
from ..providers.registry import Providers, get_providers
from .geo import Cell, cluster_bounds, generate_grid, group_contiguous, haversine_m
from .scoring import (
    CriterionResult,
    Tier,
    UnitScore,
    aggregate,
    evaluate_area_criterion,
    evaluate_listing_criterion,
)


@dataclass
class CellResult:
    cell: Cell
    score: UnitScore


@dataclass
class AnalysisResult:
    profile_id: str
    cells: list[CellResult]
    zones: list[dict]
    elimination: list[dict]
    tier_counts: dict[str, int]
    bbox: list[float]
    signature: str = ""

    def qualifying_cells(self) -> list[Cell]:
        return [cr.cell for cr in self.cells
                if cr.score.tier in (Tier.STRONG_FIT, Tier.QUALIFYING, Tier.BORDERLINE)]

    def summary(self) -> dict:
        return {
            "profile_id": self.profile_id, "signature": self.signature,
            "cell_count": len(self.cells), "tier_counts": self.tier_counts,
            "zone_count": len(self.zones), "elimination": self.elimination,
            "bbox": self.bbox,
        }


def analysis_signature(profile: Profile) -> str:
    """Stable hash of everything that affects an area analysis.

    Two profiles with the same signature must produce identical area results, so
    the signature keys the snapshot cache and lets identical re-runs short-circuit.
    """
    # Exclude volatile/cosmetic fields (random id, human label) so two profiles
    # with the same measurable criteria share a signature.
    def crit_sig(c) -> dict:
        d = c.model_dump(mode="json")
        d.pop("id", None)
        d.pop("label", None)
        return d

    crits = sorted(
        (crit_sig(c) for c in profile.area_criteria()),
        key=lambda d: json.dumps(d, sort_keys=True),
    )
    layers = sorted(
        ({"value_property": l.value_property, "features": l.features,
          "default_value": l.default_value} for l in profile.layers),
        key=lambda d: json.dumps(d, sort_keys=True),
    )
    payload = {"bbox": profile.bbox, "cell_size_m": profile.cell_size_m,
               "criteria": crits, "layers": layers}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _nearest_neighborhoods(centroid_lat: float, centroid_lon: float,
                           k: int = 2) -> list[str]:
    from ..providers.fixture import load_fixture
    hoods = load_fixture().get("neighborhoods", [])
    ranked = sorted(
        hoods, key=lambda h: haversine_m(centroid_lat, centroid_lon, h["lat"], h["lon"]))
    return [h["name"] for h in ranked[:k]]


def run_city_analysis(profile: Profile,
                      providers: Optional[Providers] = None) -> AnalysisResult:
    providers = providers or get_providers()
    bbox = profile.bbox or _default_bbox(profile)
    cells = generate_grid(bbox, profile.cell_size_m)
    area_criteria = profile.area_criteria()
    layers = {l.id: l for l in profile.layers}

    cell_results: list[CellResult] = []
    # Track per-hard-criterion elimination.
    fail_counts: dict[str, int] = {c.id: 0 for c in area_criteria if c.kind == Kind.HARD}
    sole_fail: dict[str, int] = {c.id: 0 for c in area_criteria if c.kind == Kind.HARD}
    labels = {c.id: c.label for c in area_criteria}

    for cell in cells:
        results = [
            evaluate_area_criterion(c, cell.center_lat, cell.center_lon, providers, bbox, layers)
            for c in area_criteria
        ]
        score = aggregate(results)
        cell_results.append(CellResult(cell=cell, score=score))
        failed = score.failed_hard()
        for r in failed:
            fail_counts[r.criterion_id] = fail_counts.get(r.criterion_id, 0) + 1
        if len(failed) == 1:
            sole_fail[failed[0].criterion_id] = sole_fail.get(failed[0].criterion_id, 0) + 1

    # Elimination ranking: which criteria remove the most units.
    elimination = sorted(
        [
            {
                "criterion_id": cid,
                "label": labels.get(cid, cid),
                "eliminated": fail_counts.get(cid, 0),
                "eliminated_solely_by_this": sole_fail.get(cid, 0),
                "pct_of_cells": round(100 * fail_counts.get(cid, 0) / max(1, len(cells)), 1),
            }
            for cid in fail_counts
        ],
        key=lambda d: d["eliminated"], reverse=True,
    )

    # Zones from contiguous qualifying (hard-passing) cells.
    score_by_id = {cr.cell.id: cr.score for cr in cell_results}
    qualifying = [cr.cell for cr in cell_results if cr.score.hard_passed]
    clusters = group_contiguous(qualifying)
    zones = []
    for i, cluster in enumerate(clusters):
        b = cluster_bounds(cluster)
        avg_fit = sum(score_by_id[c.id].fit_score for c in cluster) / len(cluster)
        avg_conf = sum(score_by_id[c.id].confidence for c in cluster) / len(cluster)
        zones.append({
            "zone_id": f"zone-{i + 1}",
            **b,
            "avg_fit_score": round(avg_fit, 1),
            "avg_confidence": round(avg_conf, 2),
            "nearby_neighborhoods": _nearest_neighborhoods(b["centroid_lat"], b["centroid_lon"]),
            "cell_ids": [c.id for c in cluster],
        })
    # Confidence-aware tie-breaking: larger zones first, then more-confident ones.
    zones.sort(key=lambda z: (z["cell_count"], z["avg_confidence"]), reverse=True)
    for i, z in enumerate(zones):
        z["zone_id"] = f"zone-{i + 1}"

    tier_counts: dict[str, int] = {}
    for cr in cell_results:
        tier_counts[cr.score.tier] = tier_counts.get(cr.score.tier, 0) + 1

    return AnalysisResult(
        profile_id=profile.id, cells=cell_results, zones=zones,
        elimination=elimination, tier_counts=tier_counts, bbox=bbox,
        signature=analysis_signature(profile),
    )


def _default_bbox(profile: Profile) -> list[float]:
    # ~6km half-extent box around the center.
    d = 0.055
    return [profile.center_lon - d, profile.center_lat - d * 0.7,
            profile.center_lon + d, profile.center_lat + d * 0.7]


# --------------------------------------------------------------------------- #
#  Listing scoring
# --------------------------------------------------------------------------- #

@dataclass
class ListingScore:
    listing_id: str
    area: UnitScore
    listing: UnitScore
    combined_fit: float
    combined_tier: str
    matched_zone: Optional[str]
    confidence: float = 0.0


def score_listing(profile: Profile, listing: dict[str, Any],
                  providers: Optional[Providers] = None,
                  analysis: Optional[AnalysisResult] = None) -> ListingScore:
    """Score a single geocoded listing against area + listing criteria.

    ``listing`` must contain ``lat``/``lon`` (geocoded upstream) plus listing
    fields (rent, bedrooms, ...). Area criteria are evaluated at the listing's
    exact location -- not just its containing cell -- for precise routes.
    """
    providers = providers or get_providers()
    bbox = profile.bbox or _default_bbox(profile)
    lat, lon = listing["lat"], listing["lon"]
    layers = {l.id: l for l in profile.layers}

    area_results = [
        evaluate_area_criterion(c, lat, lon, providers, bbox, layers)
        for c in profile.area_criteria()
    ]
    area_score = aggregate(area_results)

    listing_criteria = profile.listing_criteria()
    listing_results = [evaluate_listing_criterion(c, listing) for c in listing_criteria]
    listing_agg = aggregate(listing_results)

    # Combined: both hard gates must pass; combined preference = mean of whichever
    # sub-scores actually have criteria (don't dilute area with an empty listing
    # score, or vice versa). Ineligible if either hard gate fails.
    both_hard = area_score.hard_passed and listing_agg.hard_passed
    if both_hard:
        parts = []
        if profile.area_criteria():
            parts.append(area_score.fit_score)
        if listing_criteria:
            parts.append(listing_agg.fit_score)
        combined = sum(parts) / len(parts) if parts else 0.0
        if combined >= 80:
            tier = Tier.STRONG_FIT
        elif combined >= 55:
            tier = Tier.QUALIFYING
        else:
            tier = Tier.BORDERLINE
    else:
        combined = 0.0
        tier = Tier.INELIGIBLE

    matched_zone = None
    if analysis:
        for z in analysis.zones:
            if (z["min_lat"] <= lat <= z["max_lat"]
                    and z["min_lon"] <= lon <= z["max_lon"]):
                matched_zone = z["zone_id"]
                break

    confidence = round((area_score.confidence + listing_agg.confidence) / 2.0, 2)
    return ListingScore(
        listing_id=str(listing.get("id", "")), area=area_score, listing=listing_agg,
        combined_fit=round(combined, 1), combined_tier=tier, matched_zone=matched_zone,
        confidence=confidence,
    )
