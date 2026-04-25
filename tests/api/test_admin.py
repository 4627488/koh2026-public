from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from koh.api.routes.admin import _import_users_from_csv_text, _recompute_scores_for_users
from koh.db.base import Base
from koh.db.models import ScoreHistory, User


def test_recompute_scores_for_users_rebuilds_running_totals_after_round_removal():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    now = datetime(2026, 4, 18, 0, 0, 0)
    with Session(engine) as session:
        user = User(
            username="alice",
            password_hash="x",
            is_admin=False,
            is_active=True,
            is_agent=False,
            agent_name=None,
            model_name=None,
            score=12.0,
            created_at=now,
        )
        session.add(user)
        session.flush()

        session.add_all(
            [
                ScoreHistory(user_id=user.id, round_id=1, score_before=0.0, score_after=5.0, delta=5.0),
                ScoreHistory(user_id=user.id, round_id=3, score_before=5.0, score_after=12.0, delta=7.0),
            ]
        )
        session.commit()

        session.query(ScoreHistory).filter(ScoreHistory.round_id == 1).delete(synchronize_session=False)
        _recompute_scores_for_users(session, {user.id})
        session.commit()

        session.refresh(user)
        remaining = session.query(ScoreHistory).filter(ScoreHistory.round_id == 3).first()

    assert user.score == 7.0
    assert remaining is not None
    assert remaining.score_before == 0.0
    assert remaining.score_after == 7.0


def test_import_users_from_csv_text_creates_users_from_chinese_header():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    csv_text = """队伍,KOH用户名,KOH密码
21号,team_21,nXewp4NN
世界和平,team_02,mdqnDNXW
"""

    with Session(engine) as session:
        result = _import_users_from_csv_text(session, csv_text)
        users = session.query(User).order_by(User.username.asc()).all()

    assert result["created_count"] == 2
    assert result["error_count"] == 0
    assert [item["team_name"] for item in result["created"]] == ["21号", "世界和平"]
    assert [item["display_name"] for item in result["created"]] == ["21号", "世界和平"]
    assert [user.username for user in users] == ["team_02", "team_21"]
    assert [user.public_name for user in users] == ["世界和平", "21号"]
    assert all(user.is_active for user in users)
    assert all(not user.is_admin for user in users)


def test_import_users_from_csv_text_reports_row_errors_and_supports_dry_run():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    now = datetime(2026, 4, 18, 0, 0, 0)
    with Session(engine) as session:
        session.add(
            User(
                username="existing",
                display_name="已有队伍",
                password_hash="x",
                is_admin=False,
                is_active=True,
                is_agent=False,
                agent_name=None,
                model_name=None,
                score=0.0,
                created_at=now,
            )
        )
        session.commit()

        csv_text = """队伍,KOH用户名,KOH密码
老用户,existing,password1
有效队伍,new_user,password2
重复一次,new_user,password3
有效队伍,new_user_2,password4
缺密码,missing_password,

坏格式,only_two_columns
"""
        result = _import_users_from_csv_text(session, csv_text, dry_run=True)
        users = session.query(User).order_by(User.username.asc()).all()

    assert result["dry_run"] is True
    assert result["created_count"] == 1
    assert result["error_count"] == 5
    assert result["blank_lines"] == 1
    assert [item["error"] for item in result["errors"]] == [
        "username already exists",
        "username is duplicated in import file",
        "display_name is duplicated in import file",
        "password is required",
        "expected at least 3 columns",
    ]
    assert [user.username for user in users] == ["existing"]
