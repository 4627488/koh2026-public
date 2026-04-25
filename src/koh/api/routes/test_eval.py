from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from koh.api.deps import get_current_user, get_db
from koh.db.models import Baseline, Submission, SubmissionBundle, TestMatch, TestRun, User
from koh.game.map_pool import list_map_templates
from koh.site_config import get_or_create_site_config

router = APIRouter(tags=["test"])


def _display_name(user: User) -> str:
    return user.public_name


def _ensure_test_phase(db: Session) -> None:
    site_cfg = get_or_create_site_config(db)
    if site_cfg.phase != "test":
        raise HTTPException(status_code=409, detail="test evaluation is only available in test phase")


def _serialize_bundle(row: SubmissionBundle) -> dict:
    prefs = (row.bp_snapshot_json or {}).get("map_preferences", [])
    return {
        "id": row.id,
        "user_id": row.user_id,
        "attack_submission_id": row.attack_submission_id,
        "defense_submission_id": row.defense_submission_id,
        "map_preferences": prefs,
        "created_at": row.created_at.isoformat(),
    }


def _serialize_run(row: TestRun) -> dict:
    return {
        "id": row.id,
        "bundle_id": row.bundle_id,
        "user_id": row.user_id,
        "baseline_pack_version": row.baseline_pack_version,
        "status": row.status,
        "summary": row.summary_json or {},
        "queued_at": row.queued_at.isoformat(),
        "started_at": row.started_at.isoformat() if row.started_at is not None else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at is not None else None,
    }


def _serialize_test_match(
    row: TestMatch,
    user_name_by_id: dict[int, str],
    baseline_name_by_id: dict[int, str] | None = None,
) -> dict:
    if row.team_b_id is not None:
        team_b_name = user_name_by_id.get(row.team_b_id)
    elif row.baseline_id is not None and baseline_name_by_id:
        team_b_name = baseline_name_by_id.get(row.baseline_id)
    else:
        team_b_name = None
    return {
        "id": row.id,
        "round_id": row.test_run_id,
        "test_run_id": row.test_run_id,
        "contestant_user_id": row.contestant_user_id,
        "baseline_id": row.baseline_id,
        "team_a_id": row.team_a_id,
        "team_a_name": user_name_by_id.get(row.team_a_id),
        "team_b_id": row.team_b_id,
        "team_b_name": team_b_name,
        "map_id": row.map_idx,
        "map_template_id": row.map_template_id,
        "map_idx": row.map_idx,
        "map_name": row.map_name,
        "status": row.status,
        "result": row.result_json or {},
    }


def _baseline_names(db: Session, rows: list[TestMatch]) -> dict[int, str]:
    """Return {baseline_id: display_name} for all baselines referenced by these rows."""
    ids = {row.baseline_id for row in rows if row.baseline_id is not None}
    if not ids:
        return {}
    baselines = db.query(Baseline).filter(Baseline.id.in_(list(ids))).all()
    return {b.id: b.display_name for b in baselines}


def _effective_submission(db: Session, submission_id: int | None) -> Submission | None:
    if submission_id is None:
        return None
    return db.query(Submission).filter(Submission.id == submission_id).first()


def _can_view_test_user(current_user: User, owner_user_id: int) -> bool:
    return current_user.is_admin or current_user.id == owner_user_id


@router.get("/test/status")
def test_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_test_phase(db)
    latest_bundle = (
        db.query(SubmissionBundle)
        .filter(SubmissionBundle.user_id == current_user.id)
        .order_by(SubmissionBundle.id.desc())
        .first()
    )
    latest_run = (
        db.query(TestRun)
        .filter(TestRun.user_id == current_user.id)
        .order_by(TestRun.id.desc())
        .first()
    )
    return {
        "ok": True,
        "data": {
            "phase": "test",
            "has_bundle": latest_bundle is not None,
            "latest_bundle": _serialize_bundle(latest_bundle) if latest_bundle is not None else None,
            "latest_run": _serialize_run(latest_run) if latest_run is not None else None,
        },
    }


@router.get("/test/maps")
def list_test_maps(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_test_phase(db)
    templates = list_map_templates(db, active_only=True)
    return {
        "ok": True,
        "data": [
            {
                "id": row.id,
                "round_id": None,
                "template_id": row.id,
                "name": row.name,
                "slug": row.slug,
                "map_idx": idx,
                "seed": row.slug,
                "layout": row.layout_json,
            }
            for idx, row in enumerate(templates)
        ],
    }


@router.get("/test/maps/{map_id}/download")
def download_test_map(map_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_test_phase(db)
    templates = list_map_templates(db, active_only=True)
    indexed = {row.id: row for row in templates}
    row = indexed.get(map_id)
    if row is None:
        raise HTTPException(status_code=404, detail="map not found")
    filename = f"{row.slug}.txt"
    return Response(
        content=row.source_text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/test/bundles")
def list_test_bundles(current_user: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = 20):
    _ensure_test_phase(db)
    safe_limit = max(1, min(limit, 100))
    user_id = current_user.id
    rows = (
        db.query(SubmissionBundle)
        .filter(SubmissionBundle.user_id == user_id)
        .order_by(SubmissionBundle.id.desc())
        .limit(safe_limit)
        .all()
    )
    return {"ok": True, "data": [_serialize_bundle(row) for row in rows]}


@router.get("/test/runs")
def list_test_runs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    user_id: int | None = None,
):
    _ensure_test_phase(db)
    safe_limit = max(1, min(limit, 200))
    query = db.query(TestRun)
    if current_user.is_admin:
        if user_id is not None:
            query = query.filter(TestRun.user_id == user_id)
    else:
        query = query.filter(TestRun.user_id == current_user.id)
    rows = query.order_by(TestRun.id.desc()).limit(safe_limit).all()
    return {"ok": True, "data": [_serialize_run(row) for row in rows]}


@router.get("/test/matches")
def list_test_matches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 200,
    user_id: int | None = None,
):
    _ensure_test_phase(db)
    safe_limit = max(1, min(limit, 1000))
    query = db.query(TestMatch)
    if current_user.is_admin:
        if user_id is not None:
            query = query.filter(TestMatch.contestant_user_id == user_id)
    else:
        query = query.filter(TestMatch.contestant_user_id == current_user.id)
    rows = query.order_by(TestMatch.id.desc()).limit(safe_limit).all()
    user_ids = {row.team_a_id for row in rows} | {row.team_b_id for row in rows if row.team_b_id is not None}
    users = db.query(User).filter(User.id.in_(list(user_ids))).all() if user_ids else []
    user_name_by_id = {row.id: _display_name(row) for row in users}
    bl_names = _baseline_names(db, rows)
    return {"ok": True, "data": [_serialize_test_match(row, user_name_by_id, bl_names) for row in rows]}


@router.get("/test/bundles/{bundle_id}")
def get_test_bundle(bundle_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_test_phase(db)
    row = (
        db.query(SubmissionBundle)
        .filter(SubmissionBundle.id == bundle_id)
        .first()
    )
    if row is None or not _can_view_test_user(current_user, row.user_id):
        raise HTTPException(status_code=404, detail="test bundle not found")
    runs = (
        db.query(TestRun)
        .filter(TestRun.bundle_id == bundle_id)
        .order_by(TestRun.id.desc())
        .all()
    )
    return {"ok": True, "data": {"bundle": _serialize_bundle(row), "runs": [_serialize_run(run) for run in runs]}}


@router.get("/test/runs/{run_id}")
def get_test_run(run_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_test_phase(db)
    row = db.query(TestRun).filter(TestRun.id == run_id).first()
    if row is None or not _can_view_test_user(current_user, row.user_id):
        raise HTTPException(status_code=404, detail="test run not found")
    return {"ok": True, "data": _serialize_run(row)}


@router.get("/test/runs/{run_id}/matches")
def get_test_run_matches(run_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_test_phase(db)
    run = db.query(TestRun).filter(TestRun.id == run_id).first()
    if run is None or not _can_view_test_user(current_user, run.user_id):
        raise HTTPException(status_code=404, detail="test run not found")
    rows = (
        db.query(TestMatch)
        .filter(TestMatch.test_run_id == run_id)
        .order_by(TestMatch.id.asc())
        .all()
    )
    user_ids = {row.team_a_id for row in rows} | {row.team_b_id for row in rows if row.team_b_id is not None}
    users = db.query(User).filter(User.id.in_(list(user_ids))).all() if user_ids else []
    user_name_by_id = {row.id: _display_name(row) for row in users}
    bl_names = _baseline_names(db, rows)
    return {"ok": True, "data": [_serialize_test_match(row, user_name_by_id, bl_names) for row in rows]}


@router.get("/test/matches/{match_id}")
def get_test_match(match_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_test_phase(db)
    row = db.query(TestMatch).filter(TestMatch.id == match_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="test match not found")
    run = db.query(TestRun).filter(TestRun.id == row.test_run_id).first()
    if run is None or not _can_view_test_user(current_user, run.user_id):
        raise HTTPException(status_code=404, detail="test match not found")
    team_ids = [row.team_a_id] + ([row.team_b_id] if row.team_b_id is not None else [])
    users = db.query(User).filter(User.id.in_(team_ids)).all()
    user_name_by_id = {user.id: _display_name(user) for user in users}
    bl_names = _baseline_names(db, [row])

    result_json = row.result_json or {}
    team_a_role = str(result_json.get("team_a_role", "attack")).lower()
    team_b_role = "defense" if team_a_role == "attack" else "attack"
    team_a_submission = _effective_submission(
        db,
        row.attack_submission_id if team_a_role == "attack" else row.defense_submission_id,
    )
    team_b_submission = _effective_submission(
        db,
        row.defense_submission_id if team_a_role == "attack" else row.attack_submission_id,
    )

    return {
        "ok": True,
        "data": {
            **_serialize_test_match(row, user_name_by_id, bl_names),
            "team_a_model": {
                "role": team_a_role,
                "model_id": team_a_submission.file_hash if team_a_submission is not None else None,
            },
            "team_b_model": {
                "role": team_b_role,
                "model_id": team_b_submission.file_hash if team_b_submission is not None else None,
            },
        },
    }


@router.get("/test/matches/{match_id}/replay")
def get_test_match_replay(match_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_test_phase(db)
    row = db.query(TestMatch).filter(TestMatch.id == match_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="test replay not found")
    run = db.query(TestRun).filter(TestRun.id == row.test_run_id).first()
    if run is None or not _can_view_test_user(current_user, run.user_id):
        raise HTTPException(status_code=404, detail="test replay not found")
    if not row.replay_path:
        raise HTTPException(status_code=404, detail="test replay not found")
    path = Path(row.replay_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="test replay file missing")
    return {"ok": True, "data": json.loads(path.read_text(encoding="utf-8"))}
