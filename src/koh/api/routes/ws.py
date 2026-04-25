from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from redis.asyncio import Redis
from sqlalchemy import func

from koh.core.config import settings
from koh.db.models import Match, Round, TestMatch, TestRun
from koh.db.session import SessionLocal
from koh.site_config import ANNOUNCEMENT_EVENT_CHANNEL, get_or_create_site_config, serialize_site_config

router = APIRouter(tags=["ws"])
ROUND_EVENT_CHANNEL_TEMPLATE = "koh:round:{round_id}:events"
TEST_RUN_EVENT_CHANNEL_TEMPLATE = "koh:test-run:{run_id}:events"


def _round_event_channel(round_id: int) -> str:
    return ROUND_EVENT_CHANNEL_TEMPLATE.format(round_id=round_id)


def _test_run_event_channel(run_id: int) -> str:
    return TEST_RUN_EVENT_CHANNEL_TEMPLATE.format(run_id=run_id)


def _build_round_live_payload(round_id: int) -> dict:
    db = SessionLocal()
    try:
        round_row = db.query(Round).filter(Round.id == round_id).first()
        status_counts = {
            status: count
            for status, count in (
                db.query(Match.status, func.count(Match.id))
                .filter(Match.round_id == round_id)
                .group_by(Match.status)
                .all()
            )
        }
        total = sum(status_counts.values())
        return {
            "round_id": round_id,
            "round_exists": round_row is not None,
            "round_status": round_row.status if round_row is not None else "unknown",
            "matches": {
                "total": total,
                "queued": int(status_counts.get("queued", 0)),
                "running": int(status_counts.get("running", 0)),
                "completed": int(status_counts.get("completed", 0)),
                "failed": int(status_counts.get("failed", 0)),
            },
        }
    except Exception as error:
        return {
            "round_id": round_id,
            "round_exists": False,
            "round_status": "unavailable",
            "matches": {
                "total": 0,
                "queued": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
            },
            "error": str(error),
        }
    finally:
        db.close()


def _build_test_run_live_payload(run_id: int) -> dict:
    db = SessionLocal()
    try:
        row = db.query(TestRun).filter(TestRun.id == run_id).first()
        status_counts = {
            status: count
            for status, count in (
                db.query(TestMatch.status, func.count(TestMatch.id))
                .filter(TestMatch.test_run_id == run_id)
                .group_by(TestMatch.status)
                .all()
            )
        }
        total = sum(status_counts.values())
        return {
            "test_run_id": run_id,
            "test_run_exists": row is not None,
            "test_run_status": row.status if row is not None else "unknown",
            "matches": {
                "total": total,
                "queued": int(status_counts.get("queued", 0)),
                "running": int(status_counts.get("running", 0)),
                "completed": int(status_counts.get("completed", 0)),
                "failed": int(status_counts.get("failed", 0)),
            },
            "summary": row.summary_json if row is not None else {},
        }
    except Exception as error:
        return {
            "test_run_id": run_id,
            "test_run_exists": False,
            "test_run_status": "unavailable",
            "matches": {
                "total": 0,
                "queued": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
            },
            "summary": {},
            "error": str(error),
        }
    finally:
        db.close()


def _build_announcement_live_payload() -> dict:
    db = SessionLocal()
    try:
        row = get_or_create_site_config(db)
        return serialize_site_config(row)
    except Exception as error:
        return {
            "allow_registration": True,
            "phase": "competition",
            "announcement_title": "赛事公告",
            "announcement_body": "公告暂时不可用，请稍后重试。",
            "announcement_updated_at": None,
            "updated_at": "",
            "error": str(error),
        }
    finally:
        db.close()


@router.websocket("/ws/rounds/{round_id}/live")
async def round_live(round_id: int, websocket: WebSocket):
    await websocket.accept()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe(_round_event_channel(round_id))
        await websocket.send_text(
            json.dumps(
                {
                    "type": "round_live",
                    "trigger": {"type": "snapshot", "round_id": round_id},
                    "data": await run_in_threadpool(_build_round_live_payload, round_id),
                },
                ensure_ascii=True,
            )
        )

        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=30.0,
            )
            if message is None:
                # heartbeat: push current state even without a Redis event
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "round_live",
                            "trigger": {"type": "heartbeat", "round_id": round_id},
                            "data": await run_in_threadpool(
                                _build_round_live_payload, round_id
                            ),
                        },
                        ensure_ascii=True,
                    )
                )
                continue

            raw_data = message.get("data")
            trigger: dict
            if isinstance(raw_data, str):
                try:
                    trigger = json.loads(raw_data)
                except json.JSONDecodeError:
                    trigger = {"type": "unknown", "raw": raw_data, "round_id": round_id}
            else:
                trigger = {
                    "type": "unknown",
                    "raw": str(raw_data),
                    "round_id": round_id,
                }

            await websocket.send_text(
                json.dumps(
                    {
                        "type": "round_live",
                        "trigger": trigger,
                        "data": await run_in_threadpool(_build_round_live_payload, round_id),
                    },
                    ensure_ascii=True,
                )
            )
    except WebSocketDisconnect:
        return
    except Exception as error:
        # Connection may already be closed; do best-effort error push only.
        try:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "round_live_error",
                        "data": {
                            "round_id": round_id,
                            "error": str(error),
                        },
                    },
                    ensure_ascii=True,
                )
            )
        except WebSocketDisconnect:
            return
    finally:
        try:
            await pubsub.unsubscribe(_round_event_channel(round_id))
        except Exception:
            pass
        try:
            await pubsub.close()
        except Exception:
            pass
        try:
            await redis_client.aclose()
        except Exception:
            pass


@router.websocket("/ws/test/runs/{run_id}/live")
async def test_run_live(run_id: int, websocket: WebSocket):
    await websocket.accept()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe(_test_run_event_channel(run_id))
        await websocket.send_text(
            json.dumps(
                {
                    "type": "test_run_live",
                    "trigger": {"type": "snapshot", "test_run_id": run_id},
                    "data": await run_in_threadpool(_build_test_run_live_payload, run_id),
                },
                ensure_ascii=True,
            )
        )

        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=30.0,
            )
            if message is None:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "test_run_live",
                            "trigger": {"type": "heartbeat", "test_run_id": run_id},
                            "data": await run_in_threadpool(_build_test_run_live_payload, run_id),
                        },
                        ensure_ascii=True,
                    )
                )
                continue

            raw_data = message.get("data")
            if isinstance(raw_data, str):
                try:
                    trigger = json.loads(raw_data)
                except json.JSONDecodeError:
                    trigger = {"type": "unknown", "raw": raw_data, "test_run_id": run_id}
            else:
                trigger = {"type": "unknown", "raw": str(raw_data), "test_run_id": run_id}

            await websocket.send_text(
                json.dumps(
                    {
                        "type": "test_run_live",
                        "trigger": trigger,
                        "data": await run_in_threadpool(_build_test_run_live_payload, run_id),
                    },
                    ensure_ascii=True,
                )
            )
    except WebSocketDisconnect:
        return
    finally:
        try:
            await pubsub.unsubscribe(_test_run_event_channel(run_id))
        except Exception:
            pass
        try:
            await pubsub.close()
        except Exception:
            pass
        try:
            await redis_client.aclose()
        except Exception:
            pass


@router.websocket("/ws/announcements/live")
async def announcement_live(websocket: WebSocket):
    await websocket.accept()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe(ANNOUNCEMENT_EVENT_CHANNEL)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "announcement_live",
                    "trigger": {"type": "snapshot"},
                    "data": await run_in_threadpool(_build_announcement_live_payload),
                },
                ensure_ascii=True,
            )
        )

        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=30.0,
            )
            if message is None:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "announcement_live",
                            "trigger": {"type": "heartbeat"},
                            "data": await run_in_threadpool(
                                _build_announcement_live_payload
                            ),
                        },
                        ensure_ascii=True,
                    )
                )
                continue

            raw_data = message.get("data")
            if isinstance(raw_data, str):
                try:
                    trigger = json.loads(raw_data)
                except json.JSONDecodeError:
                    trigger = {"type": "unknown", "raw": raw_data}
            else:
                trigger = {"type": "unknown", "raw": str(raw_data)}

            await websocket.send_text(
                json.dumps(
                    {
                        "type": "announcement_live",
                        "trigger": trigger,
                        "data": await run_in_threadpool(_build_announcement_live_payload),
                    },
                    ensure_ascii=True,
                )
            )
    except WebSocketDisconnect:
        return
    except Exception as error:
        try:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "announcement_live_error",
                        "data": {"error": str(error)},
                    },
                    ensure_ascii=True,
                )
            )
        except WebSocketDisconnect:
            return
    finally:
        try:
            await pubsub.unsubscribe(ANNOUNCEMENT_EVENT_CHANNEL)
        except Exception:
            pass
        try:
            await pubsub.close()
        except Exception:
            pass
        try:
            await redis_client.aclose()
        except Exception:
            pass
