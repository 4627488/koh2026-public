from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from koh.db.base import Base
from koh.db.models import AutoRoundConfig, GameMap, Match, Round, SiteConfig, TestRun
from koh.metrics import collect_competition_metrics


def test_collect_competition_metrics_summarizes_rounds_matches_and_test_runs():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    now = datetime(2026, 4, 18, 0, 0, 0)
    with Session(engine) as session:
        session.add(SiteConfig(id=1, allow_registration=True, phase="competition", updated_at=now))
        session.add(
            AutoRoundConfig(
                id=1,
                enabled=True,
                interval_minutes=10,
                competition_starts_at=now,
                competition_ends_at=None,
                strategy_window_minutes=0,
                max_open_rounds=2,
                max_pending_matches=2000,
                updated_at=now,
            )
        )
        session.add_all(
            [
                Round(id=1, status="completed", strategy_opens_at=now, strategy_closes_at=now, created_mode="manual", auto_slot_start=None, created_at=now),
                Round(id=2, status="running", strategy_opens_at=now, strategy_closes_at=now, created_mode="auto", auto_slot_start=now, created_at=now),
            ]
        )
        session.add(
            GameMap(id=1, round_id=2, template_id=None, map_idx=1, seed="seed-1", difficulty=0.5, layout_json={})
        )
        session.add_all(
            [
                Match(id=1, round_id=2, map_id=1, team_a_id=1, team_b_id=2, status="queued", result_json={}),
                Match(id=2, round_id=2, map_id=1, team_a_id=1, team_b_id=2, status="completed", result_json={}),
            ]
        )
        session.add(
            TestRun(
                id=7,
                bundle_id=1,
                user_id=1,
                baseline_pack_version="v1",
                status="completed",
                summary_json={},
                queued_at=now,
                started_at=now,
                finished_at=now,
            )
        )
        session.commit()

        data = collect_competition_metrics(session)

    assert data["phase"] == "competition"
    assert data["current_round_id"] == 2
    assert data["next_round_id"] == 3
    assert data["latest_test_run_id"] == 7
    assert data["active_maps"] == 0
    assert data["round_status_counts"] == {"completed": 1, "running": 1}
    assert data["match_status_counts"] == {"completed": 1, "queued": 1}
