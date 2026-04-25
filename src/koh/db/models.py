from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from koh.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_agent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spectator: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    @property
    def public_name(self) -> str:
        return (self.display_name or "").strip() or self.username


class Session(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    strategy_opens_at: Mapped[datetime] = mapped_column(DateTime)  # kept for scheduler compat
    strategy_closes_at: Mapped[datetime] = mapped_column(DateTime)  # kept for scheduler compat
    created_mode: Mapped[str] = mapped_column(String(16), default="manual")
    auto_slot_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class AutoRoundConfig(Base):
    __tablename__ = "auto_round_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=10)
    competition_starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    competition_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    strategy_window_minutes: Mapped[int] = mapped_column(Integer, default=0)  # unused, kept for compat
    max_open_rounds: Mapped[int] = mapped_column(Integer, default=2)
    max_pending_matches: Mapped[int] = mapped_column(Integer, default=2000)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class SiteConfig(Base):
    __tablename__ = "site_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    allow_registration: Mapped[bool] = mapped_column(Boolean, default=True)
    phase: Mapped[str] = mapped_column(String(16), default="competition")
    announcement_title: Mapped[str] = mapped_column(String(160), default="")
    announcement_body: Mapped[str] = mapped_column(Text, default="")
    announcement_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class RegistrationInvite(Base):
    __tablename__ = "registration_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class GameMap(Base):
    __tablename__ = "maps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id"), index=True)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("map_templates.id"), index=True, nullable=True
    )
    map_idx: Mapped[int] = mapped_column(Integer)
    seed: Mapped[str] = mapped_column(String(128))
    difficulty: Mapped[float] = mapped_column(Float, default=0.5)
    layout_json: Mapped[dict] = mapped_column(JSON)


class MapTemplate(Base):
    __tablename__ = "map_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    source_text: Mapped[str] = mapped_column(Text)
    layout_json: Mapped[dict] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    difficulty: Mapped[float] = mapped_column(Float, default=0.5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    round_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # soft reference, no FK
    role: Mapped[str] = mapped_column(String(16))
    stored_path: Mapped[str] = mapped_column(Text)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime)


class Baseline(Base):
    __tablename__ = "baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), unique=True)
    attack_submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"))
    defense_submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class BPPreference(Base):
    __tablename__ = "bp_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    round_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # soft reference, no FK
    # Ordered list of map_idx values, most preferred first.
    # Maps listed earlier get higher weight in the weighted random map selection.
    map_preferences: Mapped[list] = mapped_column(JSON, default=list)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id"), index=True)
    map_id: Mapped[int] = mapped_column(ForeignKey("maps.id"), index=True)
    team_a_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    team_b_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Replay(Base):
    __tablename__ = "replays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    map_id: Mapped[int] = mapped_column(ForeignKey("maps.id"), index=True)
    frames_path: Mapped[str] = mapped_column(Text)


class ScoreHistory(Base):
    __tablename__ = "score_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id"), index=True)
    score_before: Mapped[float] = mapped_column(Float)
    score_after: Mapped[float] = mapped_column(Float)
    delta: Mapped[float] = mapped_column(Float)


class SubmissionBundle(Base):
    __tablename__ = "submission_bundles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    attack_submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    defense_submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    bp_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bundle_id: Mapped[int] = mapped_column(ForeignKey("submission_bundles.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    baseline_pack_version: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    queued_at: Mapped[datetime] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentTelemetry(Base):
    __tablename__ = "agent_telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    agent_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    method: Mapped[str] = mapped_column(String(16))
    path: Mapped[str] = mapped_column(String(256))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class TestMatch(Base):
    __tablename__ = "test_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), index=True)
    contestant_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    baseline_id: Mapped[int | None] = mapped_column(ForeignKey("baselines.id"), index=True, nullable=True)
    attack_submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    defense_submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    map_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("map_templates.id"), index=True, nullable=True
    )
    map_idx: Mapped[int] = mapped_column(Integer)
    map_name: Mapped[str] = mapped_column(String(128))
    layout_json: Mapped[dict] = mapped_column(JSON)
    team_a_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    team_b_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    replay_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
