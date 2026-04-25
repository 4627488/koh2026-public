from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from koh.core.config import settings
from koh.db.models import AutoRoundConfig
from koh.security import utc_now


def _clamp(value: int, *, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _parse_env_datetime(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return _normalize_dt(parsed)


def get_or_create_auto_round_config(db: Session) -> AutoRoundConfig:
    row = db.query(AutoRoundConfig).filter(AutoRoundConfig.id == 1).first()
    if row is not None:
        return row

    now = utc_now().replace(tzinfo=None)
    row = AutoRoundConfig(
        id=1,
        enabled=bool(settings.auto_round_enabled),
        interval_minutes=_clamp(settings.auto_round_interval_minutes, low=1, high=1440),
        competition_starts_at=_parse_env_datetime(settings.auto_round_competition_starts_at),
        competition_ends_at=_parse_env_datetime(settings.auto_round_competition_ends_at),
        strategy_window_minutes=0,
        max_open_rounds=_clamp(settings.auto_round_max_open_rounds, low=1, high=1000),
        max_pending_matches=_clamp(
            settings.auto_round_max_pending_matches,
            low=1,
            high=10_000_000,
        ),
        updated_at=now,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.query(AutoRoundConfig).filter(AutoRoundConfig.id == 1).first()
        if row is None:
            raise
        return row
    db.refresh(row)
    return row


def auto_round_schedule_state(row: AutoRoundConfig, now: datetime | None = None) -> str:
    if not row.enabled:
        return "disabled"
    starts_at = _normalize_dt(row.competition_starts_at)
    ends_at = _normalize_dt(row.competition_ends_at)
    if starts_at is None or ends_at is None:
        return "unscheduled"
    if ends_at <= starts_at:
        return "invalid"
    now = _normalize_dt(now) or utc_now().replace(tzinfo=None)
    if now < starts_at:
        return "before_start"
    if now >= ends_at:
        return "finished"
    return "running"


def auto_round_next_slot(row: AutoRoundConfig, now: datetime | None = None) -> datetime | None:
    starts_at = _normalize_dt(row.competition_starts_at)
    ends_at = _normalize_dt(row.competition_ends_at)
    if starts_at is None or ends_at is None or ends_at <= starts_at:
        return None
    interval = timedelta(minutes=max(1, int(row.interval_minutes)))
    now = _normalize_dt(now) or utc_now().replace(tzinfo=None)
    if now <= starts_at:
        return starts_at
    elapsed = now - starts_at
    slot_index = int(elapsed.total_seconds() // interval.total_seconds()) + 1
    candidate = starts_at + slot_index * interval
    if candidate >= ends_at:
        return None
    return candidate


def auto_round_due_slot(row: AutoRoundConfig, now: datetime | None = None) -> datetime | None:
    starts_at = _normalize_dt(row.competition_starts_at)
    ends_at = _normalize_dt(row.competition_ends_at)
    if starts_at is None or ends_at is None or ends_at <= starts_at:
        return None
    interval = timedelta(minutes=max(1, int(row.interval_minutes)))
    now = _normalize_dt(now) or utc_now().replace(tzinfo=None)
    if now < starts_at or now >= ends_at:
        return None
    elapsed = now - starts_at
    slot_index = int(elapsed.total_seconds() // interval.total_seconds())
    candidate = starts_at + slot_index * interval
    if candidate >= ends_at:
        return None
    return candidate


def auto_round_due_slots(
    row: AutoRoundConfig,
    now: datetime | None = None,
) -> list[datetime]:
    starts_at = _normalize_dt(row.competition_starts_at)
    ends_at = _normalize_dt(row.competition_ends_at)
    if starts_at is None or ends_at is None or ends_at <= starts_at:
        return []

    interval = timedelta(minutes=max(1, int(row.interval_minutes)))
    now = _normalize_dt(now) or utc_now().replace(tzinfo=None)
    if now < starts_at or now >= ends_at:
        return []

    elapsed = now - starts_at
    slot_index = int(elapsed.total_seconds() // interval.total_seconds())
    return [starts_at + idx * interval for idx in range(slot_index + 1)]


def serialize_auto_round_config(row: AutoRoundConfig) -> dict:
    return {
        "enabled": row.enabled,
        "interval_minutes": row.interval_minutes,
        "competition_starts_at": row.competition_starts_at.isoformat() if row.competition_starts_at else None,
        "competition_ends_at": row.competition_ends_at.isoformat() if row.competition_ends_at else None,
        "schedule_state": auto_round_schedule_state(row),
        "next_slot_at": auto_round_next_slot(row).isoformat() if auto_round_next_slot(row) else None,
        "updated_at": row.updated_at.isoformat(),
        "env_defaults": {
            "enabled": settings.auto_round_enabled,
            "interval_minutes": settings.auto_round_interval_minutes,
            "competition_starts_at": settings.auto_round_competition_starts_at or None,
            "competition_ends_at": settings.auto_round_competition_ends_at or None,
            "tick_seconds": settings.auto_round_tick_seconds,
            "reconcile_seconds": settings.auto_round_reconcile_seconds,
        },
    }


def touch_auto_round_updated_at(row: AutoRoundConfig) -> None:
    row.updated_at = utc_now().replace(tzinfo=None)
