from __future__ import annotations

from datetime import datetime

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from koh.cache import get_cached_token, set_cached_token
from koh.db.models import Session as UserSession
from koh.db.models import User
from koh.db.session import SessionLocal
from koh.security import utc_now


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="authentication required")
    token = authorization.split(" ", 1)[1].strip()

    cached = await get_cached_token(token)
    if cached:
        return User(
            id=cached["id"],
            username=cached["username"],
            display_name=cached.get("display_name"),
            password_hash=cached["password_hash"],
            is_admin=cached["is_admin"],
            is_active=cached["is_active"],
            is_agent=cached["is_agent"],
            is_spectator=cached["is_spectator"],
            agent_name=cached.get("agent_name"),
            model_name=cached.get("model_name"),
            score=cached["score"],
            created_at=datetime.fromisoformat(cached["created_at"]),
        )

    # Cache miss: query DB, then immediately release the connection
    with SessionLocal() as db:
        session = db.query(UserSession).filter(UserSession.token == token).first()
        if not session or session.expires_at <= utc_now().replace(tzinfo=None):
            raise HTTPException(status_code=401, detail="invalid or expired token")
        user = (
            db.query(User)
            .filter(User.id == session.user_id, User.is_active.is_(True))
            .first()
        )
        if not user:
            raise HTTPException(status_code=401, detail="user not available")
        user_data = {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "password_hash": user.password_hash,
            "is_admin": user.is_admin,
            "is_active": user.is_active,
            "is_agent": user.is_agent,
            "is_spectator": user.is_spectator,
            "agent_name": user.agent_name,
            "model_name": user.model_name,
            "score": user.score,
            "created_at": user.created_at.isoformat(),
        }
        session_expires = session.expires_at

    remaining = int((session_expires - utc_now().replace(tzinfo=None)).total_seconds())
    ttl = min(60, max(1, remaining))
    await set_cached_token(token, user_data, ttl)

    return User(**user_data | {"created_at": datetime.fromisoformat(user_data["created_at"])})


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin privilege required")
    return user
