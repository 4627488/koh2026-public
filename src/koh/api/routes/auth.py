from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from koh.api.deps import get_current_user, get_db
from koh.cache import invalidate_cached_token
from koh.db.models import RegistrationInvite
from koh.db.models import Session as UserSession
from koh.db.models import User
from koh.registration_invites import (
    is_registration_invite_valid,
    serialize_registration_invite,
)
from koh.security import (
    hash_password,
    new_token,
    token_expiry,
    utc_now,
    verify_password,
)
from koh.site_config import get_or_create_site_config, serialize_site_config

router = APIRouter(tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    invite_token: str | None = None


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)


@router.post("/auth/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    site_config = get_or_create_site_config(db)
    invite_token = (payload.invite_token or "").strip()
    invite: RegistrationInvite | None = None
    if invite_token:
        invite = (
            db.query(RegistrationInvite)
            .filter(RegistrationInvite.token == invite_token)
            .first()
        )
        if invite is None or not is_registration_invite_valid(invite):
            raise HTTPException(status_code=400, detail="invite link is invalid or exhausted")

    if not site_config.allow_registration and invite is None:
        raise HTTPException(status_code=403, detail="registration is disabled")

    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="username already exists")
    now = utc_now().replace(tzinfo=None)
    user = User(
        username=payload.username,
        display_name=payload.username,
        password_hash=hash_password(payload.password),
        is_admin=False,
        is_active=True,
        score=0.0,
        created_at=now,
    )
    if invite is not None:
        invite.used_count += 1
        invite.updated_at = now
    db.add(user)
    db.commit()
    return {"ok": True, "data": {"username": payload.username}}


@router.get("/auth/register-status")
def register_status(db: Session = Depends(get_db)):
    row = get_or_create_site_config(db)
    return {"ok": True, "data": serialize_site_config(row)}


@router.get("/auth/invite-status")
def invite_status(token: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    row = (
        db.query(RegistrationInvite)
        .filter(RegistrationInvite.token == token.strip())
        .first()
    )
    if row is None:
        return {
            "ok": True,
            "data": {
                "token": token,
                "valid": False,
                "revoked": False,
                "max_uses": 0,
                "used_count": 0,
                "remaining_uses": 0,
                "created_by_user_id": None,
                "created_at": None,
                "updated_at": None,
            },
        }
    return {"ok": True, "data": serialize_registration_invite(row)}


@router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .filter(User.username == payload.username, User.is_active.is_(True))
        .first()
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = new_token()
    expires_at: datetime = token_expiry().replace(tzinfo=None)
    db.add(UserSession(token=token, user_id=user.id, expires_at=expires_at))
    db.commit()
    return {"ok": True, "data": {"token": token, "expires_at": expires_at.isoformat()}}


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return {
        "ok": True,
        "data": {
            "id": user.id,
            "username": user.username,
            "display_name": user.public_name,
            "is_admin": user.is_admin,
            "score": user.score,
        },
    }


@router.post("/auth/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=400, detail="new password must be different from current password"
        )

    # Explicit update: user may be a transient (cache-reconstructed) object
    db.query(User).filter(User.id == user.id).update(
        {"password_hash": hash_password(payload.new_password)},
        synchronize_session=False,
    )
    db.query(UserSession).filter(UserSession.user_id == user.id).delete(
        synchronize_session=False
    )
    token = new_token()
    expires_at: datetime = token_expiry().replace(tzinfo=None)
    db.add(UserSession(token=token, user_id=user.id, expires_at=expires_at))
    db.commit()

    if authorization and authorization.startswith("Bearer "):
        old_token = authorization.split(" ", 1)[1].strip()
        await invalidate_cached_token(old_token)

    return {"ok": True, "data": {"token": token, "expires_at": expires_at.isoformat()}}
