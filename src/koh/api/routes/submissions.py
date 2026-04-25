from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from koh.api.deps import get_current_user, get_db
from koh.db.models import Submission, User
from koh.ml.policies import WeightPolicy
from koh.security import utc_now
from koh.site_config import get_or_create_site_config

router = APIRouter(tags=["submissions"])

_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB
_COOLDOWN_SECONDS = 5


def _submissions_dir() -> Path:
    base = Path(os.getenv("KOH_DATA_DIR", "data"))
    d = base / "submissions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _compute_file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _public_model_id(submission: Submission) -> str | None:
    return submission.file_hash


def _resolve_path(stored_path: str) -> Path | None:
    data_dir = Path(os.getenv("KOH_DATA_DIR", "data"))
    p = Path(stored_path)
    for candidate in [p, Path.cwd() / p, data_dir / p]:
        if candidate.exists():
            return candidate
    return None


def _row_to_dict(r: Submission, *, inherited: bool = False) -> dict:
    public_id = _public_model_id(r)
    return {
        "id": public_id,
        "role": r.role,
        "round_id": r.round_id,
        "uploaded_at": r.uploaded_at.isoformat(),
        "inherited": inherited,
    }


def _check_cooldown(db: Session, user_id: int) -> None:
    last = (
        db.query(Submission)
        .filter(Submission.user_id == user_id)
        .order_by(Submission.uploaded_at.desc())
        .first()
    )
    if last:
        elapsed = (utc_now().replace(tzinfo=None) - last.uploaded_at).total_seconds()
        if elapsed < _COOLDOWN_SECONDS:
            raise HTTPException(
                status_code=429,
                detail=f"upload cooldown: wait {_COOLDOWN_SECONDS - elapsed:.1f}s",
            )


async def _do_upload(role: str, file: UploadFile, user: User, db: Session) -> Submission:
    if role not in ("attack", "defense"):
        raise HTTPException(status_code=400, detail="role must be 'attack' or 'defense'")

    fname = file.filename or ""
    if not fname.endswith(".safetensors"):
        raise HTTPException(status_code=400, detail="only .safetensors files accepted")

    _check_cooldown(db, user.id)

    content = await file.read()
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 50 MB)")

    ts = int(time.time())
    stored_path = _submissions_dir() / f"{user.id}_{role}_{ts}.safetensors"
    stored_path.write_bytes(content)

    data_dir = Path(os.getenv("KOH_DATA_DIR", "data"))
    try:
        stored_path_for_db = str(stored_path.relative_to(data_dir))
    except ValueError:
        stored_path_for_db = str(stored_path)

    valid, msg = WeightPolicy.validate_submission(stored_path)
    if not valid:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"invalid weights: {msg}")

    file_hash = _compute_file_hash(stored_path)

    now = utc_now().replace(tzinfo=None)
    sub = Submission(
        user_id=user.id,
        round_id=None,
        role=role,
        stored_path=stored_path_for_db,
        file_hash=file_hash,
        uploaded_at=now,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def _maybe_schedule_test_run(user: User, db: Session) -> None:
    """In test phase, build a new evaluation bundle after every valid contestant upload."""
    site_cfg = get_or_create_site_config(db)
    if site_cfg.phase != "test":
        return
    roles = {
        r.role
        for r in db.query(Submission.role)
        .filter(Submission.user_id == user.id)
        .distinct()
        .all()
    }
    if "attack" in roles and "defense" in roles:
        from koh.tasks.celery_app import celery_app
        celery_app.send_task("koh.tasks.schedule_test_run", args=[user.id])


@router.post("/submissions")
async def upload_submission_global(
    role: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = await _do_upload(role, file, user, db)
    _maybe_schedule_test_run(user, db)
    return {"ok": True, "data": _row_to_dict(sub)}


@router.post("/rounds/{round_id}/submissions")
async def upload_submission(
    round_id: int,
    role: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = await _do_upload(role, file, user, db)
    _maybe_schedule_test_run(user, db)
    return {"ok": True, "data": _row_to_dict(sub)}


@router.get("/rounds/{round_id}/submissions")
def list_submissions(
    round_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Effective submissions per role for the user (latest by uploaded_at)."""
    rows = (
        db.query(Submission)
        .filter(Submission.user_id == user.id)
        .order_by(Submission.uploaded_at.desc())
        .all()
    )

    latest_by_role: dict[str, Submission] = {}
    for row in rows:
        if row.role not in latest_by_role:
            latest_by_role[row.role] = row

    effective_rows = sorted(latest_by_role.values(), key=lambda r: r.uploaded_at, reverse=True)

    return {
        "ok": True,
        "data": [_row_to_dict(r) for r in effective_rows],
    }


@router.get("/submissions")
def list_all_submissions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """All submissions by the current user, newest first."""
    rows = (
        db.query(Submission)
        .filter(Submission.user_id == user.id)
        .order_by(Submission.uploaded_at.desc())
        .all()
    )
    return {"ok": True, "data": [_row_to_dict(r) for r in rows]}


@router.get("/submissions/{model_id}/download")
def download_submission(
    model_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a submission file by its public model ID."""
    query = db.query(Submission).order_by(Submission.uploaded_at.desc())
    if not user.is_admin:
        query = query.filter(Submission.user_id == user.id)
    rows = query.all()
    sub = next((row for row in rows if _public_model_id(row) == model_id), None)
    if sub is None:
        raise HTTPException(status_code=404, detail="submission not found")

    resolved = _resolve_path(sub.stored_path)
    if resolved is None:
        raise HTTPException(status_code=404, detail="file not found on disk")

    if not sub.file_hash:
        raise HTTPException(status_code=404, detail="submission not found")

    short = sub.file_hash[:8]
    filename = f"model_{sub.role}_{short}.safetensors"
    return FileResponse(path=str(resolved), filename=filename, media_type="application/octet-stream")
