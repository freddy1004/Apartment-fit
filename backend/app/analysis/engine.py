"""City-area analysis and listing scoring orchestration."""
from __future__ import annotations

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

    def qualifying_cells(self) -> list[Cell]:
        return [cr.cell for cr in self.cells
                if cr.score.tier in (Tier.STRONG_FIT, Tier.QUALIFYING, Tier.BORDERLINE)]


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

    cell_results: list[CellResult] = []
    # Track per-hard-criterion elimination.
    fail_counts: dict[str, int] = {c.id: 0 for c in area_criteria if c.kind == Kind.HARD}
    sole_fail: dict[str, int] = {c.id: 0 for c in area_criteria if c.kind == Kind.HARD}
    labels = {c.id: c.label for c in area_criteria}

    for cell in cells:
        results = [
            evaluate_area_criterion(c, cell.center_lat, cell.center_lon, providers, bbox)
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
    qualifying = [cr.cell for cr in cell_results if cr.score.hard_passed]
    clusters = group_contiguous(qualifying)
    zones = []
    for i, cluster in enumerate(clusters):
        b = cluster_bounds(cluster)
        avg_fit = sum(
            next(cr.score.fit_score for cr in cell_results if cr.cell.id == c.id)
            for c in cluster
        ) / len(cluster)
        zones.append({
            "zone_id": f"zone-{i + 1}",
            **b,
            "avg_fit_score": round(avg_fit, 1),
            "nearby_neighborhoods": _nearest_neighborhoods(b["centroid_lat"], b["centroid_lon"]),
            "cell_ids": [c.id for c in cluster],
        })

    tier_counts: dict[str, int] = {}
    for cr in cell_results:
        tier_counts[cr.score.tier] = tier_counts.get(cr.score.tier, 0) + 1

    return AnalysisResult(
        profile_id=profile.id, cells=cell_results, zones=zones,
        elimination=elimination, tier_counts=tier_counts, bbox=bbox,
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

    area_results = [
        evaluate_area_criterion(c, lat, lon, providers, bbox)
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

    return ListingScore(
        listing_id=str(listing.get("id", "")), area=area_score, listing=listing_agg,
        combined_fit=round(combined, 1), combined_tier=tier, matched_zone=matched_zone,
    )
