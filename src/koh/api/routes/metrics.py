from __future__ import annotations

from fastapi import APIRouter, Response

from koh.api.routes.status import _VERSION
from koh.auto_round import (
    auto_round_schedule_state,
    get_or_create_auto_round_config,
)
from koh.db.session import SessionLocal
from koh.metrics import collect_competition_metrics, render_metrics_text

router = APIRouter(tags=["metrics"])


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    with SessionLocal() as db:
        metrics_data = collect_competition_metrics(db)
        auto_round_config = get_or_create_auto_round_config(db)
        auto_round_state = auto_round_schedule_state(auto_round_config)

    payload = render_metrics_text(
        service="koh-api",
        version=_VERSION,
        phase=metrics_data["phase"],
        auto_round_enabled=bool(auto_round_config.enabled),
        auto_round_state=auto_round_state,
        active_maps=int(metrics_data["active_maps"]),
        current_round_id=int(metrics_data["current_round_id"]),
        next_round_id=int(metrics_data["next_round_id"]),
        latest_test_run_id=int(metrics_data["latest_test_run_id"]),
        round_status_counts=metrics_data["round_status_counts"],
        match_status_counts=metrics_data["match_status_counts"],
    )
    return Response(
        content=payload,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
