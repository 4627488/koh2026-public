from __future__ import annotations

import logging
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from koh.core.config import settings

log = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
    pool_timeout=10,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# alembic.ini lives at the project root, which is 4 levels above this file:
# src/koh/db/session.py -> src/koh/db -> src/koh -> src -> <project root>
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _run_migrations() -> None:
    # Do NOT pass the ini file path — doing so triggers fileConfig() inside
    # env.py which calls logging.config.fileConfig with disable_existing_loggers=True,
    # silencing uvicorn and all other existing loggers.
    cfg = AlembicConfig()
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    cfg.set_main_option("script_location", str(_PROJECT_ROOT / "migrations"))
    alembic_command.upgrade(cfg, "head")


def _bootstrap_admin() -> None:
    import sys

    from koh.db.models import User
    from koh.security import hash_password, utc_now

    with SessionLocal() as session:
        any_user_exists = session.execute(select(User.id).limit(1)).first() is not None
        existing = session.execute(
            select(User).where(User.username == settings.koh_admin_username)
        ).scalar_one_or_none()

        # Enforce admin bootstrap password only on first-time initialization.
        if not any_user_exists and not settings.koh_admin_password:
            print(
                "\n[KOH] FATAL: KOH_ADMIN_PASSWORD is not set.\n"
                "      Database is empty, so an initial admin password is required.\n"
                "      Example: export KOH_ADMIN_PASSWORD='your_strong_password'\n",
                file=sys.stderr,
                flush=True,
            )
            sys.exit(1)

        if existing is None:
            if not settings.koh_admin_password:
                log.info(
                    "Bootstrap skipped: admin user '%s' does not exist, but KOH_ADMIN_PASSWORD is not set.",
                    settings.koh_admin_username,
                )
                return
            admin = User(
                username=settings.koh_admin_username,
                display_name=settings.koh_admin_username,
                password_hash=hash_password(settings.koh_admin_password),
                is_admin=True,
                is_active=True,
                score=0.0,
                created_at=utc_now().replace(tzinfo=None),
            )
            session.add(admin)
            session.commit()
            log.info("Bootstrap: admin user '%s' created.", settings.koh_admin_username)
        else:
            log.debug(
                "Bootstrap: admin user '%s' already exists.",
                settings.koh_admin_username,
            )


def init_db() -> None:
    from koh.db import models  # noqa: F401 — ensure models are registered

    log.info("Running database migrations…")
    _run_migrations()
    log.info("Migrations complete. Bootstrapping admin user…")
    _bootstrap_admin()
    log.info("Database ready.")
