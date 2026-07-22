"""Authentication endpoints (used when AUTH_ENABLED=true)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import Principal, current_user, register_user
from ..config import settings
from ..db import get_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: str


@router.get("/status")
def status():
    return {"auth_enabled": settings.auth_enabled}


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_session)):
    """Create (or fetch) a user and return their bearer token."""
    principal, token = register_user(db, body.email)
    return {"user_id": principal.id, "email": principal.email, "token": token}


@router.get("/me")
def me(user: Principal = Depends(current_user)):
    return {"user_id": user.id, "email": user.email}
