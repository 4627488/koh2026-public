from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from koh.db.base import Base
from koh.db.models import BPPreference, Submission
from koh.tasks.jobs import _users_with_both_roles_submitted


def test_users_with_both_roles_submitted_requires_attack_defense_and_bp():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    now = datetime(2026, 4, 18, 0, 0, 0)
    with Session(engine) as session:
        session.add_all(
            [
                Submission(user_id=1, round_id=None, role="attack", stored_path="a1", uploaded_at=now),
                Submission(user_id=1, round_id=None, role="defense", stored_path="d1", uploaded_at=now),
                BPPreference(user_id=1, round_id=None, map_preferences=[1, 2]),
                Submission(user_id=2, round_id=None, role="attack", stored_path="a2", uploaded_at=now),
                Submission(user_id=2, round_id=None, role="defense", stored_path="d2", uploaded_at=now),
                Submission(user_id=3, round_id=None, role="attack", stored_path="a3", uploaded_at=now),
                BPPreference(user_id=3, round_id=None, map_preferences=[2, 3]),
                Submission(user_id=4, round_id=None, role="defense", stored_path="d4", uploaded_at=now),
                BPPreference(user_id=4, round_id=None, map_preferences=[3, 4]),
            ]
        )
        session.commit()

        user_ids = session.execute(_users_with_both_roles_submitted()).scalars().all()

    assert user_ids == [1]
