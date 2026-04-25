from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from koh.api.deps import get_current_user, get_db
from koh.cache import get_api_cache_sync, set_api_cache_sync
from koh.auto_round import auto_round_schedule_state, get_or_create_auto_round_config
from koh.db.models import BPPreference, GameMap, MapTemplate, Match, Round, User
from koh.game.koh_env import MapLayout, RoundLayout
from koh.game.map_pool import MapFormatError, ensure_round_maps, list_map_templates, serialize_ascii_map
from koh.site_config import get_or_create_site_config

router = APIRouter(tags=["rounds"])


def _display_name(user: User) -> str:
    return user.public_name


class BPRequest(BaseModel):
    map_preferences: list[int]


def _is_upcoming_round_preview_available(db: Session, round_id: int) -> bool:
    latest = db.query(Round).order_by(Round.id.desc()).first()
    next_round_id = (latest.id + 1) if latest else 1
    if round_id != next_round_id:
        return False
    config = get_or_create_auto_round_config(db)
    return auto_round_schedule_state(config) == "before_start"


def _build_preview_maps(db: Session, round_id: int) -> list[dict]:
    templates = list_map_templates(db, active_only=True)
    if not templates:
        raise MapFormatError("no active maps available")

    return [
        {
            "id": template.id,
            "round_id": round_id,
            "template_id": template.id,
            "name": template.name,
            "slug": template.slug,
            "map_idx": map_idx,
            "seed": template.slug,
            "difficulty": template.difficulty,
            "layout": RoundLayout(
                round_id=round_id,
                map_layout=MapLayout.from_dict(template.layout_json),
            ).to_dict(),
        }
        for map_idx, template in enumerate(templates)
    ]


@router.get("/rounds")
def list_rounds(_: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = 50):
    site_cfg = get_or_create_site_config(db)
    if site_cfg.phase == "test" and not _.is_admin:
        return {"ok": True, "data": []}

    safe_limit = max(1, min(limit, 200))
    cache_key = f"rounds:list:{safe_limit}"
    cached = get_api_cache_sync(cache_key)
    if cached is not None:
        return cached

    rows = db.query(Round).order_by(Round.id.desc()).limit(safe_limit).all()
    result = {
        "ok": True,
        "data": [
            {
                "id": row.id,
                "status": row.status,
                "created_mode": row.created_mode,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }
    set_api_cache_sync(cache_key, result, 5)
    return result


@router.get("/rounds/{round_id}/maps")
def get_maps(round_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    site_cfg = get_or_create_site_config(db)
    if site_cfg.phase == "test" and not _.is_admin:
        raise HTTPException(status_code=404, detail="rounds are unavailable in test phase")
    round_row = db.query(Round).filter(Round.id == round_id).first()
    if round_row is None:
        if not _is_upcoming_round_preview_available(db, round_id):
            raise HTTPException(status_code=404, detail="round not found")
        try:
            preview_maps = _build_preview_maps(db, round_id)
        except MapFormatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "data": preview_maps}

    try:
        rows = ensure_round_maps(db, round_id)
    except MapFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    template_by_id = {
        row.id: row for row in list_map_templates(db, active_only=False)
    }

    return {
        "ok": True,
        "data": [
            {
                "id": row.id,
                "round_id": row.round_id,
                "template_id": row.template_id,
                "name": (
                    template_by_id[row.template_id].name
                    if row.template_id in template_by_id
                    else row.seed
                ),
                "slug": (
                    template_by_id[row.template_id].slug
                    if row.template_id in template_by_id
                    else row.seed
                ),
                "map_idx": row.map_idx,
                "seed": row.seed,
                "difficulty": row.difficulty,
                "layout": row.layout_json,
            }
            for row in rows
        ],
    }


@router.post("/bp")
def upsert_bp_global(
    payload: BPRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Global map preference — not tied to any round."""
    seen: set[int] = set()
    sanitized: list[int] = []
    for idx in payload.map_preferences:
        if idx not in seen:
            seen.add(idx)
            sanitized.append(idx)

    row = db.query(BPPreference).filter(BPPreference.user_id == user.id).first()
    if row is None:
        row = BPPreference(user_id=user.id, round_id=None, map_preferences=sanitized)
        db.add(row)
    else:
        row.map_preferences = sanitized
        flag_modified(row, "map_preferences")
    db.commit()
    return {"ok": True, "data": {"saved": True}}


@router.get("/bp")
def get_bp_global(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Global map preference."""
    row = db.query(BPPreference).filter(BPPreference.user_id == user.id).first()
    if row is None:
        return {"ok": True, "data": None}
    return {"ok": True, "data": {"map_preferences": row.map_preferences or []}}


@router.post("/rounds/{round_id}/bp")
def upsert_bp(
    round_id: int,
    payload: BPRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(Round).filter(Round.id == round_id).first()  # existence check only

    seen: set[int] = set()
    sanitized = []
    for idx in payload.map_preferences:
        if idx not in seen:
            seen.add(idx)
            sanitized.append(idx)

    row = db.query(BPPreference).filter(BPPreference.user_id == user.id).first()
    if row is None:
        row = BPPreference(user_id=user.id, round_id=round_id, map_preferences=sanitized)
        db.add(row)
    else:
        row.map_preferences = sanitized
        flag_modified(row, "map_preferences")
    db.commit()
    return {"ok": True, "data": {"round_id": round_id, "saved": True}}


@router.get("/rounds/{round_id}/bp")
def get_bp(
    round_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    row = db.query(BPPreference).filter(BPPreference.user_id == user.id).first()
    if row is None:
        return {"ok": True, "data": None}
    return {"ok": True, "data": {"map_preferences": row.map_preferences or []}}


@router.get("/rounds/{round_id}/matches")
def list_round_matches(
    round_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    site_cfg = get_or_create_site_config(db)
    if site_cfg.phase == "test" and not current_user.is_admin:
        raise HTTPException(status_code=404, detail="rounds are unavailable in test phase")
    round_row = db.query(Round).filter(Round.id == round_id).first()
    if round_row is None:
        raise HTTPException(status_code=404, detail="round not found")

    cache_key = f"round:matches:{round_id}"
    cached = get_api_cache_sync(cache_key)
    if cached is not None:
        return cached

    rows = db.query(Match).filter(Match.round_id == round_id).all()
    user_ids = {row.team_a_id for row in rows} | {row.team_b_id for row in rows}
    users = db.query(User).filter(User.id.in_(list(user_ids))).all() if user_ids else []
    user_name_by_id = {row.id: _display_name(row) for row in users}

    map_ids = {row.map_id for row in rows if row.map_id is not None}
    game_maps = db.query(GameMap).filter(GameMap.id.in_(list(map_ids))).all() if map_ids else []
    game_map_by_id: dict[int, GameMap] = {gm.id: gm for gm in game_maps}
    template_ids = {gm.template_id for gm in game_maps if gm.template_id is not None}
    templates = db.query(MapTemplate).filter(MapTemplate.id.in_(list(template_ids))).all() if template_ids else []
    template_by_id: dict[int, MapTemplate] = {t.id: t for t in templates}

    def _map_name(map_id: int | None) -> str | None:
        if map_id is None:
            return None
        gm = game_map_by_id.get(map_id)
        if gm is None:
            return None
        if gm.template_id is not None and gm.template_id in template_by_id:
            return template_by_id[gm.template_id].name
        return gm.seed or None

    def _map_idx(map_id: int | None) -> int | None:
        if map_id is None:
            return None
        gm = game_map_by_id.get(map_id)
        return gm.map_idx if gm is not None else None

    result = {
        "ok": True,
        "data": [
            {
                "id": row.id,
                "round_id": row.round_id,
                "map_id": row.map_id,
                "map_idx": _map_idx(row.map_id),
                "map_name": _map_name(row.map_id),
                "team_a_id": row.team_a_id,
                "team_a_name": user_name_by_id.get(row.team_a_id),
                "team_b_id": row.team_b_id,
                "team_b_name": user_name_by_id.get(row.team_b_id),
                "status": row.status,
                "result": row.result_json,
            }
            for row in rows
        ],
    }
    # Cache longer if the round is settled; short TTL while matches are still running
    statuses = {row.status for row in rows}
    ttl = 300 if not (statuses & {"queued", "running"}) else 5
    set_api_cache_sync(cache_key, result, ttl)
    return result


@router.get("/rounds/{round_id}/maps/{map_id}/download")
def download_round_map(
    round_id: int,
    map_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    site_cfg = get_or_create_site_config(db)
    if site_cfg.phase == "test" and not _.is_admin:
        raise HTTPException(status_code=404, detail="rounds are unavailable in test phase")
    round_row = db.query(Round).filter(Round.id == round_id).first()
    if round_row is None:
        if not _is_upcoming_round_preview_available(db, round_id):
            raise HTTPException(status_code=404, detail="round not found")
        template = db.query(MapTemplate).filter(MapTemplate.id == map_id, MapTemplate.is_active.is_(True)).first()
        if template is None:
            raise HTTPException(status_code=404, detail="map not found")
        filename = f"{(template.slug or template.name or f'map-{map_id}').strip() or f'map-{map_id}'}.txt"
        return Response(
            content=template.source_text,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    row = (
        db.query(GameMap)
        .filter(GameMap.round_id == round_id, GameMap.id == map_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="map not found")

    layout_payload = row.layout_json or {}
    map_layout_payload = layout_payload.get("map_layout", layout_payload)
    layout = MapLayout.from_dict(map_layout_payload)
    source_text = serialize_ascii_map(layout)
    filename = f"{(row.seed or f'map-{row.map_idx}').strip() or f'map-{row.map_idx}'}.txt"

    return Response(
        content=source_text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
