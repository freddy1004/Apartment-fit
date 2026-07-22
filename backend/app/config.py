"""Runtime configuration via environment variables."""
from __future__ import annotations

import os


class Settings:
    # SQLite by default (works everywhere, incl. tests); Postgres/PostGIS in Docker.
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./apartment_fit.db")
    provider_mode: str = os.getenv("PROVIDER_MODE", "fixture")  # fixture | osm | auto
    cors_origins: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    app_name: str = "Apartment Fit"
    version: str = "0.1.0"


settings = Settings()
