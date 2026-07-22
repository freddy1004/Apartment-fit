"""Database layer.

Profiles and listings are persisted as JSON documents in a single table each.
This keeps the schema portable across SQLite (tests / zero-setup) and
PostgreSQL+PostGIS (Docker stack) while the geospatial *computation* lives in
Python. PostGIS is available in the stack for future spatial queries and tiles.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


class ProfileRow(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    city: Mapped[str] = mapped_column(String, default="")
    owner_id: Mapped[str] = mapped_column(String, index=True, default="public")
    data: Mapped[dict] = mapped_column(JSON)  # serialized Profile


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, index=True, default="")
    token: Mapped[str] = mapped_column(String, index=True, default="")


class ListingRow(Base):
    __tablename__ = "listings"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    profile_id: Mapped[str] = mapped_column(String, index=True)
    data: Mapped[dict] = mapped_column(JSON)  # normalized listing dict


class AlertStateRow(Base):
    """Tracks which matching listings a profile has already alerted on."""
    __tablename__ = "alert_state"
    profile_id: Mapped[str] = mapped_column(String, primary_key=True)
    seen_listing_ids: Mapped[list] = mapped_column(JSON, default=list)
    last_run: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc))


class SnapshotRow(Base):
    """A persisted area-analysis run, keyed by profile + criteria signature."""
    __tablename__ = "analysis_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(String, index=True)
    signature: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc))
    summary: Mapped[dict] = mapped_column(JSON)  # tier_counts, elimination, zones, bbox


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
