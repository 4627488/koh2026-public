from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from koh.api.routes.rounds import download_round_map, get_maps
from koh.db.base import Base
from koh.db.models import AutoRoundConfig, MapTemplate, User
from koh.game.koh_env import MapLayout


def _seed_user(session: Session) -> User:
    user = User(
        username="alice",
        password_hash="x",
        is_admin=False,
        is_active=True,
        is_agent=False,
        agent_name=None,
        model_name=None,
        score=0.0,
        created_at=datetime(2026, 4, 19, 0, 0, 0),
    )
    session.add(user)
    session.flush()
    return user


def _seed_map_template(session: Session) -> MapTemplate:
    layout = MapLayout(
        name="Preview Arena",
        grid_size=25,
        t_spawns=((1, 1), (1, 2)),
        ct_spawns=((23, 22), (23, 23)),
        bomb_site_a=(12, 12),
        bomb_site_b=(12, 13),
        obstacles=((5, 5), (6, 6)),
    )
    row = MapTemplate(
        slug="preview-arena",
        name="Preview Arena",
        source_text="preview-map-text",
        layout_json=layout.to_dict(),
        sort_order=1,
        difficulty=0.4,
        is_active=True,
        created_by_user_id=None,
        created_at=datetime(2026, 4, 19, 0, 0, 0),
        updated_at=datetime(2026, 4, 19, 0, 0, 0),
    )
    session.add(row)
    session.flush()
    return row


def _seed_before_start_config(session: Session) -> None:
    now = datetime.utcnow().replace(microsecond=0)
    session.add(
        AutoRoundConfig(
            id=1,
            enabled=True,
            interval_minutes=10,
            competition_starts_at=now + timedelta(hours=1),
            competition_ends_at=now + timedelta(hours=3),
            strategy_window_minutes=0,
            max_open_rounds=2,
            max_pending_matches=2000,
            updated_at=now,
        )
    )


def test_get_maps_returns_preview_for_next_round_before_start():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = _seed_user(session)
        template = _seed_map_template(session)
        _seed_before_start_config(session)
        session.commit()

        resp = get_maps(1, user, session)

    assert resp["ok"] is True
    assert len(resp["data"]) == 1
    preview = resp["data"][0]
    assert preview["id"] == template.id
    assert preview["round_id"] == 1
    assert preview["template_id"] == template.id
    assert preview["map_idx"] == 0
    assert preview["name"] == "Preview Arena"
    assert preview["layout"]["round_id"] == 1
    assert preview["layout"]["map_layout"]["name"] == "Preview Arena"


def test_download_round_map_supports_preview_before_start():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = _seed_user(session)
        template = _seed_map_template(session)
        _seed_before_start_config(session)
        session.commit()

        resp = download_round_map(1, template.id, user, session)

    assert resp.body.decode("utf-8") == "preview-map-text"
    assert resp.headers["content-disposition"] == 'attachment; filename="preview-arena.txt"'
