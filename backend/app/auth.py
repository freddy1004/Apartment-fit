"""Opt-in bearer-token auth and per-user ownership.

When ``AUTH_ENABLED`` is false (default) every request maps to the shared
``public`` owner and no token is needed -- local dev, the demo, and the test
suite work with zero friction. When enabled, requests must carry
``Authorization: Bearer <token>`` and are scoped to the owning user.
"""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import settings
from .db import UserRow, get_session


@dataclass
class Principal:
    id: str
    email: str = ""


def _token_from_header(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_session),
) -> Principal:
    if not settings.auth_enabled:
        return Principal(id=settings.public_owner, email="public@local")
    token = _token_from_header(authorization)
    if not token:
        raise HTTPException(401, "missing bearer token")
    row = db.query(UserRow).filter(UserRow.token == token).first()
    if not row:
        raise HTTPException(401, "invalid token")
    return Principal(id=row.id, email=row.email)


def register_user(db: Session, email: str) -> tuple[Principal, str]:
    existing = db.query(UserRow).filter(UserRow.email == email).first()
    if existing:
        return Principal(id=existing.id, email=existing.email), existing.token
    uid = f"user-{uuid.uuid4().hex[:10]}"
    token = secrets.token_urlsafe(24)
    db.add(UserRow(id=uid, email=email, token=token))
    db.commit()
    return Principal(id=uid, email=email), token
