"""Saved-search matching + alerting foundation.

A profile *is* a saved search: its hard requirements define what "matches". This
module finds stored listings that satisfy every hard requirement (area + listing)
and routes them through a pluggable Notifier so new matches can trigger alerts.
The default notifier logs; swap in email/push/webhook implementations later.
"""
from __future__ import annotations

import abc
import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Any, Callable, Optional

from ..analysis.engine import AnalysisResult, score_listing
from ..criteria.schema import Profile
from ..providers.registry import Providers

log = logging.getLogger("apartment_fit.alerts")


class Notifier(abc.ABC):
    @abc.abstractmethod
    def notify(self, profile: Profile, matches: list[dict]) -> None:
        ...


class LoggingNotifier(Notifier):
    """Default: writes alerts to the application log / console."""

    def notify(self, profile: Profile, matches: list[dict]) -> None:
        for m in matches:
            log.info("ALERT profile=%s listing=%s fit=%s tier=%s",
                     profile.id, m["listing_id"], m["combined_fit"], m["combined_tier"])


class WebhookNotifier(Notifier):
    """POSTs a JSON payload to a configured URL (Slack/Zapier/custom endpoint)."""

    def __init__(self, url: str, poster: Optional[Callable] = None):
        self.url = url
        self._poster = poster  # injectable for tests; defaults to httpx.post

    def notify(self, profile: Profile, matches: list[dict]) -> None:
        if not matches:
            return
        payload = {"profile_id": profile.id, "profile_name": profile.name,
                   "match_count": len(matches), "matches": matches}
        poster = self._poster
        if poster is None:
            import httpx
            poster = lambda url, json: httpx.post(url, json=json, timeout=10)  # noqa: E731
        try:
            poster(self.url, payload)
        except Exception as e:  # noqa: BLE001
            log.warning("webhook notify failed: %s", e)


class EmailNotifier(Notifier):
    """Sends alert emails via SMTP. Falls back to logging if SMTP is unconfigured."""

    def __init__(self, host: str = "", port: int = 587, user: str = "",
                 password: str = "", sender: str = "", to: str = ""):
        self.host, self.port = host, port
        self.user, self.password = user, password
        self.sender, self.to = sender or user, to

    def notify(self, profile: Profile, matches: list[dict]) -> None:
        if not matches:
            return
        if not (self.host and self.to):
            log.info("EmailNotifier not configured; %d match(es) for %s not emailed",
                     len(matches), profile.id)
            return
        msg = EmailMessage()
        msg["Subject"] = f"Apartment Fit: {len(matches)} new match(es) for {profile.name}"
        msg["From"], msg["To"] = self.sender, self.to
        lines = [f"- {m['address'] or m['listing_id']}: fit {m['combined_fit']} "
                 f"({m['combined_tier']})" for m in matches]
        msg.set_content("New listings matching your saved search:\n\n" + "\n".join(lines))
        try:
            with smtplib.SMTP(self.host, self.port, timeout=15) as s:
                s.starttls()
                if self.user:
                    s.login(self.user, self.password)
                s.send_message(msg)
        except Exception as e:  # noqa: BLE001
            log.warning("email notify failed: %s", e)


def build_notifier() -> Notifier:
    """Select a notifier from environment configuration."""
    kind = os.getenv("ALERT_NOTIFIER", "console").lower()
    if kind == "webhook":
        return WebhookNotifier(os.getenv("ALERT_WEBHOOK_URL", ""))
    if kind == "email":
        return EmailNotifier(
            host=os.getenv("SMTP_HOST", ""), port=int(os.getenv("SMTP_PORT", "587")),
            user=os.getenv("SMTP_USER", ""), password=os.getenv("SMTP_PASSWORD", ""),
            sender=os.getenv("ALERT_EMAIL_FROM", ""), to=os.getenv("ALERT_EMAIL_TO", ""))
    return LoggingNotifier()


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
