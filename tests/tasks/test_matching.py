"""Unit tests for all-vs-all pairing algorithm."""

from unittest.mock import MagicMock

from koh.db.models import User
from koh.tasks.matching import pair_users_all_vs_all


def create_mock_user(user_id: int, elo: float = 1200.0) -> User:
    """Helper to create a mock user."""
    user = MagicMock(spec=User)
    user.id = user_id
    user.elo = elo
    return user


def _pair_ids(pairs: list[tuple[User, User]]) -> set[tuple[int, int]]:
    return {(a.id, b.id) for a, b in pairs}


def test_pair_users_all_vs_all_empty():
    users = []
    pairs = pair_users_all_vs_all(users)
    assert pairs == []


def test_pair_users_all_vs_all_single():
    users = [create_mock_user(1)]
    pairs = pair_users_all_vs_all(users)
    assert pairs == []


def test_pair_users_all_vs_all_two_users():
    users = [create_mock_user(1), create_mock_user(2)]
    pairs = pair_users_all_vs_all(users)
    assert len(pairs) == 1
    assert _pair_ids(pairs) == {(1, 2)}


def test_pair_users_all_vs_all_three_users():
    users = [create_mock_user(1), create_mock_user(2), create_mock_user(3)]
    pairs = pair_users_all_vs_all(users)
    assert len(pairs) == 3
    assert _pair_ids(pairs) == {(1, 2), (1, 3), (2, 3)}


def test_pair_users_all_vs_all_five_users_pair_count_and_uniqueness():
    users = [create_mock_user(i) for i in range(1, 6)]
    pairs = pair_users_all_vs_all(users)
    assert len(pairs) == 10  # 5*4/2
    assert len(_pair_ids(pairs)) == 10


def test_pair_users_all_vs_all_everyone_participates_when_n_ge_2():
    users = [create_mock_user(i) for i in range(1, 6)]
    pairs = pair_users_all_vs_all(users)
    involved = {a.id for a, _ in pairs} | {b.id for _, b in pairs}
    assert involved == {1, 2, 3, 4, 5}
