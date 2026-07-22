"""Saved-search matching + alerting foundation.

A profile *is* a saved search: its hard requirements define what "matches". This
module finds stored listings that satisfy every hard requirement (area + listing)
and routes them through a pluggable Notifier so new matches can trigger alerts.
The default notifier logs; swap in email/push/webhook implementations later.
"""
from __future__ import annotations

import abc
import logging
from typing import Any, Optional

from ..analysis.engine import AnalysisResult, score_listing
from ..criteria.schema import Profile
from ..providers.registry import Providers

log = logging.getLogger("apartment_fit.alerts")


class Notifier(abc.ABC):
    @abc.abstractmethod
    def notify(self, profile: Profile, matches: list[dict]) -> None:
        ...


class LoggingNotifier(Notifier):
    def notify(self, profile: Profile, matches: list[dict]) -> None:
        for m in matches:
            log.info("ALERT profile=%s listing=%s fit=%s tier=%s",
                     profile.id, m["listing_id"], m["combined_fit"], m["combined_tier"])


def find_matches(
    profile: Profile, listings: list[dict], providers: Providers,
    analysis: Optional[AnalysisResult] = None,
) -> list[dict]:
    """Return listings that pass every hard requirement (not ineligible)."""
    out: list[dict] = []
    for li in listings:
        if li.get("lat") is None or li.get("lon") is None:
            continue
        sc = score_listing(profile, li, providers, analysis)
        if sc.area.hard_passed and sc.listing.hard_passed:
            out.append({
                "listing_id": sc.listing_id,
                "address": li.get("address", ""),
                "combined_fit": sc.combined_fit,
                "combined_tier": sc.combined_tier,
                "matched_zone": sc.matched_zone,
            })
    out.sort(key=lambda m: m["combined_fit"], reverse=True)
    return out


def run_alerts(
    profile: Profile, listings: list[dict], providers: Providers,
    analysis: Optional[AnalysisResult] = None, notifier: Optional[Notifier] = None,
) -> list[dict]:
    matches = find_matches(profile, listings, providers, analysis)
    (notifier or LoggingNotifier()).notify(profile, matches)
    return matches
