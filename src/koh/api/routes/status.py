from __future__ import annotations

import os
import subprocess
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from koh.api.deps import get_db
from koh.cache import get_api_cache_sync, set_api_cache_sync
from koh.auto_round import (
    auto_round_next_slot,
    auto_round_schedule_state,
    get_or_create_auto_round_config,
)
from koh.db.models import MapTemplate, Round, TestRun
from koh.site_config import get_or_create_site_config

router = APIRouter(tags=["status"])


def _compute_version() -> str:
    build_version = os.environ.get("KOH_VERSION")
    if build_version:
        return build_version

    try:
        short_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=normal"],
                text=True,
            ).strip()
        )
        return f"{short_sha}-dirty" if dirty else short_sha
    except Exception:
        return "dev"


_VERSION = _compute_version()
@router.get("/status")
def status(db: Session = Depends(get_db)):
    cached = get_api_cache_sync("status")
    if cached is not None:
        return cached
    site_cfg = get_or_create_site_config(db)
    latest = db.query(Round).order_by(Round.id.desc()).first()
    next_round_id = (latest.id + 1) if latest else 1
    active_maps = (
        db.query(MapTemplate)
        .filter(MapTemplate.is_active.is_(True))
        .count()
    )

    config = get_or_create_auto_round_config(db)
    schedule_state = auto_round_schedule_state(config, datetime.utcnow())
    next_slot = auto_round_next_slot(config, datetime.utcnow())
    next_round_at = next_slot.isoformat() if next_slot is not None else None

    latest_test_run = db.query(TestRun).order_by(TestRun.id.desc()).first()

    common_data = {
        "auto_round_enabled": config.enabled,
        "auto_round_state": schedule_state,
        "competition_starts_at": config.competition_starts_at.isoformat() if config.competition_starts_at else None,
        "competition_ends_at": config.competition_ends_at.isoformat() if config.competition_ends_at else None,
        "round_interval_minutes": config.interval_minutes,
    }

    if site_cfg.phase == "test":
        result = {
            "ok": True,
            "data": {
                "service": "koh-api",
                "version": _VERSION,
                "phase": site_cfg.phase,
                "current_round_id": None,
                "next_round_id": None,
                "next_round_at": None,
                **common_data,
                "maps": active_maps,
                "latest_test_run_id": latest_test_run.id if latest_test_run else None,
            },
        }
        set_api_cache_sync("status", result, 5)
        return result

    result = {
        "ok": True,
        "data": {
            "service": "koh-api",
            "version": _VERSION,
            "phase": site_cfg.phase,
            "current_round_id": latest.id if latest else None,
            "next_round_id": next_round_id,
            "next_round_at": next_round_at,
            **common_data,
            "maps": active_maps,
            "latest_test_run_id": latest_test_run.id if latest_test_run else None,
        },
    }
    set_api_cache_sync("status", result, 5)
    return result
