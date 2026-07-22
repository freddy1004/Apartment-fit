"""Runtime configuration via environment variables."""
from __future__ import annotations

import os


class Settings:
    # SQLite by default (works everywhere, incl. tests); Postgres/PostGIS in Docker.
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./apartment_fit.db")
    # auto = live OSM services where reachable (Overpass POIs by default), else
    # bundled offline data. fixture = always offline. osm = force live services.
    provider_mode: str = os.getenv("PROVIDER_MODE", "auto")  # auto | fixture | osm
    cors_origins: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    app_name: str = "Apartment Fit"
    version: str = "0.1.0"
    # Opt-in multi-user auth. When false (default), everything belongs to a
    # single "public" workspace and no token is required -- keeps local/demo use
    # and tests zero-friction.
    auth_enabled: bool = os.getenv("AUTH_ENABLED", "false").lower() in ("1", "true", "yes")

    @property
    def public_owner(self) -> str:
        return "public"


settings = Settings()
