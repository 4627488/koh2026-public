from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from koh.api.deps import get_current_user, get_db
from koh.cache import get_api_cache_sync, set_api_cache_sync
from koh.db.models import Match, ScoreHistory, TestRun, User
from koh.site_config import get_or_create_site_config

router = APIRouter(tags=["leaderboard"])


def _display_name(user: User) -> str:
    return user.public_name


def _competition_leaderboard_rows(db: Session) -> list[dict]:
    users = (
        db.query(User)
        .filter(User.is_active.is_(True), User.is_spectator.is_(False))
        .order_by(User.username.asc())
        .all()
    )
    user_ids = [row.id for row in users]

    stats = defaultdict(
        lambda: {
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "attack_games": 0,
            "attack_wins": 0,
            "defense_games": 0,
            "defense_wins": 0,
            "high_reward_win_score": 0.0,
        }
    )

    if user_ids:
        matches = (
            db.query(Match)
            .filter(
                Match.status.in_(["completed", "failed"]),
                Match.team_a_id.in_(user_ids),
                Match.team_b_id.in_(user_ids),
            )
            .all()
        )

        for row in matches:
            result = row.result_json or {}
            team_a_role = str(result.get("team_a_role", "attack")).lower()
            team_b_role = "defense" if team_a_role == "attack" else "attack"
            team_a_outcome = str(result.get("team_a_outcome", "draw")).lower()
            if team_a_outcome not in {"win", "loss", "draw"}:
                team_a_outcome = "draw"
            if team_a_outcome == "win":
                team_b_outcome = "loss"
            elif team_a_outcome == "loss":
                team_b_outcome = "win"
            else:
                team_b_outcome = "draw"

            score_detail = result.get("score_detail") or {}
            team_a_game_score = float(score_detail.get("team_a_game_score", 0.0) or 0.0)
            team_b_game_score = float(score_detail.get("team_b_game_score", 0.0) or 0.0)
            high_reward_map = bool(score_detail.get("high_reward_map", False))

            for user_id, role, outcome, game_score in (
                (row.team_a_id, team_a_role, team_a_outcome, team_a_game_score),
                (row.team_b_id, team_b_role, team_b_outcome, team_b_game_score),
            ):
                entry = stats[user_id]
                if outcome == "win":
                    entry["wins"] += 1
                    if high_reward_map:
                        entry["high_reward_win_score"] += game_score
                elif outcome == "loss":
                    entry["losses"] += 1
                else:
                    entry["draws"] += 1

                if role == "attack":
                    entry["attack_games"] += 1
                    if outcome == "win":
                        entry["attack_wins"] += 1
                else:
                    entry["defense_games"] += 1
                    if outcome == "win":
                        entry["defense_wins"] += 1

    latest_score_delta: dict[int, float] = {}
    if user_ids:
        histories = (
            db.query(ScoreHistory)
            .filter(ScoreHistory.user_id.in_(user_ids))
            .order_by(ScoreHistory.user_id.asc(), ScoreHistory.round_id.desc())
            .all()
        )
        for row in histories:
            if row.user_id not in latest_score_delta:
                latest_score_delta[row.user_id] = row.delta

    rows = [
        {
            "username": _display_name(row),
            "login_username": row.username,
            "display_name": _display_name(row),
            "score": row.score,
            "is_agent": row.is_agent,
            "wins": stats[row.id]["wins"],
            "draws": stats[row.id]["draws"],
            "losses": stats[row.id]["losses"],
            "attack_win_rate": (
                stats[row.id]["attack_wins"] / stats[row.id]["attack_games"]
                if stats[row.id]["attack_games"]
                else 0.0
            ),
            "defense_win_rate": (
                stats[row.id]["defense_wins"] / stats[row.id]["defense_games"]
                if stats[row.id]["defense_games"]
                else 0.0
            ),
            "score_delta": latest_score_delta.get(row.id, 0.0),
            "_high_reward_win_score": stats[row.id]["high_reward_win_score"],
        }
        for row in users
    ]
    rows.sort(
        key=lambda row: (
            -row["score"],
            -row["wins"],
            -row["_high_reward_win_score"],
            -row["score_delta"],
            row["username"],
        )
    )
    for row in rows:
        row.pop("_high_reward_win_score", None)
    return rows


def _public_leaderboard_payload(db: Session):
    site_cfg = get_or_create_site_config(db)
    phase = site_cfg.phase

    if phase != "test":
        cached = get_api_cache_sync("leaderboard:competition")
        if cached is not None:
            return cached

    if phase == "test":
        return {"ok": True, "data": {"rows": [], "phase": phase}}
    rows = _competition_leaderboard_rows(db)
    result = {"ok": True, "data": {"rows": rows, "phase": phase}}
    set_api_cache_sync("leaderboard:competition", result, 15)
    return result


@router.get("/leaderboard")
def leaderboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    site_cfg = get_or_create_site_config(db)
    if site_cfg.phase == "test":
        if not current_user.is_admin:
            return {"ok": True, "data": {"rows": [], "phase": site_cfg.phase}}

        users = (
            db.query(User)
            .filter(User.is_active.is_(True), User.is_spectator.is_(False))
            .order_by(User.username.asc())
            .all()
        )
        latest_run_by_user: dict[int, TestRun] = {}
        if users:
            user_ids = [row.id for row in users]
            runs = (
                db.query(TestRun)
                .filter(TestRun.user_id.in_(user_ids))
                .order_by(TestRun.user_id.asc(), TestRun.id.desc())
                .all()
            )
            for row in runs:
                if row.user_id not in latest_run_by_user:
                    latest_run_by_user[row.user_id] = row

        rows = []
        for user in users:
            run = latest_run_by_user.get(user.id)
            summary = run.summary_json if run is not None else {}
            rows.append(
                {
                    "username": _display_name(user),
                    "login_username": user.username,
                    "display_name": _display_name(user),
                    "score": float(summary.get("overall_win_rate", 0.0)) * 100.0,
                    "is_agent": user.is_agent,
                    "wins": int(summary.get("wins", 0)),
                    "draws": int(summary.get("draws", 0)),
                    "losses": int(summary.get("losses", 0)),
                    "attack_win_rate": float(summary.get("attack_win_rate", 0.0)),
                    "defense_win_rate": float(summary.get("defense_win_rate", 0.0)),
                    "score_delta": 0.0,
                }
            )
        rows.sort(
            key=lambda row: (
                -row["score"],
                -(row["wins"] + row["draws"] + row["losses"]),
                row["username"],
            )
        )
        return {"ok": True, "data": {"rows": rows, "phase": site_cfg.phase}}

    return _public_leaderboard_payload(db)


@router.get("/public/leaderboard")
def public_leaderboard(db: Session = Depends(get_db)):
    return _public_leaderboard_payload(db)
