from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
import re

from fastapi import FastAPI, Request
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from koh.api.router import api_router
from koh.core.config import settings
from koh.db.session import init_db
from koh.metrics import RequestTimer, observe_http_request

log = logging.getLogger(__name__)


def _write_telemetry_sync(
    token: str,
    agent_name: str | None,
    model_name: str | None,
    method: str,
    path: str,
) -> None:
    from koh.db.models import AgentTelemetry
    from koh.db.models import Session as UserSession
    from koh.db.models import User
    from koh.db.session import SessionLocal
    from koh.security import utc_now

    db = SessionLocal()
    try:
        now = utc_now().replace(tzinfo=None)
        session = db.query(UserSession).filter(UserSession.token == token).first()
        if not session or session.expires_at <= now:
            return
        user = (
            db.query(User)
            .filter(User.id == session.user_id, User.is_active.is_(True))
            .first()
        )
        if not user:
            return

        changed = False
        if not user.is_agent:
            user.is_agent = True
            changed = True
        if agent_name and user.agent_name != agent_name:
            user.agent_name = agent_name
            changed = True
        if model_name and user.model_name != model_name:
            user.model_name = model_name
            changed = True

        db.add(
            AgentTelemetry(
                user_id=user.id,
                agent_name=agent_name,
                model_name=model_name,
                method=method,
                path=path,
                recorded_at=now,
            )
        )
        if changed:
            db.add(user)
        db.commit()
    except Exception:
        db.rollback()
        log.debug("agent telemetry write failed", exc_info=True)
    finally:
        db.close()


async def _record_telemetry_async(
    token: str,
    agent_name: str | None,
    model_name: str | None,
    method: str,
    path: str,
) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, _write_telemetry_sync, token, agent_name, model_name, method, path
    )

_FINGERPRINTED_ASSET_RE = re.compile(r"-[0-9A-Za-z]{8,}\.")


def create_app() -> FastAPI:
    app = FastAPI(title="Asuri Major API", version="2.0.0")
    package_root = Path(__file__).resolve().parent
    static_root = package_root / "static"
    app_root = static_root / "app"
    artifact_root = package_root / "artifacts"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    def _decode_b64_header(value: str) -> str | None:
        """Decode a base64-encoded telemetry header value; fall back to raw if not valid b64."""
        value = value.strip()
        if not value:
            return None
        try:
            decoded = base64.b64decode(value, validate=True).decode("utf-8", errors="replace").strip()
            return decoded or None
        except Exception:
            # Accept plaintext as fallback so misconfigured agents still get recorded
            return value or None

    @app.middleware("http")
    async def record_agent_telemetry(request: Request, call_next):
        timer = RequestTimer()
        response = await call_next(request)
        path = request.url.path
        observe_http_request(
            request.method,
            path,
            response.status_code,
            timer.elapsed(),
        )
        if path.startswith("/api/") and not path.startswith("/api/artifacts/"):
            agent_name = _decode_b64_header(request.headers.get("x-agent-name", ""))
            model_name = _decode_b64_header(request.headers.get("x-model-name", ""))
            if agent_name or model_name:
                auth = request.headers.get("authorization", "")
                if auth.startswith("Bearer "):
                    token = auth.split(" ", 1)[1].strip()
                    asyncio.create_task(
                        _record_telemetry_async(
                            token, agent_name, model_name, request.method, path
                        )
                    )
        return response

    @app.middleware("http")
    async def apply_security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'")
        path = request.url.path
        if path in {"/", "/dashboard", "/admin", "/replay", "/leaderboard"}:
            response.headers.setdefault("Cache-Control", "no-cache")
        elif path.startswith("/static/app/") and _FINGERPRINTED_ASSET_RE.search(path):
            response.headers.setdefault(
                "Cache-Control", "public, max-age=31536000, immutable"
            )
        return response

    if static_root.exists():
        app.mount("/static", StaticFiles(directory=static_root), name="static")

    def _spa_index() -> FileResponse:
        index_path = app_root / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="frontend build not found")
        return FileResponse(index_path)

    @app.get("/")
    def dashboard_entry() -> FileResponse:
        return _spa_index()

    @app.get("/dashboard")
    def dashboard_alias() -> FileResponse:
        return _spa_index()

    @app.get("/admin")
    def admin_alias() -> FileResponse:
        return _spa_index()

    @app.get("/replay")
    def replay_alias() -> FileResponse:
        return _spa_index()

    @app.get("/leaderboard")
    def leaderboard_alias() -> FileResponse:
        return _spa_index()

    @app.get("/api/artifacts/koh_env.py")
    def download_koh_env() -> FileResponse:
        env_path = Path(__file__).resolve().parent / "game" / "koh_env.py"
        if not env_path.exists():
            raise HTTPException(status_code=404, detail="koh_env.py not found")
        return FileResponse(
            env_path,
            media_type="text/x-python; charset=utf-8",
            filename="koh_env.py",
        )

    @app.get("/api/artifacts/KOH_rules.md")
    def download_koh_rules() -> FileResponse:
        rules_path = artifact_root / "KOH_rules.md"
        if not rules_path.exists():
            raise HTTPException(status_code=404, detail="KOH_rules.md not found")
        return FileResponse(
            rules_path,
            media_type="text/markdown; charset=utf-8",
            filename="KOH_rules.md",
        )

    @app.get("/api/artifacts/score_rule.md")
    def download_score_rules() -> FileResponse:
        score_rules_path = artifact_root / "score_rule.md"
        if not score_rules_path.exists():
            raise HTTPException(status_code=404, detail="score_rule.md not found")
        return FileResponse(
            score_rules_path,
            media_type="text/markdown; charset=utf-8",
            filename="score_rule.md",
        )

    def _llms_txt_response() -> FileResponse:
        llms_path = artifact_root / "llms.txt"
        if not llms_path.exists():
            raise HTTPException(status_code=404, detail="llms.txt not found")
        return FileResponse(
            llms_path,
            media_type="text/plain; charset=utf-8",
            filename="llms.txt",
        )

    @app.get("/llms.txt")
    def download_llms_txt() -> FileResponse:
        return _llms_txt_response()

    @app.get("/api/artifacts/llms.txt")
    def download_llms_txt_artifact() -> FileResponse:
        return _llms_txt_response()

    @app.get("/api/artifacts/koh_baseline_template.py")
    def download_koh_baseline_template() -> FileResponse:
        baseline_path = artifact_root / "koh_baseline_template.py"
        if not baseline_path.exists():
            raise HTTPException(
                status_code=404, detail="koh_baseline_template.py not found"
            )
        return FileResponse(
            baseline_path,
            media_type="text/x-python; charset=utf-8",
            filename="koh_baseline_template.py",
        )

    app.include_router(api_router)
    return app


app = create_app()
