from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from koh.api.deps import get_current_user, get_db
from koh.db.models import ScoreHistory, User
from koh.site_config import get_or_create_site_config

router = APIRouter(tags=["users"])


def _score_history_payload(username: str, db: Session):
    user = (
        db.query(User)
        .filter(or_(User.username == username, User.display_name == username))
        .first()
    )
    if user is None:
        return {"ok": True, "data": []}

    site_cfg = get_or_create_site_config(db)
    if site_cfg.phase == "test":
        return {"ok": True, "data": []}

    rows = (
        db.query(ScoreHistory)
        .filter(ScoreHistory.user_id == user.id)
        .order_by(ScoreHistory.round_id.asc())
        .all()
    )
    return {
        "ok": True,
        "data": [
            {
                "round_id": row.round_id,
                "score_before": row.score_before,
                "score_after": row.score_after,
                "delta": row.delta,
            }
            for row in rows
        ],
    }


@router.get("/users/{username}/score-history")
def score_history(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _score_history_payload(username, db)


@router.get("/public/users/{username}/score-history")
def public_score_history(username: str, db: Session = Depends(get_db)):
    return _score_history_payload(username, db)
