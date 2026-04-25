from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from koh.api.deps import get_current_user, get_db
from koh.db.models import GameMap, MapTemplate, Match, Replay, Round, Submission, User
from koh.site_config import get_or_create_site_config

router = APIRouter(tags=["matches"])


def _display_name(user: User) -> str:
    return user.public_name


def _submission_model_id(submission: Submission | None) -> str | None:
    return submission.file_hash if submission is not None else None


def _effective_submission(
    db: Session, round_id: int, user_id: int, role: str
) -> Submission | None:
    return (
        db.query(Submission)
        .filter(
            Submission.user_id == user_id,
            Submission.role == role,
            or_(Submission.round_id.is_(None), Submission.round_id <= round_id),
        )
        .order_by(Submission.uploaded_at.desc())
        .first()
    )


def _can_view_match(db: Session, current_user: User, row: Match) -> bool:
    site_cfg = get_or_create_site_config(db)
    if site_cfg.phase != "test":
        return True
    return current_user.is_admin


@router.get("/matches/{match_id}")
def get_match(
    match_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(Match).filter(Match.id == match_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="match not found")
    if not _can_view_match(db, current_user, row):
        raise HTTPException(status_code=404, detail="match not found")

    users = db.query(User).filter(User.id.in_([row.team_a_id, row.team_b_id])).all()
    user_name_by_id = {user.id: _display_name(user) for user in users}

    game_map = db.query(GameMap).filter(GameMap.id == row.map_id).first() if row.map_id else None
    map_template = (
        db.query(MapTemplate).filter(MapTemplate.id == game_map.template_id).first()
        if game_map and game_map.template_id
        else None
    )
    map_name: str | None = map_template.name if map_template else (game_map.seed if game_map else None)
    map_idx: int | None = game_map.map_idx if game_map else None

    result_json = row.result_json or {}
    team_a_role = str(result_json.get("team_a_role", "attack")).lower()
    if team_a_role not in {"attack", "defense"}:
        team_a_role = "attack"
    team_b_role = "defense" if team_a_role == "attack" else "attack"

    team_a_submission = _effective_submission(
        db, row.round_id, row.team_a_id, team_a_role
    )
    team_b_submission = _effective_submission(
        db, row.round_id, row.team_b_id, team_b_role
    )

    return {
        "ok": True,
        "data": {
            "id": row.id,
            "round_id": row.round_id,
            "map_id": row.map_id,
            "map_idx": map_idx,
            "map_name": map_name,
            "team_a_id": row.team_a_id,
            "team_a_name": user_name_by_id.get(row.team_a_id),
            "team_b_id": row.team_b_id,
            "team_b_name": user_name_by_id.get(row.team_b_id),
            "status": row.status,
            "result": row.result_json,
            "team_a_model": {
                "role": team_a_role,
                "model_id": _submission_model_id(team_a_submission),
            },
            "team_b_model": {
                "role": team_b_role,
                "model_id": _submission_model_id(team_b_submission),
            },
        },
    }


@router.get("/matches/{match_id}/replay")
def get_replay(
    match_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    match_row = db.query(Match).filter(Match.id == match_id).first()
    if match_row is None:
        raise HTTPException(status_code=404, detail="match not found")
    if not _can_view_match(db, current_user, match_row):
        raise HTTPException(status_code=404, detail="replay not found")

    replay_row = db.query(Replay).filter(Replay.match_id == match_id).first()
    if replay_row is None:
        raise HTTPException(status_code=404, detail="replay not found")
    path = Path(replay_row.frames_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="replay file missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"ok": True, "data": data}
