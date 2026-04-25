from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://koh:koh@127.0.0.1:5432/koh"
    redis_url: str = "redis://127.0.0.1:6379/0"
    secret_key: str = "change-me-in-production"
    cors_origins: list[str] = ["*"]
    session_duration_seconds: int = 24 * 60 * 60

    auto_round_enabled: bool = False
    auto_round_interval_minutes: int = 10
    auto_round_competition_starts_at: str = ""
    auto_round_competition_ends_at: str = ""
    auto_round_max_open_rounds: int = 2
    auto_round_max_pending_matches: int = 2000
    auto_round_tick_seconds: int = 30
    auto_round_reconcile_seconds: int = 60

    koh_admin_username: str = "admin"
    koh_admin_password: str = ""


settings = Settings()
