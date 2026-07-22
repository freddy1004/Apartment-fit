"""Apartment Fit FastAPI application."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import SessionLocal, init_db
from .routers import (
    analysis_router,
    auth_router,
    criteria_router,
    listings_router,
    profiles_router,
)

log = logging.getLogger("apartment_fit")


async def _alert_scheduler(interval_s: int):
    """Periodically run saved-search alerts. Disabled unless ALERT_INTERVAL_SECONDS>0."""
    from .alerts import run_all_alerts
    while True:
        await asyncio.sleep(interval_s)
        try:
            db = SessionLocal()
            try:
                results = run_all_alerts(db)
                notified = sum(r.get("notified", 0) for r in results)
                if notified:
                    log.info("scheduled alerts: notified %d new match(es)", notified)
            finally:
                db.close()
        except Exception as e:  # noqa: BLE001
            log.warning("alert scheduler error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    interval = int(os.getenv("ALERT_INTERVAL_SECONDS", "0"))
    task = None
    if interval > 0:
        task = asyncio.create_task(_alert_scheduler(interval))
        log.info("alert scheduler enabled (every %ds)", interval)
    try:
        yield
    finally:
        if task:
            task.cancel()


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

# Allow any origin: the browser calls the API directly (localhost:3000 ->
# localhost:8000, Codespaces URLs, etc.). Auth is header-based (bearer tokens),
# not cookies, so credentials aren't needed and a wildcard origin is safe here.
_cors_all = settings.cors_origins == ["*"] or "*" in settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _cors_all else settings.cors_origins,
    allow_origin_regex=None if _cors_all else r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=not _cors_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(criteria_router.router)
app.include_router(profiles_router.router)
app.include_router(analysis_router.router)
app.include_router(listings_router.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.version,
        "provider_mode": settings.provider_mode,
    }
