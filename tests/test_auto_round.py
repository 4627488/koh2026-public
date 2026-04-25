from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from koh.auto_round import auto_round_due_slot, auto_round_due_slots, auto_round_next_slot


def _config(*, start: datetime, end: datetime, interval_minutes: int = 10):
    return SimpleNamespace(
        competition_starts_at=start,
        competition_ends_at=end,
        interval_minutes=interval_minutes,
    )


def test_auto_round_due_slots_include_all_missed_slots():
    cfg = _config(
        start=datetime(2026, 4, 17, 14, 47, 0),
        end=datetime(2026, 4, 18, 14, 0, 0),
    )

    due = auto_round_due_slots(cfg, datetime(2026, 4, 17, 15, 7, 1))

    assert due == [
        datetime(2026, 4, 17, 14, 47, 0),
        datetime(2026, 4, 17, 14, 57, 0),
        datetime(2026, 4, 17, 15, 7, 0),
    ]


def test_auto_round_due_slots_are_empty_before_start():
    cfg = _config(
        start=datetime(2026, 4, 17, 14, 47, 0),
        end=datetime(2026, 4, 18, 14, 0, 0),
    )

    assert auto_round_due_slots(cfg, datetime(2026, 4, 17, 14, 46, 59)) == []


def test_auto_round_due_slot_and_next_slot_stay_consistent_on_boundary():
    cfg = _config(
        start=datetime(2026, 4, 17, 14, 47, 0),
        end=datetime(2026, 4, 18, 14, 0, 0),
    )

    now = datetime(2026, 4, 17, 14, 57, 0)

    assert auto_round_due_slot(cfg, now) == datetime(2026, 4, 17, 14, 57, 0)
    assert auto_round_next_slot(cfg, now) == datetime(2026, 4, 17, 15, 7, 0)
