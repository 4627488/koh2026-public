from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from koh.api.deps import get_admin_user, get_db
from koh.auto_round import (
    get_or_create_auto_round_config,
    serialize_auto_round_config,
    touch_auto_round_updated_at,
)
from koh.db.models import (
    AgentTelemetry,
    Baseline,
    BPPreference,
    GameMap,
    MapTemplate,
    Match,
    RegistrationInvite,
    Replay,
    Round,
    ScoreHistory,
    Session as UserSession,
    Submission,
    User,
)
from koh.game.map_pool import (
    MapFormatError,
    create_or_update_map_template,
    ensure_round_maps,
    list_map_templates,
)
from koh.registration_invites import (
    create_registration_invite,
    serialize_registration_invite,
)
from koh.security import hash_password, new_password, utc_now
from koh.site_config import (
    get_or_create_site_config,
    normalize_announcement_body,
    normalize_announcement_title,
    publish_announcement_event,
    serialize_site_config,
    touch_site_config_updated_at,
)
from koh.tasks.celery_app import celery_app

router = APIRouter(tags=["admin"])


# ── rounds ────────────────────────────────────────────────────


class CreateRoundRequest(BaseModel):
    auto_run: bool = True  # kept for API compat; always runs immediately


@router.post("/admin/rounds")
def create_round(
    payload: CreateRoundRequest,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    site_cfg = get_or_create_site_config(db)
    if site_cfg.phase == "test":
        raise HTTPException(status_code=409, detail="test phase does not use rounds")

    now = utc_now().replace(tzinfo=None)
    row = Round(
        status="running",
        strategy_opens_at=now,
        strategy_closes_at=now,
        created_mode="manual",
        auto_slot_start=None,
        created_at=now,
    )
    db.add(row)
    try:
        db.flush()
        ensure_round_maps(db, row.id)
        db.commit()
    except MapFormatError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(row)
    _start_round(row.id)
    return {"ok": True, "data": {"id": row.id, "status": row.status}}


def _start_round(round_id: int) -> None:
    celery_app.send_task("koh.tasks.close_strategy_window", args=[round_id])
    celery_app.send_task("koh.tasks.watch_and_finalize", args=[round_id], countdown=5)


def _recompute_scores_for_users(db: Session, user_ids: set[int]) -> None:
    if not user_ids:
        return

    users = db.query(User).filter(User.id.in_(list(user_ids))).all()
    history_rows = (
        db.query(ScoreHistory)
        .filter(ScoreHistory.user_id.in_(list(user_ids)))
        .order_by(ScoreHistory.user_id.asc(), ScoreHistory.round_id.asc(), ScoreHistory.id.asc())
        .all()
    )
    history_by_user: dict[int, list[ScoreHistory]] = {}
    for history in history_rows:
        history_by_user.setdefault(history.user_id, []).append(history)
    for user in users:
        running = 0.0
        for history in history_by_user.get(user.id, []):
            history.score_before = running
            running += history.delta
            history.score_after = running
        user.score = running


def _delete_round_replay_files(match_ids: list[int]) -> None:
    replay_dir = Path(os.getenv("KOH_DATA_DIR", "data")) / "replays"
    for match_id in match_ids:
        replay_path = replay_dir / f"match_{match_id}.json"
        try:
            if replay_path.is_file():
                replay_path.unlink()
        except OSError:
            pass


class AutoRoundConfigRequest(BaseModel):
    enabled: bool
    interval_minutes: int
    competition_starts_at: datetime | None = None
    competition_ends_at: datetime | None = None


class SiteConfigRequest(BaseModel):
    allow_registration: bool
    phase: str = "competition"
    announcement_title: str = Field(default="")
    announcement_body: str = Field(default="")


class CreateRegistrationInviteRequest(BaseModel):
    max_uses: int = 1


class BulkImportUsersRequest(BaseModel):
    text: str = Field(..., min_length=1)
    dry_run: bool = False


def _user_display_name(user: User) -> str:
    return user.public_name


class MapTemplateRequest(BaseModel):
    name: str
    source_text: str
    sort_order: int = 0
    difficulty: float = 0.5
    is_active: bool = True


class CreateBaselineRequest(BaseModel):
    display_name: str
    attack_submission_id: int
    defense_submission_id: int
    sort_order: int = 0
    is_active: bool = True


class UpdateBaselineRequest(BaseModel):
    display_name: str
    sort_order: int = 0
    is_active: bool = True


def _serialize_map_template(row: MapTemplate) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "source_text": row.source_text,
        "layout": row.layout_json,
        "sort_order": row.sort_order,
        "difficulty": row.difficulty,
        "is_active": row.is_active,
        "created_by_user_id": row.created_by_user_id,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.get("/admin/auto-round")
def get_auto_round_config(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    row = get_or_create_auto_round_config(db)
    return {"ok": True, "data": serialize_auto_round_config(row)}


@router.get("/admin/site-config")
def get_site_config(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    row = get_or_create_site_config(db)
    return {"ok": True, "data": serialize_site_config(row)}


@router.get("/admin/registration-invites")
def list_registration_invites(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(RegistrationInvite)
        .order_by(RegistrationInvite.id.desc())
        .limit(100)
        .all()
    )
    return {"ok": True, "data": [serialize_registration_invite(row) for row in rows]}


@router.get("/admin/maps")
def admin_list_maps(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    rows = list_map_templates(db, active_only=False)
    return {"ok": True, "data": [_serialize_map_template(row) for row in rows]}


@router.post("/admin/maps")
def admin_create_map(
    payload: MapTemplateRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        row = create_or_update_map_template(
            db,
            name=payload.name,
            source_text=payload.source_text,
            sort_order=int(payload.sort_order),
            difficulty=float(payload.difficulty),
            is_active=bool(payload.is_active),
            created_by_user_id=admin.id,
        )
    except MapFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(row)
    return {"ok": True, "data": _serialize_map_template(row)}


@router.put("/admin/maps/{map_id}")
def admin_update_map(
    map_id: int,
    payload: MapTemplateRequest,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    row = db.query(MapTemplate).filter(MapTemplate.id == map_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="map not found")
    try:
        row = create_or_update_map_template(
            db,
            name=payload.name,
            source_text=payload.source_text,
            sort_order=int(payload.sort_order),
            difficulty=float(payload.difficulty),
            is_active=bool(payload.is_active),
            created_by_user_id=row.created_by_user_id,
            template=row,
        )
    except MapFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(row)
    return {"ok": True, "data": _serialize_map_template(row)}


@router.delete("/admin/maps/{map_id}")
def admin_delete_map(
    map_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    row = db.query(MapTemplate).filter(MapTemplate.id == map_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="map not found")
    in_use = db.query(GameMap.id).filter(GameMap.template_id == map_id).first()
    if in_use:
        raise HTTPException(
            status_code=400,
            detail="地图已被历史轮次使用，请改为停用而非删除",
        )
    db.delete(row)
    db.commit()
    return {"ok": True, "data": {"deleted_map_id": map_id}}


@router.post("/admin/maps/upload")
async def admin_upload_maps(
    files: List[UploadFile] = File(...),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    created = []
    errors = []
    for upload in files:
        try:
            raw = await upload.read()
            text = raw.decode("utf-8", errors="replace")
            name = Path(upload.filename or "map").stem
            row = create_or_update_map_template(
                db,
                name=name,
                source_text=text,
                sort_order=0,
                difficulty=0.5,
                is_active=True,
                created_by_user_id=admin.id,
            )
            created.append(_serialize_map_template(row))
        except MapFormatError as exc:
            errors.append({"filename": upload.filename, "error": str(exc)})
    db.commit()
    return {"ok": True, "data": {"created": created, "errors": errors}}


@router.post("/admin/registration-invites")
def create_invite(
    payload: CreateRegistrationInviteRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    row = create_registration_invite(
        db,
        created_by_user_id=admin.id,
        max_uses=max(1, min(10_000, int(payload.max_uses))),
    )
    return {"ok": True, "data": serialize_registration_invite(row)}


@router.post("/admin/registration-invites/{invite_id}/revoke")
def revoke_invite(
    invite_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    row = db.query(RegistrationInvite).filter(RegistrationInvite.id == invite_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="invite not found")
    row.revoked = True
    row.updated_at = utc_now().replace(tzinfo=None)
    db.commit()
    db.refresh(row)
    return {"ok": True, "data": serialize_registration_invite(row)}


@router.post("/admin/site-config")
def update_site_config(
    payload: SiteConfigRequest,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    row = get_or_create_site_config(db)
    announcement_title = normalize_announcement_title(payload.announcement_title)
    announcement_body = normalize_announcement_body(payload.announcement_body)
    announcement_changed = (
        announcement_title != (row.announcement_title or "")
        or announcement_body != (row.announcement_body or "")
    )
    row.allow_registration = bool(payload.allow_registration)
    row.phase = payload.phase if payload.phase in ("test", "competition") else "competition"
    row.announcement_title = announcement_title
    row.announcement_body = announcement_body
    if announcement_changed:
        row.announcement_updated_at = utc_now().replace(tzinfo=None)
    touch_site_config_updated_at(row)
    db.commit()
    db.refresh(row)
    if announcement_changed:
        publish_announcement_event("announcement_updated", serialize_site_config(row))
    return {"ok": True, "data": serialize_site_config(row)}


@router.post("/admin/auto-round")
def update_auto_round_config(
    payload: AutoRoundConfigRequest,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    row = get_or_create_auto_round_config(db)
    row.enabled = bool(payload.enabled)
    row.interval_minutes = max(1, min(1440, int(payload.interval_minutes)))
    row.competition_starts_at = (
        payload.competition_starts_at.astimezone(timezone.utc).replace(tzinfo=None)
        if payload.competition_starts_at is not None and payload.competition_starts_at.tzinfo is not None
        else payload.competition_starts_at
    )
    row.competition_ends_at = (
        payload.competition_ends_at.astimezone(timezone.utc).replace(tzinfo=None)
        if payload.competition_ends_at is not None and payload.competition_ends_at.tzinfo is not None
        else payload.competition_ends_at
    )
    if (row.competition_starts_at is None) != (row.competition_ends_at is None):
        raise HTTPException(status_code=400, detail="competition start and end time must both be set or both be empty")
    if (
        row.competition_starts_at is not None
        and row.competition_ends_at is not None
        and row.competition_ends_at <= row.competition_starts_at
    ):
        raise HTTPException(status_code=400, detail="competition end time must be later than start time")
    touch_auto_round_updated_at(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "data": serialize_auto_round_config(row)}


@router.post("/admin/auto-round/trigger")
def trigger_auto_round_once(
    _: User = Depends(get_admin_user),
):
    task = celery_app.send_task("koh.tasks.auto_round_tick", kwargs={"force": True})
    return {
        "ok": True,
        "data": {
            "task": "auto_round_tick",
            "task_id": task.id,
        },
    }


@router.post("/admin/rounds/{round_id}/pipeline")
def admin_pipeline(
    round_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Start the full pipeline for an existing round."""
    row = db.query(Round).filter(Round.id == round_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="round not found")
    if row.created_mode == "test":
        raise HTTPException(status_code=409, detail="test phase does not use rounds")
    _start_round(round_id)
    return {"ok": True, "data": {"round_id": round_id, "task": "start_round"}}


@router.get("/admin/rounds")
def list_rounds(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    rows = db.query(Round).order_by(Round.id.desc()).limit(50).all()
    return {
        "ok": True,
        "data": [
            {
                "id": r.id,
                "status": r.status,
                "created_mode": r.created_mode,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.post("/admin/rounds/{round_id}/finalize")
def admin_finalize_round(
    round_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    row = db.query(Round).filter(Round.id == round_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="round not found")
    celery_app.send_task("koh.tasks.finalize_round", args=[round_id])
    return {"ok": True, "data": {"round_id": round_id, "task": "finalize_round"}}


@router.post("/admin/rounds/{round_id}/rerun")
def admin_rerun_round(
    round_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    row = db.query(Round).filter(Round.id == round_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="round not found")
    if row.created_mode == "test":
        raise HTTPException(status_code=409, detail="test phase does not use rounds")

    active_matches = (
        db.query(Match)
        .filter(Match.round_id == round_id, Match.status.in_(["queued", "running"]))
        .count()
    )
    if active_matches > 0:
        raise HTTPException(status_code=409, detail="round still has active matches")

    match_ids = [match_id for match_id, in db.query(Match.id).filter(Match.round_id == round_id).all()]
    affected_user_ids = {
        user_id
        for user_id, in db.query(ScoreHistory.user_id)
        .filter(ScoreHistory.round_id == round_id)
        .all()
    }

    if match_ids:
        db.query(Replay).filter(Replay.match_id.in_(match_ids)).delete(
            synchronize_session=False
        )
        db.query(Match).filter(Match.id.in_(match_ids)).delete(
            synchronize_session=False
        )

    db.query(ScoreHistory).filter(ScoreHistory.round_id == round_id).delete(
        synchronize_session=False
    )

    row.status = "running"
    _recompute_scores_for_users(db, affected_user_ids)
    db.commit()

    _delete_round_replay_files(match_ids)
    _start_round(round_id)

    return {
        "ok": True,
        "data": {
            "round_id": round_id,
            "task": "rerun_round",
            "deleted_matches": len(match_ids),
        },
    }


@router.delete("/admin/rounds/{round_id}")
def delete_round(
    round_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    row = db.query(Round).filter(Round.id == round_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="round not found")

    # collect submission file paths before deletion
    subs = db.query(Submission).filter(Submission.round_id == round_id).all()
    stored_paths = [s.stored_path for s in subs]

    # cascade delete in dependency order
    match_ids = [m.id for m in db.query(Match.id).filter(Match.round_id == round_id)]
    if match_ids:
        map_ids = [
            m.id for m in db.query(GameMap.id).filter(GameMap.round_id == round_id)
        ]
        db.query(Replay).filter(Replay.match_id.in_(match_ids)).delete(
            synchronize_session=False
        )
        db.query(Match).filter(Match.round_id == round_id).delete(
            synchronize_session=False
        )
        if map_ids:
            db.query(Replay).filter(Replay.map_id.in_(map_ids)).delete(
                synchronize_session=False
            )

    affected_user_ids = {
        user_id
        for user_id, in db.query(ScoreHistory.user_id)
        .filter(ScoreHistory.round_id == round_id)
        .all()
    }

    db.query(ScoreHistory).filter(ScoreHistory.round_id == round_id).delete(
        synchronize_session=False
    )
    db.query(BPPreference).filter(BPPreference.round_id == round_id).delete(
        synchronize_session=False
    )
    db.query(Submission).filter(Submission.round_id == round_id).delete(
        synchronize_session=False
    )
    db.query(GameMap).filter(GameMap.round_id == round_id).delete(
        synchronize_session=False
    )
    db.delete(row)

    _recompute_scores_for_users(db, affected_user_ids)

    db.commit()

    # remove submission files from disk (best-effort)
    for path in stored_paths:
        try:
            if path and os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass

    return {"ok": True, "data": {"deleted_round_id": round_id}}


# ── users ─────────────────────────────────────────────────────


def _serialize_baseline(row: Baseline) -> dict:
    return {
        "id": row.id,
        "display_name": row.display_name,
        "attack_submission_id": row.attack_submission_id,
        "defense_submission_id": row.defense_submission_id,
        "is_active": row.is_active,
        "sort_order": row.sort_order,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _normalize_import_column_name(value: str) -> str:
    return "".join(ch for ch in value.strip().lower() if ch.isalnum())


def _csv_header_index_map(header: list[str]) -> dict[str, int] | None:
    aliases = {
        "team_name": {"队伍", "队名", "team", "teamname", "displayname", "name"},
        "username": {"koh用户名", "用户名", "账号", "账户", "username", "user", "login"},
        "password": {"koh密码", "密码", "password", "pass", "passwd"},
    }
    normalized_header = [_normalize_import_column_name(item) for item in header]
    mapping: dict[str, int] = {}
    for field_name, names in aliases.items():
        normalized_aliases = {_normalize_import_column_name(name) for name in names}
        for idx, column_name in enumerate(normalized_header):
            if column_name in normalized_aliases:
                mapping[field_name] = idx
                break
    if "username" not in mapping or "password" not in mapping:
        return None
    mapping.setdefault("team_name", 0)
    return mapping


def _import_users_from_csv_text(db: Session, text: str, dry_run: bool = False) -> dict:
    reader = csv.reader(io.StringIO(text.strip()))
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="import text is empty")

    header_map = _csv_header_index_map(rows[0])
    has_header = header_map is not None
    data_rows = rows[1:] if has_header else rows
    if header_map is None:
        header_map = {"team_name": 0, "username": 1, "password": 2}

    existing_usernames = {username for username, in db.query(User.username).all()}
    existing_display_names = {
        display_name.strip()
        for display_name, in db.query(User.display_name).all()
        if display_name is not None and display_name.strip()
    }
    seen_usernames: set[str] = set()
    seen_display_names: set[str] = set()
    created: list[dict] = []
    errors: list[dict] = []
    blank_lines = 0
    users_to_create: list[User] = []
    now = utc_now().replace(tzinfo=None)

    for offset, raw_row in enumerate(data_rows, start=2 if has_header else 1):
        if not raw_row or not any(cell.strip() for cell in raw_row):
            blank_lines += 1
            continue
        if len(raw_row) < 3:
            errors.append({"line": offset, "error": "expected at least 3 columns"})
            continue

        def _cell(field_name: str) -> str:
            idx = header_map.get(field_name, 0)
            return raw_row[idx].strip() if idx < len(raw_row) else ""

        team_name = _cell("team_name")
        username = _cell("username")
        password = _cell("password")
        display_name = team_name or username

        if not username:
            errors.append(
                {
                    "line": offset,
                    "team_name": team_name,
                    "error": "username is required",
                }
            )
            continue
        if not password:
            errors.append(
                {
                    "line": offset,
                    "team_name": team_name,
                    "username": username,
                    "error": "password is required",
                }
            )
            continue
        if username in seen_usernames:
            errors.append(
                {
                    "line": offset,
                    "team_name": team_name,
                    "username": username,
                    "error": "username is duplicated in import file",
                }
            )
            continue
        if username in existing_usernames:
            errors.append(
                {
                    "line": offset,
                    "team_name": team_name,
                    "username": username,
                    "error": "username already exists",
                }
            )
            continue
        if display_name in seen_display_names:
            errors.append(
                {
                    "line": offset,
                    "team_name": team_name,
                    "username": username,
                    "error": "display_name is duplicated in import file",
                }
            )
            continue
        if display_name in existing_display_names:
            errors.append(
                {
                    "line": offset,
                    "team_name": team_name,
                    "username": username,
                    "error": "display_name already exists",
                }
            )
            continue

        seen_usernames.add(username)
        seen_display_names.add(display_name)
        created.append(
            {
                "line": offset,
                "team_name": team_name,
                "username": username,
                "display_name": display_name,
                "password": password,
            }
        )
        users_to_create.append(
            User(
                username=username,
                display_name=display_name,
                password_hash=hash_password(password),
                is_admin=False,
                is_active=True,
                score=0.0,
                created_at=now,
            )
        )

    if not dry_run:
        if users_to_create:
            db.add_all(users_to_create)
        db.commit()

    return {
        "created_count": len(created),
        "error_count": len(errors),
        "blank_lines": blank_lines,
        "dry_run": dry_run,
        "created": created,
        "errors": errors,
    }


# ── baselines ──────────────────────────────────────────────────


@router.get("/admin/baselines")
def list_baselines(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Baseline)
        .order_by(Baseline.sort_order.asc(), Baseline.id.asc())
        .all()
    )
    return {"ok": True, "data": [_serialize_baseline(row) for row in rows]}


@router.post("/admin/baselines")
def create_baseline(
    payload: CreateBaselineRequest,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    display_name = payload.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name must not be empty")
    # Validate submissions exist
    for sub_id, label in [
        (payload.attack_submission_id, "attack_submission_id"),
        (payload.defense_submission_id, "defense_submission_id"),
    ]:
        if not db.query(Submission.id).filter(Submission.id == sub_id).first():
            raise HTTPException(status_code=404, detail=f"{label} not found")
    existing = db.query(Baseline).filter(Baseline.display_name == display_name).first()
    if existing:
        raise HTTPException(status_code=409, detail="display_name already in use")
    now = utc_now().replace(tzinfo=None)
    row = Baseline(
        display_name=display_name,
        attack_submission_id=payload.attack_submission_id,
        defense_submission_id=payload.defense_submission_id,
        is_active=bool(payload.is_active),
        sort_order=int(payload.sort_order),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "data": _serialize_baseline(row)}


@router.put("/admin/baselines/{baseline_id}")
def update_baseline(
    baseline_id: int,
    payload: UpdateBaselineRequest,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    row = db.query(Baseline).filter(Baseline.id == baseline_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="baseline not found")
    display_name = payload.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name must not be empty")
    conflict = (
        db.query(Baseline)
        .filter(Baseline.display_name == display_name, Baseline.id != baseline_id)
        .first()
    )
    if conflict:
        raise HTTPException(status_code=409, detail="display_name already in use")
    row.display_name = display_name
    row.sort_order = int(payload.sort_order)
    row.is_active = bool(payload.is_active)
    row.updated_at = utc_now().replace(tzinfo=None)
    db.commit()
    db.refresh(row)
    return {"ok": True, "data": _serialize_baseline(row)}


@router.delete("/admin/baselines/{baseline_id}")
def delete_baseline(
    baseline_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    row = db.query(Baseline).filter(Baseline.id == baseline_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="baseline not found")
    db.delete(row)
    db.commit()
    return {"ok": True, "data": {"deleted_baseline_id": baseline_id}}


# ── global submissions list (for baseline picker) ──────────────


@router.get("/admin/all-submissions")
def admin_all_submissions(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Return all submissions with user info, ordered newest first. Used by the baseline picker."""
    rows = (
        db.query(Submission, User.username, User.display_name)
        .join(User, Submission.user_id == User.id)
        .order_by(Submission.uploaded_at.desc())
        .limit(2000)
        .all()
    )
    return {
        "ok": True,
        "data": [
            {
                "id": sub.id,
                "user_id": sub.user_id,
                "username": (display_name or "").strip() or username,
                "login_username": username,
                "display_name": (display_name or "").strip() or username,
                "role": sub.role,
                "file_hash": sub.file_hash,
                "uploaded_at": sub.uploaded_at.isoformat(),
            }
            for sub, username, display_name in rows
        ],
    }


# ── users ──────────────────────────────────────────────────────


@router.post("/admin/users/import")
def import_users(
    payload: BulkImportUsersRequest,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return {
        "ok": True,
        "data": _import_users_from_csv_text(
            db,
            payload.text,
            dry_run=payload.dry_run,
        ),
    }


@router.get("/admin/users")
def list_users(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    rows = db.query(User).order_by(User.id.asc()).all()
    return {
        "ok": True,
        "data": [
            {
                "id": r.id,
                "username": _user_display_name(r),
                "login_username": r.username,
                "display_name": _user_display_name(r),
                "is_admin": r.is_admin,
                "is_active": r.is_active,
                "is_agent": r.is_agent,
                "is_spectator": r.is_spectator,
                "agent_name": r.agent_name,
                "model_name": r.model_name,
                "score": r.score,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/admin/users/{user_id}/agent-telemetry")
def get_user_agent_telemetry(
    user_id: int,
    limit: int = 200,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    limit = max(1, min(1000, limit))
    rows = (
        db.query(AgentTelemetry)
        .filter(AgentTelemetry.user_id == user_id)
        .order_by(AgentTelemetry.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "ok": True,
        "data": {
            "user_id": user.id,
            "username": _user_display_name(user),
            "login_username": user.username,
            "display_name": _user_display_name(user),
            "is_agent": user.is_agent,
            "agent_name": user.agent_name,
            "model_name": user.model_name,
            "telemetry": [
                {
                    "id": r.id,
                    "agent_name": r.agent_name,
                    "model_name": r.model_name,
                    "method": r.method,
                    "path": r.path,
                    "recorded_at": r.recorded_at.replace(tzinfo=timezone.utc).isoformat(),
                }
                for r in rows
            ],
        },
    }


@router.post("/admin/users/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="cannot deactivate yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    user.is_active = not user.is_active
    db.commit()
    return {"ok": True, "data": {"id": user.id, "is_active": user.is_active}}


@router.post("/admin/users/{user_id}/toggle-admin")
def toggle_user_admin(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="cannot change your own admin status")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    user.is_admin = not user.is_admin
    db.commit()
    return {"ok": True, "data": {"id": user.id, "is_admin": user.is_admin}}



@router.post("/admin/users/{user_id}/toggle-spectator")
def toggle_user_spectator(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="cannot set yourself as spectator")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    user.is_spectator = not user.is_spectator
    db.commit()
    return {"ok": True, "data": {"id": user.id, "is_spectator": user.is_spectator}}


@router.post("/admin/users/{user_id}/reset-score")
def reset_user_score(
    user_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    db.query(ScoreHistory).filter(ScoreHistory.user_id == user_id).delete(
        synchronize_session=False
    )
    user.score = 0.0
    db.commit()
    return {"ok": True, "data": {"id": user.id, "score": user.score}}


@router.post("/admin/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="cannot reset your own password here")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    password = new_password()
    user.password_hash = hash_password(password)
    db.query(UserSession).filter(UserSession.user_id == user.id).delete(
        synchronize_session=False
    )
    db.commit()
    return {
        "ok": True,
        "data": {
            "id": user.id,
            "username": user.username,
            "display_name": _user_display_name(user),
            "password": password,
        },
    }


# ── system health ─────────────────────────────────────────────


@router.get("/admin/system")
def system_health(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    # DB check
    db_ok = False
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # Celery / Redis check via inspect with short timeout
    workers = 0
    active_tasks = 0
    redis_ok = False
    try:
        insp = celery_app.control.inspect(timeout=1.5)
        ping = insp.ping() or {}
        workers = len(ping)
        redis_ok = True  # if inspect responds, redis is reachable
        active = insp.active() or {}
        active_tasks = sum(len(v) for v in active.values())
    except Exception:
        pass

    return {
        "ok": True,
        "data": {
            "db": db_ok,
            "redis": redis_ok,
            "celery_workers": workers,
            "celery_active_tasks": active_tasks,
        },
    }


# ── round overview ────────────────────────────────────────────


@router.get("/admin/rounds/{round_id}/overview")
def round_overview(
    round_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    round_row = db.query(Round).filter(Round.id == round_id).first()
    if not round_row:
        raise HTTPException(status_code=404, detail="round not found")

    users = db.query(User).filter(User.is_active == True).order_by(User.id.asc()).all()

    # effective submissions: latest per user+role (round_id is now nullable/global)
    subs = (
        db.query(Submission)
        .order_by(Submission.uploaded_at.desc())
        .all()
    )
    sub_map: dict[int, set[str]] = {}
    for sub in subs:
        roles = sub_map.setdefault(sub.user_id, set())
        if sub.role not in roles:
            roles.add(sub.role)

    # BPs set (round_id is now nullable/global)
    bps = db.query(BPPreference.user_id).filter(BPPreference.user_id.isnot(None)).all()
    bp_set = {r.user_id for r in bps}

    # match counts per user
    from koh.db.models import Match as MatchModel

    match_rows = db.query(MatchModel).filter(MatchModel.round_id == round_id).all()
    match_counts: dict[int, dict[str, int]] = {}
    for m in match_rows:
        for uid in (m.team_a_id, m.team_b_id):
            mc = match_counts.setdefault(
                uid,
                {"total": 0, "queued": 0, "running": 0, "completed": 0, "failed": 0},
            )
            mc["total"] += 1
            mc[m.status] = mc.get(m.status, 0) + 1

    data = []
    for u in users:
        sm = sub_map.get(u.id, set())
        mc = match_counts.get(
            u.id, {"total": 0, "queued": 0, "running": 0, "completed": 0, "failed": 0}
        )
        data.append(
            {
                "user_id": u.id,
                "username": _user_display_name(u),
                "login_username": u.username,
                "display_name": _user_display_name(u),
                "has_attack_sub": "attack" in sm,
                "has_defense_sub": "defense" in sm,
                "has_bp": u.id in bp_set,
                "matches_total": mc["total"],
                "matches_queued": mc.get("queued", 0),
                "matches_running": mc.get("running", 0),
                "matches_completed": mc.get("completed", 0),
                "matches_failed": mc.get("failed", 0),
            }
        )

    return {"ok": True, "data": data}


@router.get("/admin/rounds/{round_id}/all-submissions")
def all_round_submissions(
    round_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Submission, User.username, User.display_name)
        .join(User, Submission.user_id == User.id)
        .filter(Submission.round_id == round_id)
        .order_by(Submission.uploaded_at.desc())
        .all()
    )
    return {
        "ok": True,
        "data": [
            {
                "id": sub.id,
                "user_id": sub.user_id,
                "username": (display_name or "").strip() or username,
                "login_username": username,
                "display_name": (display_name or "").strip() or username,
                "role": sub.role,
                "uploaded_at": sub.uploaded_at.isoformat(),
            }
            for sub, username, display_name in rows
        ],
    }


# ── match operations ──────────────────────────────────────────


@router.post("/admin/matches/{match_id}/retry")
def retry_match(
    match_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="match not found")
    if match.status not in ("failed", "queued"):
        raise HTTPException(
            status_code=400, detail=f"cannot retry match with status '{match.status}'"
        )
    match.status = "queued"
    match.result_json = {}
    db.commit()
    celery_app.send_task("koh.tasks.run_match", args=[match_id])
    return {"ok": True, "data": {"match_id": match_id, "task": "run_match"}}


@router.post("/admin/rounds/{round_id}/reset-failed")
def reset_failed_matches(
    round_id: int,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    failed = (
        db.query(Match)
        .filter(Match.round_id == round_id, Match.status == "failed")
        .all()
    )
    if not failed:
        return {"ok": True, "data": {"reset": 0}}
    for m in failed:
        m.status = "queued"
        m.result_json = {}
    db.commit()
    for m in failed:
        celery_app.send_task("koh.tasks.run_match", args=[m.id])
    return {"ok": True, "data": {"reset": len(failed)}}
