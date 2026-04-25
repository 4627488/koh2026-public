from __future__ import annotations

from datetime import timedelta

from celery import Celery

from koh.core.config import settings

celery_app = Celery(
    "koh",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["koh.tasks.jobs"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "auto-round-tick": {
            "task": "koh.tasks.auto_round_tick",
            "schedule": timedelta(seconds=max(5, settings.auto_round_tick_seconds)),
        },
        "auto-round-reconcile": {
            "task": "koh.tasks.auto_round_reconcile",
            "schedule": timedelta(
                seconds=max(10, settings.auto_round_reconcile_seconds)
            ),
        },
    },
)
