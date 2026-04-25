from __future__ import annotations

import json

from redis import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from koh.core.config import settings
from koh.db.models import SiteConfig
from koh.security import utc_now

ANNOUNCEMENT_EVENT_CHANNEL = "koh:site:announcements"
DEFAULT_ANNOUNCEMENT_TITLE = "赛事公告"
DEFAULT_ANNOUNCEMENT_BODY = (
    "欢迎来到 Asuri Major。\n"
    "1. 先下载规则、环境和 Baseline，确认本地训练与推理链路可用。\n"
    "2. 保存地图偏好后，再分别上传 T 方与 CT 方模型。\n"
    "3. 测试赛阶段会自动触发测试局；正式赛阶段由系统统一调度并持续更新排行榜。"
)


def get_or_create_site_config(db: Session) -> SiteConfig:
    row = db.query(SiteConfig).filter(SiteConfig.id == 1).first()
    if row is not None:
        return row

    row = SiteConfig(
        id=1,
        allow_registration=True,
        phase="competition",
        announcement_title=DEFAULT_ANNOUNCEMENT_TITLE,
        announcement_body=DEFAULT_ANNOUNCEMENT_BODY,
        announcement_updated_at=utc_now().replace(tzinfo=None),
        updated_at=utc_now().replace(tzinfo=None),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.query(SiteConfig).filter(SiteConfig.id == 1).first()
        if row is None:
            raise
        return row
    db.refresh(row)
    return row


def normalize_announcement_title(value: str | None) -> str:
    return (value or "").strip()[:160] or DEFAULT_ANNOUNCEMENT_TITLE


def normalize_announcement_body(value: str | None) -> str:
    text = (value or "").replace("\r\n", "\n").strip()
    return text[:8000] or DEFAULT_ANNOUNCEMENT_BODY


def serialize_site_config(row: SiteConfig) -> dict:
    return {
        "allow_registration": row.allow_registration,
        "phase": row.phase,
        "announcement_title": row.announcement_title or DEFAULT_ANNOUNCEMENT_TITLE,
        "announcement_body": row.announcement_body or DEFAULT_ANNOUNCEMENT_BODY,
        "announcement_updated_at": (
            row.announcement_updated_at.isoformat()
            if row.announcement_updated_at is not None
            else None
        ),
        "updated_at": row.updated_at.isoformat(),
    }


def touch_site_config_updated_at(row: SiteConfig) -> None:
    row.updated_at = utc_now().replace(tzinfo=None)


def publish_announcement_event(event_type: str, payload: dict) -> None:
    client: Redis | None = None
    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        client.publish(
            ANNOUNCEMENT_EVENT_CHANNEL,
            json.dumps(
                {
                    "type": event_type,
                    "payload": payload,
                },
                ensure_ascii=True,
                separators=(",", ":"),
            ),
        )
    except Exception:
        return
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
