from __future__ import annotations

from fastapi import APIRouter

from koh.api.routes import admin, auth, leaderboard, matches, metrics, rounds, status, submissions, test_eval, users, ws

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/api")
api_router.include_router(metrics.router, prefix="/api")
api_router.include_router(status.router, prefix="/api")
api_router.include_router(rounds.router, prefix="/api")
api_router.include_router(submissions.router, prefix="/api")
api_router.include_router(test_eval.router, prefix="/api")
api_router.include_router(matches.router, prefix="/api")
api_router.include_router(leaderboard.router, prefix="/api")
api_router.include_router(users.router, prefix="/api")
api_router.include_router(admin.router, prefix="/api")
api_router.include_router(ws.router)
