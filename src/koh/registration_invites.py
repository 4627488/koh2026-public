from __future__ import annotations

from sqlalchemy.orm import Session

from koh.db.models import RegistrationInvite
from koh.security import new_token, utc_now


def is_registration_invite_valid(row: RegistrationInvite) -> bool:
    return (not row.revoked) and row.used_count < row.max_uses


def serialize_registration_invite(row: RegistrationInvite) -> dict:
    remaining_uses = max(0, row.max_uses - row.used_count)
    return {
        "id": row.id,
        "token": row.token,
        "max_uses": row.max_uses,
        "used_count": row.used_count,
        "remaining_uses": remaining_uses,
        "revoked": row.revoked,
        "valid": is_registration_invite_valid(row),
        "created_by_user_id": row.created_by_user_id,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def create_registration_invite(
    db: Session, *, created_by_user_id: int, max_uses: int
) -> RegistrationInvite:
    now = utc_now().replace(tzinfo=None)
    row = RegistrationInvite(
        token=new_token(),
        max_uses=max(1, int(max_uses)),
        used_count=0,
        revoked=False,
        created_by_user_id=created_by_user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
