from __future__ import annotations

import calendar
import json
import os
import random
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from celery import group
from redis import Redis
from sqlalchemy import intersect, select, update as sa_update
from sqlalchemy.exc import IntegrityError

from koh.cache import invalidate_api_caches_sync
from koh.core.config import settings
from koh.auto_round import get_or_create_auto_round_config
from koh.auto_round import auto_round_schedule_state
from koh.auto_round import auto_round_due_slots
from koh.site_config import get_or_create_site_config
from koh.db.models import (
    Baseline,
    BPPreference,
    GameMap,
    MapTemplate,
    Match,
    Replay,
    Round,
    ScoreHistory,
    Submission,
    SubmissionBundle,
    TestMatch,
    TestRun,
    User,
)
from koh.db.session import SessionLocal
from koh.game.koh_env import DEFAULT_MAP, KOHBattleEnv, MapLayout, RoundLayout, make_round_layout
from koh.game.map_pool import ensure_round_maps, list_map_templates
from koh.scoring import (
    HIGH_REWARD_THRESHOLD,
    ROUND_HISTORY_WINDOW,
    active_challenge_factor,
    base_score_for_outcome,
    bp_breadth_factor,
    compute_coldness_by_key,
    infer_outcomes,
    map_reward_factor,
    normalize_round_score,
    sanitize_bp_preferences,
)
from koh.tasks.celery_app import celery_app
from koh.tasks.matching import (
    pair_users_all_vs_all,
)
from koh.security import utc_now

ROUND_EVENT_CHANNEL_TEMPLATE = "koh:round:{round_id}:events"
TEST_RUN_EVENT_CHANNEL_TEMPLATE = "koh:test-run:{run_id}:events"
_redis_client: Redis | None = None


@contextmanager
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _data_dir() -> Path:
    return Path(os.getenv("KOH_DATA_DIR", "data"))


def _get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _round_event_channel(round_id: int) -> str:
    return ROUND_EVENT_CHANNEL_TEMPLATE.format(round_id=round_id)


def _test_run_event_channel(run_id: int) -> str:
    return TEST_RUN_EVENT_CHANNEL_TEMPLATE.format(run_id=run_id)


def _publish_round_event(round_id: int, event_type: str, payload: dict) -> None:
    message = {
        "type": event_type,
        "round_id": round_id,
        "payload": payload,
    }
    try:
        _get_redis_client().publish(
            _round_event_channel(round_id),
            json.dumps(message, ensure_ascii=True, separators=(",", ":")),
        )
    except Exception:
        # Events are best-effort. Task execution must not fail because realtime push is unavailable.
        return


def _publish_test_run_event(run_id: int, event_type: str, payload: dict) -> None:
    message = {
        "type": event_type,
        "test_run_id": run_id,
        "payload": payload,
    }
    try:
        _get_redis_client().publish(
            _test_run_event_channel(run_id),
            json.dumps(message, ensure_ascii=True, separators=(",", ":")),
        )
    except Exception:
        return


def _resolve_submission_path(stored_path_str: str) -> Path:
    stored_path = Path(stored_path_str)
    resolved_path: Path | None = None

    if stored_path.is_absolute():
        if stored_path.exists():
            resolved_path = stored_path
    else:
        data_dir = _data_dir()
        candidates = [
            stored_path,
            Path.cwd() / stored_path,
            data_dir / stored_path,
        ]
        for candidate in candidates:
            if candidate.exists():
                resolved_path = candidate
                break

    if resolved_path is None:
        raise ValueError(f"submission file not found: path={stored_path_str}")
    return resolved_path


def _pick_policy(round_id: int, user_id: int, role: str) -> WeightPolicy:
    from koh.ml.policies import WeightPolicy, load_weight_policy

    with db_session() as db:
        # Always use the latest submission regardless of round.
        submission = (
            db.query(Submission)
            .filter(
                Submission.user_id == user_id,
                Submission.role == role,
            )
            .order_by(Submission.uploaded_at.desc())
            .first()
        )
    if submission is None:
        raise ValueError(
            f"missing submission: user_id={user_id}, role={role}, round_id={round_id}"
        )

    resolved_path = _resolve_submission_path(submission.stored_path)

    valid, msg = WeightPolicy.validate_submission(resolved_path)
    if not valid:
        raise ValueError(
            f"invalid submission weights: user_id={user_id}, role={role}, round_id={round_id}, error={msg}"
        )
    return load_weight_policy(resolved_path)


def _load_policy_from_submission(submission_id: int):
    from koh.ml.policies import WeightPolicy, load_weight_policy

    with db_session() as db:
        submission = (
            db.query(Submission).filter(Submission.id == submission_id).first()
        )
    if submission is None:
        raise ValueError(f"missing submission: submission_id={submission_id}")

    resolved_path = _resolve_submission_path(submission.stored_path)
    valid, msg = WeightPolicy.validate_submission(resolved_path)
    if not valid:
        raise ValueError(
            f"invalid submission weights: submission_id={submission_id}, error={msg}"
        )
    return load_weight_policy(resolved_path)


def _weighted_map_pick(map_idx_pool: set[int], pref_a: list[int], pref_b: list[int]) -> int:
    """Select one map from the pool using weighted random sampling.

    Maps preferred by at least one player are weighted by preference rank.
    Maps not listed by either player are excluded (weight 0) when any
    preferences exist.  If neither player submitted preferences, all maps
    are weighted equally.
    """
    pool = sorted(map_idx_pool)
    if not pool:
        raise ValueError("empty map pool")
    if len(pool) == 1:
        return pool[0]

    n = len(pool)
    rank_a = {idx: i for i, idx in enumerate(pref_a)}
    rank_b = {idx: i for i, idx in enumerate(pref_b)}

    # Maps selected by at least one player that are actually in the pool
    preferred_in_pool = (set(pref_a) | set(pref_b)) & set(pool)
    has_any_pref = bool(preferred_in_pool)

    weights = []
    for map_idx in pool:
        if has_any_pref and map_idx not in preferred_in_pool:
            # Neither player wants this map — exclude it
            w = 0
        else:
            w = 1  # base weight (used only when no preferences exist)
            if map_idx in rank_a:
                w += n - rank_a[map_idx]  # rank 0 (most preferred) adds n
            if map_idx in rank_b:
                w += n - rank_b[map_idx]
        weights.append(w)

    # Safety fallback: if all weights are 0 (shouldn't happen), go uniform
    if not any(weights):
        weights = [1] * len(pool)

    return random.choices(pool, weights=weights, k=1)[0]

def _map_key(game_map: GameMap) -> str:
    if game_map.template_id is not None:
        return f"template:{game_map.template_id}"
    return f"seed:{game_map.seed}"


def _to_slot_start(now: datetime, interval_minutes: int) -> datetime:
    interval_seconds = max(60, int(interval_minutes) * 60)
    ts = calendar.timegm(now.timetuple())
    slot_ts = ts - (ts % interval_seconds)
    return datetime.utcfromtimestamp(slot_ts)


def _start_round(round_id: int) -> None:
    """Immediately kick off match creation and finalization for a round."""
    celery_app.send_task("koh.tasks.close_strategy_window", args=[round_id])
    celery_app.send_task("koh.tasks.watch_and_finalize", args=[round_id], countdown=5)


def _users_with_both_roles_submitted():
    attack_user_ids = select(Submission.user_id).where(Submission.role == "attack").distinct()
    defense_user_ids = select(Submission.user_id).where(Submission.role == "defense").distinct()
    bp_user_ids = select(BPPreference.user_id).distinct()
    return intersect(attack_user_ids, defense_user_ids, bp_user_ids)


def _run_battle(
    *,
    layout_payload: dict,
    team_a_role_seed: str,
    team_a_policy,
    team_b_policy,
):
    if "map_layout" in layout_payload:
        layout = RoundLayout.from_dict(layout_payload)
    else:
        layout = make_round_layout(round_id=0, map_layout=DEFAULT_MAP)

    team_a_role = str(team_a_role_seed or "attack").lower()
    if team_a_role not in {"attack", "defense"}:
        team_a_role = "attack"
    team_b_role = "defense" if team_a_role == "attack" else "attack"

    if team_a_role == "attack":
        attacker_policy = team_a_policy
        defender_policy = team_b_policy
    else:
        attacker_policy = team_b_policy
        defender_policy = team_a_policy

    env = KOHBattleEnv(layout=layout)
    payload = env.run_match(attacker_policy, defender_policy, capture_replay=True)
    result = payload["result"]
    replay_data = payload.get("replay")

    winner = str(result.get("winner", "draw")).lower()
    if winner == "draw":
        team_a_outcome = "draw"
        team_b_outcome = "draw"
        winner_user_id = None
    elif winner == "attacker":
        if team_a_role == "attack":
            team_a_outcome = "win"
            team_b_outcome = "loss"
            winner_user_id = "team_a"
        else:
            team_a_outcome = "loss"
            team_b_outcome = "win"
            winner_user_id = "team_b"
    elif winner == "defender":
        if team_a_role == "defense":
            team_a_outcome = "win"
            team_b_outcome = "loss"
            winner_user_id = "team_a"
        else:
            team_a_outcome = "loss"
            team_b_outcome = "win"
            winner_user_id = "team_b"
    else:
        team_a_outcome = "draw"
        team_b_outcome = "draw"
        winner_user_id = None

    normalized_result = {
        **result,
        "team_a_role": team_a_role,
        "team_b_role": team_b_role,
        "team_a_outcome": team_a_outcome,
        "team_b_outcome": team_b_outcome,
        "winner_ref": winner_user_id,
    }
    return normalized_result, replay_data


@celery_app.task(name="koh.tasks.close_strategy_window")
def close_strategy_window(round_id: int):
    with db_session() as db:
        round_row = db.query(Round).filter(Round.id == round_id).first()
        if round_row is None:
            return {"ok": False, "round_id": round_id, "error": "round not found"}

        maps = ensure_round_maps(db, round_id)

        # Only include users who have submitted BOTH attack and defense models.
        submitted_user_ids = _users_with_both_roles_submitted()
        users = (
            db.query(User)
            .filter(User.is_active.is_(True), User.is_spectator.is_(False), User.id.in_(submitted_user_ids))
            .order_by(User.score.asc(), User.id.asc())
            .all()
        )
        pairs = pair_users_all_vs_all(users)

        queued_matches: list[int] = []

        if pairs:
            maps_by_idx = {row.map_idx: row for row in maps}
            existing = (
                db.query(Match)
                .filter(Match.round_id == round_id)
                .order_by(Match.id.asc())
                .all()
            )
            if existing:
                for row in existing:
                    if row.status in {"queued", "running", "failed"}:
                        queued_matches.append(row.id)
            else:
                # Fetch all BP preferences for involved users in one query
                involved_ids = [u.id for pair in pairs for u in pair]
                bp_rows = (
                    db.query(BPPreference)
                    .filter(BPPreference.user_id.in_(involved_ids))
                    .all()
                )
                bp_by_user = {row.user_id: row for row in bp_rows}

                new_match_rows: list[Match] = []
                for team_a, team_b in pairs:
                    pref_a = list(bp_by_user[team_a.id].map_preferences) if team_a.id in bp_by_user else []
                    pref_b = list(bp_by_user[team_b.id].map_preferences) if team_b.id in bp_by_user else []

                    selected_map_idx = _weighted_map_pick(set(maps_by_idx.keys()), pref_a, pref_b)
                    game_map = maps_by_idx[selected_map_idx]

                    # BO2: game 1 team_a attacks, game 2 team_a defends
                    for game_no, (team_a_role, team_b_role) in enumerate(
                        [("attack", "defense"), ("defense", "attack")], start=1
                    ):
                        row = Match(
                            round_id=round_id,
                            map_id=game_map.id,
                            team_a_id=team_a.id,
                            team_b_id=team_b.id,
                            status="queued",
                            result_json={
                                "team_a_role": team_a_role,
                                "team_b_role": team_b_role,
                                "game_no": game_no,
                                "selected_map_idx": selected_map_idx,
                            },
                        )
                        db.add(row)
                        new_match_rows.append(row)

                # Single flush for all matches instead of one per match
                db.flush()
                queued_matches.extend(row.id for row in new_match_rows)

        round_row.status = "running"
        db.commit()

    if queued_matches:
        scheduled = group(
            celery_app.signature("koh.tasks.run_match", args=[match_id])
            for match_id in queued_matches
        )
        scheduled.apply_async()

    _publish_round_event(
        round_id,
        "round_status_changed",
        {
            "status": "running",
            "scheduled_matches": len(queued_matches),
        },
    )

    return {
        "ok": True,
        "round_id": round_id,
        "status": "running",
        "scheduled_matches": len(queued_matches),
    }


@celery_app.task(name="koh.tasks.run_match")
def run_match(match_id: int):
    from koh.ml.policies import WeightPolicy, load_weight_policy

    # Phase 1: fetch all needed data, then release the DB connection immediately.
    # Do NOT hold it during the multi-second game simulation.
    with db_session() as db:
        match = db.query(Match).filter(Match.id == match_id).first()
        if match is None:
            return {"ok": False, "match_id": match_id, "error": "match not found"}
        game_map = db.query(GameMap).filter(GameMap.id == match.map_id).first()
        if game_map is None:
            match.status = "failed"
            match.result_json = {"error": "map not found"}
            db.commit()
            return {"ok": False, "match_id": match_id, "error": "map not found"}

        layout_payload = game_map.layout_json or {}
        seed_result = dict(match.result_json or {})
        team_a_role = str(seed_result.get("team_a_role", "attack")).lower()
        team_b_role = "defense" if team_a_role == "attack" else "attack"
        round_id = match.round_id
        team_a_id = match.team_a_id
        team_b_id = match.team_b_id
        map_id = match.map_id
        game_no = seed_result.get("game_no")

        # Fetch submission paths in the same session to avoid extra connections
        def _get_submission_path(user_id: int, role: str) -> str:
            sub = (
                db.query(Submission)
                .filter(Submission.user_id == user_id, Submission.role == role)
                .order_by(Submission.uploaded_at.desc())
                .first()
            )
            if sub is None:
                raise ValueError(f"missing submission: user_id={user_id}, role={role}")
            return sub.stored_path

        try:
            team_a_stored = _get_submission_path(team_a_id, team_a_role)
            team_b_stored = _get_submission_path(team_b_id, team_b_role)
        except ValueError as e:
            match.status = "failed"
            match.result_json = {"error": str(e)}
            db.commit()
            _publish_round_event(round_id, "match_status_changed",
                                 {"match_id": match_id, "status": "failed", "error": str(e)})
            return {"ok": False, "match_id": match_id, "status": "failed", "error": str(e)}

    # Phase 2: load model weights from disk — no DB connection needed
    try:
        team_a_path = _resolve_submission_path(team_a_stored)
        team_b_path = _resolve_submission_path(team_b_stored)
        for path, label in [(team_a_path, "team_a"), (team_b_path, "team_b")]:
            valid, msg = WeightPolicy.validate_submission(path)
            if not valid:
                raise ValueError(f"invalid weights {label}: {msg}")
        team_a_policy = load_weight_policy(team_a_path)
        team_b_policy = load_weight_policy(team_b_path)
    except Exception as error:
        with db_session() as db:
            m = db.query(Match).filter(Match.id == match_id).first()
            if m:
                m.status = "failed"
                m.result_json = {"error": str(error)}
                db.commit()
        _publish_round_event(round_id, "match_status_changed",
                             {"match_id": match_id, "status": "failed", "error": str(error)})
        return {"ok": False, "match_id": match_id, "status": "failed", "error": str(error)}

    # Phase 3: mark running (quick write, release immediately)
    with db_session() as db:
        m = db.query(Match).filter(Match.id == match_id).first()
        if m:
            m.status = "running"
            db.commit()
    _publish_round_event(round_id, "match_status_changed", {"match_id": match_id, "status": "running"})

    # Phase 4: run the game — NO DB connection held during simulation
    try:
        normalized_result, replay_data = _run_battle(
            layout_payload=layout_payload,
            team_a_role_seed=team_a_role,
            team_a_policy=team_a_policy,
            team_b_policy=team_b_policy,
        )

        replay_dir = _data_dir() / "replays"
        replay_dir.mkdir(parents=True, exist_ok=True)
        replay_path = replay_dir / f"match_{match_id}.json"
        if replay_data is not None:
            replay_path.write_text(
                json.dumps(replay_data, ensure_ascii=True, separators=(",", ":")),
                encoding="utf-8",
            )

        winner_ref = normalized_result.pop("winner_ref", None)
        winner_user_id = (
            team_a_id if winner_ref == "team_a"
            else team_b_id if winner_ref == "team_b"
            else None
        )
        normalized_result["winner_user_id"] = winner_user_id
        normalized_result["game_no"] = game_no

        # Phase 5: save results (quick write, release immediately)
        with db_session() as db:
            m = db.query(Match).filter(Match.id == match_id).first()
            if m:
                m.status = "completed"
                m.result_json = normalized_result
            replay_row = db.query(Replay).filter(Replay.match_id == match_id).first()
            if replay_row is None:
                db.add(Replay(match_id=match_id, map_id=map_id, frames_path=str(replay_path)))
            else:
                replay_row.frames_path = str(replay_path)
            db.commit()

        _publish_round_event(
            round_id, "match_status_changed",
            {
                "match_id": match_id,
                "status": "completed",
                "winner": normalized_result.get("winner"),
                "winner_user_id": normalized_result.get("winner_user_id"),
            },
        )
        return {
            "ok": True,
            "match_id": match_id,
            "status": "completed",
            "winner": normalized_result.get("winner"),
        }

    except Exception as error:
        with db_session() as db:
            m = db.query(Match).filter(Match.id == match_id).first()
            if m:
                m.status = "failed"
                m.result_json = {"error": str(error)}
                db.commit()
        _publish_round_event(
            round_id, "match_status_changed",
            {"match_id": match_id, "status": "failed", "error": str(error)},
        )
        return {"ok": False, "match_id": match_id, "status": "failed", "error": str(error)}


@celery_app.task(name="koh.tasks.finalize_round")
def finalize_round(round_id: int):
    with db_session() as db:
        round_row = db.query(Round).filter(Round.id == round_id).first()
        if round_row is None:
            return {"ok": False, "round_id": round_id, "error": "round not found"}

        if round_row.created_mode == "test":
            return {
                "ok": False,
                "round_id": round_id,
                "error": "test phase does not use rounds",
            }

        if round_row.status == "completed":
            return {"ok": True, "round_id": round_id, "status": "completed"}

        pending = (
            db.query(Match)
            .filter(
                Match.round_id == round_id,
                Match.status.in_(["queued", "running"]),
            )
            .count()
        )
        if pending > 0:
            _publish_round_event(
                round_id,
                "round_settlement_waiting",
                {"pending_matches": pending},
            )
            return {
                "ok": False,
                "round_id": round_id,
                "status": "running",
                "pending_matches": pending,
            }

        failed = (
            db.query(Match)
            .filter(
                Match.round_id == round_id,
                Match.status == "failed",
            )
            .count()
        )

        matches = (
            db.query(Match)
            .filter(
                Match.round_id == round_id,
                Match.status.in_(["completed", "failed"]),
            )
            .order_by(Match.id.asc())
            .all()
        )

        round_maps = ensure_round_maps(db, round_id)
        maps_by_id = {row.id: row for row in round_maps}
        map_indices = [row.map_idx for row in round_maps]
        total_maps = len(round_maps)
        current_map_keys = [_map_key(row) for row in round_maps]
        current_map_key_by_id = {row.id: _map_key(row) for row in round_maps}

        involved_user_ids: set[int] = set()
        for row in matches:
            involved_user_ids.add(row.team_a_id)
            involved_user_ids.add(row.team_b_id)

        users = (
            db.query(User).filter(User.id.in_(list(involved_user_ids))).all()
            if involved_user_ids
            else []
        )
        users_by_id = {row.id: row for row in users}

        bp_rows = (
            db.query(BPPreference)
            .filter(BPPreference.user_id.in_(list(involved_user_ids)))
            .all()
            if involved_user_ids
            else []
        )
        raw_bp_by_user = {row.user_id: list(row.map_preferences or []) for row in bp_rows}
        sanitized_bp_by_user = {
            user_id: sanitize_bp_preferences(raw_bp_by_user.get(user_id, []), map_indices)
            for user_id in involved_user_ids
        }
        breadth_factor_by_user = {
            user_id: bp_breadth_factor(len(sanitized_bp_by_user.get(user_id, [])), total_maps)
            for user_id in involved_user_ids
        }

        recent_rounds = (
            db.query(Round)
            .filter(
                Round.status == "completed",
                Round.created_mode != "test",
                Round.id != round_id,
            )
            .order_by(Round.created_at.desc(), Round.id.desc())
            .limit(ROUND_HISTORY_WINDOW)
            .all()
        )
        recent_round_ids = [row.id for row in recent_rounds]
        recent_round_map_keys: list[str] = []
        if recent_round_ids:
            historical_matches = (
                db.query(Match)
                .filter(
                    Match.round_id.in_(recent_round_ids),
                    Match.status.in_(["completed", "failed"]),
                )
                .order_by(Match.id.asc())
                .all()
            )
            historical_map_ids = {
                row.map_id
                for row in historical_matches
                if int((row.result_json or {}).get("game_no", 1)) == 1
            }
            historical_maps = (
                db.query(GameMap).filter(GameMap.id.in_(list(historical_map_ids))).all()
                if historical_map_ids
                else []
            )
            historical_map_by_id = {row.id: row for row in historical_maps}
            for row in historical_matches:
                if int((row.result_json or {}).get("game_no", 1)) != 1:
                    continue
                game_map = historical_map_by_id.get(row.map_id)
                if game_map is None:
                    continue
                recent_round_map_keys.append(_map_key(game_map))

        coldness_by_key = compute_coldness_by_key(current_map_keys, recent_round_map_keys)

        initial_scores = {user_id: users_by_id[user_id].score for user_id in users_by_id}
        raw_scores = {user_id: 0.0 for user_id in users_by_id}
        # Collect result_json updates without touching ORM identity map (avoids 1200 individual UPDATEs)
        match_result_updates: list[dict] = []

        for row in matches:
            game_map = maps_by_id.get(row.map_id)
            if game_map is None:
                continue

            result = dict(row.result_json or {})
            team_a_outcome, team_b_outcome = infer_outcomes(
                result,
                fallback_failed_to_draw=(row.status == "failed"),
            )
            result["team_a_outcome"] = team_a_outcome
            result["team_b_outcome"] = team_b_outcome

            map_key = current_map_key_by_id.get(game_map.id, _map_key(game_map))
            coldness = coldness_by_key.get(map_key, 0.5)
            map_factor = map_reward_factor(coldness, game_map.difficulty)

            team_a_bp = sanitized_bp_by_user.get(row.team_a_id, [])
            team_b_bp = sanitized_bp_by_user.get(row.team_b_id, [])
            team_a_breadth = breadth_factor_by_user.get(row.team_a_id, bp_breadth_factor(0, total_maps))
            team_b_breadth = breadth_factor_by_user.get(row.team_b_id, bp_breadth_factor(0, total_maps))
            team_a_active = active_challenge_factor(team_a_bp, game_map.map_idx, total_maps)
            team_b_active = active_challenge_factor(team_b_bp, game_map.map_idx, total_maps)
            team_a_base = base_score_for_outcome(team_a_outcome)
            team_b_base = base_score_for_outcome(team_b_outcome)
            team_a_game_score = team_a_base * map_factor * team_a_breadth * team_a_active
            team_b_game_score = team_b_base * map_factor * team_b_breadth * team_b_active

            raw_scores[row.team_a_id] = raw_scores.get(row.team_a_id, 0.0) + team_a_game_score
            raw_scores[row.team_b_id] = raw_scores.get(row.team_b_id, 0.0) + team_b_game_score

            result["score_detail"] = {
                "settlement_applied": True,
                "treated_as_draw": row.status == "failed",
                "map_key": map_key,
                "map_idx": game_map.map_idx,
                "map_difficulty": game_map.difficulty,
                "map_coldness": coldness,
                "map_factor": map_factor,
                "high_reward_map": map_factor >= HIGH_REWARD_THRESHOLD,
                "team_a_base_score": team_a_base,
                "team_b_base_score": team_b_base,
                "team_a_breadth_factor": team_a_breadth,
                "team_b_breadth_factor": team_b_breadth,
                "team_a_active_factor": team_a_active,
                "team_b_active_factor": team_b_active,
                "team_a_game_score": team_a_game_score,
                "team_b_game_score": team_b_game_score,
            }
            match_result_updates.append({"id": row.id, "result_json": result})

        # Fetch all ScoreHistory rows for this round in one query (avoid N+1)
        existing_histories = {
            row.user_id: row
            for row in db.query(ScoreHistory)
            .filter(
                ScoreHistory.round_id == round_id,
                ScoreHistory.user_id.in_(list(involved_user_ids)),
            )
            .all()
        }

        participant_count = len(users_by_id)
        user_score_updates: list[dict] = []
        for user_id, user in users_by_id.items():
            before = initial_scores[user_id]
            delta = normalize_round_score(raw_scores.get(user_id, 0.0), participant_count)
            after = before + delta
            user_score_updates.append({"id": user_id, "score": after})

            history = existing_histories.get(user_id)
            if history is None:
                db.add(ScoreHistory(
                    user_id=user_id,
                    round_id=round_id,
                    score_before=before,
                    score_after=after,
                    delta=delta,
                ))
            else:
                history.score_before = before
                history.score_after = after
                history.delta = delta

        # Bulk-write all match result_json and user scores in two batched statements
        if match_result_updates:
            db.execute(sa_update(Match), match_result_updates)
        if user_score_updates:
            db.execute(sa_update(User), user_score_updates)

        round_row.status = "completed"
        db.commit()
        invalidate_api_caches_sync(
            "leaderboard:competition",
            f"round:matches:{round_id}",
            "rounds:list:50",
            "status",
        )
        _publish_round_event(
            round_id,
            "round_status_changed",
            {
                "status": "completed",
                "settled_users": len(users_by_id),
                "settled_matches": len(matches),
                "failed_matches": failed,
            },
        )
        return {
            "ok": True,
            "round_id": round_id,
            "status": "completed",
            "settled_users": len(users_by_id),
            "settled_matches": len(matches),
            "failed_matches": failed,
        }


@celery_app.task(name="koh.tasks.watch_and_finalize", bind=True, max_retries=240)
def watch_and_finalize(self, round_id: int):
    """Poll until all matches complete, then trigger finalize_round.

    Retries every 15 s for up to 240 × 15 s = 60 min before giving up.
    """
    with db_session() as db:
        round_row = db.query(Round).filter(Round.id == round_id).first()
        if round_row is None:
            return {"ok": False, "error": "round not found"}
        if round_row.created_mode == "test":
            return {"ok": False, "error": "test phase does not use rounds"}
        if round_row.status == "completed":
            return {"ok": True, "status": "already_completed"}

        pending = (
            db.query(Match)
            .filter(
                Match.round_id == round_id,
                Match.status.in_(["queued", "running"]),
            )
            .count()
        )

    if pending > 0:
        raise self.retry(countdown=15)

    finalize_round.delay(round_id)
    return {"ok": True, "round_id": round_id, "triggered": "finalize_round"}


@celery_app.task(name="koh.tasks.auto_round_tick")
def auto_round_tick(force: bool = False):
    now = utc_now().replace(tzinfo=None)
    created_rounds: list[tuple[int, datetime]] = []

    with db_session() as db:
        config = get_or_create_auto_round_config(db)
        schedule_state = auto_round_schedule_state(config, now)
        if schedule_state == "disabled":
            return {"ok": True, "status": "disabled"}
        if schedule_state == "unscheduled":
            return {"ok": True, "status": "unscheduled"}
        if schedule_state == "invalid":
            return {"ok": True, "status": "invalid_schedule"}
        if schedule_state == "before_start":
            return {
                "ok": True,
                "status": "before_start",
                "competition_starts_at": config.competition_starts_at.isoformat() if config.competition_starts_at else None,
            }
        if schedule_state == "finished":
            return {
                "ok": True,
                "status": "finished",
                "competition_ends_at": config.competition_ends_at.isoformat() if config.competition_ends_at else None,
            }
        due_slots = auto_round_due_slots(config, now)
        if not due_slots:
            return {"ok": True, "status": "no_due_slot"}

        existing_slot_rows = (
            db.query(Round.auto_slot_start)
            .filter(
                Round.created_mode == "auto",
                Round.auto_slot_start.isnot(None),
                Round.auto_slot_start >= due_slots[0],
                Round.auto_slot_start <= due_slots[-1],
            )
            .all()
        )
        existing_slots = {row[0] for row in existing_slot_rows if row[0] is not None}
        missing_slots = [slot for slot in due_slots if slot not in existing_slots]
        if not missing_slots:
            return {
                "ok": True,
                "status": "up_to_date",
                "latest_slot_start": due_slots[-1].isoformat(),
            }

        running_rounds = (
            db.query(Round)
            .filter(Round.status == "running", Round.created_mode != "test")
            .count()
        )
        pending_matches = (
            db.query(Match)
            .filter(Match.status.in_(["queued", "running"]))
            .count()
        )
        if pending_matches >= config.max_pending_matches and not force:
            return {
                "ok": True,
                "status": "pending_limit_reached",
                "pending_matches": pending_matches,
                "max_pending_matches": config.max_pending_matches,
                "missing_slots": [slot.isoformat() for slot in missing_slots],
            }

        available_open_rounds = max(0, config.max_open_rounds - running_rounds)
        if available_open_rounds <= 0 and not force:
            return {
                "ok": True,
                "status": "open_round_limit_reached",
                "running_rounds": running_rounds,
                "max_open_rounds": config.max_open_rounds,
                "missing_slots": [slot.isoformat() for slot in missing_slots],
            }

        slots_to_create = missing_slots if force else missing_slots[:available_open_rounds]
        if not slots_to_create:
            return {
                "ok": True,
                "status": "no_slots_selected",
                "missing_slots": [slot.isoformat() for slot in missing_slots],
            }

        for slot_start in slots_to_create:
            lock_key = f"koh:auto-round:slot:{int(slot_start.timestamp())}"
            lock_acquired = _get_redis_client().set(lock_key, "1", nx=True, ex=120)
            if not lock_acquired and not force:
                continue

            existing = (
                db.query(Round)
                .filter(Round.auto_slot_start == slot_start)
                .order_by(Round.id.desc())
                .first()
            )
            if existing is not None:
                continue

            row = Round(
                status="running",
                strategy_opens_at=slot_start,
                strategy_closes_at=slot_start,  # instantaneous: no window
                created_mode="auto",
                auto_slot_start=slot_start,
                created_at=now,
            )
            db.add(row)
            try:
                db.flush()
                created_round_id = row.id
                ensure_round_maps(db, created_round_id)
                db.commit()
            except IntegrityError:
                db.rollback()
                existing = (
                    db.query(Round)
                    .filter(Round.auto_slot_start == slot_start)
                    .order_by(Round.id.desc())
                    .first()
                )
                if existing is None:
                    return {
                        "ok": False,
                        "status": "integrity_error",
                        "slot_start": slot_start.isoformat(),
                    }
                continue
            except Exception:
                db.rollback()
                raise

            created_rounds.append((created_round_id, slot_start))

    for created_round_id, slot_start in created_rounds:
        _start_round(created_round_id)
        _publish_round_event(
            created_round_id,
            "round_auto_created",
            {"round_id": created_round_id, "slot_start": slot_start.isoformat()},
        )

    if not created_rounds:
        return {
            "ok": True,
            "status": "locked_or_exists",
            "missing_slots": [slot.isoformat() for slot in missing_slots],
        }

    created_slot_set = {slot for _, slot in created_rounds}
    return {
        "ok": True,
        "status": "created",
        "created_round_ids": [round_id for round_id, _ in created_rounds],
        "created_slots": [slot.isoformat() for _, slot in created_rounds],
        "remaining_missing_slots": [
            slot.isoformat() for slot in missing_slots if slot not in created_slot_set
        ],
    }


def _latest_submission(db, user_id: int, role: str) -> Submission | None:
    return (
        db.query(Submission)
        .filter(Submission.user_id == user_id, Submission.role == role)
        .order_by(Submission.uploaded_at.desc())
        .first()
    )


def _bp_snapshot(db, user_id: int) -> dict:
    row = db.query(BPPreference).filter(BPPreference.user_id == user_id).first()
    prefs = list(row.map_preferences) if row is not None and row.map_preferences else []
    return {"map_preferences": prefs}


def _build_test_run_summary(test_run: TestRun, matches: list[TestMatch], baselines_by_id: dict[int, Baseline]) -> dict:
    summary = {
        "test_run_id": test_run.id,
        "bundle_id": test_run.bundle_id,
        "status": test_run.status,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "attack_games": 0,
        "attack_wins": 0,
        "defense_games": 0,
        "defense_wins": 0,
        "completed_matches": 0,
        "failed_matches": 0,
        "pending_matches": 0,
        "baseline_results": [],
    }

    baseline_rows: dict[int, dict] = {}
    for row in matches:
        result = row.result_json or {}
        contestant_is_team_a = row.team_a_id == row.contestant_user_id
        contestant_role = (
            str(result.get("team_a_role", "attack")).lower()
            if contestant_is_team_a
            else str(result.get("team_b_role", "defense")).lower()
        )
        contestant_outcome = (
            str(result.get("team_a_outcome", row.status)).lower()
            if contestant_is_team_a
            else str(result.get("team_b_outcome", row.status)).lower()
        )

        bl_key = row.baseline_id or 0
        bl_name = (
            baselines_by_id[row.baseline_id].display_name
            if row.baseline_id and row.baseline_id in baselines_by_id
            else f"baseline-{row.baseline_id}"
        )
        baseline_entry = baseline_rows.setdefault(
            bl_key,
            {
                "baseline_id": row.baseline_id,
                "baseline_display_name": bl_name,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "matches": 0,
            },
        )

        if row.status == "completed":
            summary["completed_matches"] += 1
            baseline_entry["matches"] += 1
            if contestant_outcome == "win":
                summary["wins"] += 1
                baseline_entry["wins"] += 1
            elif contestant_outcome == "loss":
                summary["losses"] += 1
                baseline_entry["losses"] += 1
            else:
                summary["draws"] += 1
                baseline_entry["draws"] += 1

            if contestant_role == "attack":
                summary["attack_games"] += 1
                if contestant_outcome == "win":
                    summary["attack_wins"] += 1
            else:
                summary["defense_games"] += 1
                if contestant_outcome == "win":
                    summary["defense_wins"] += 1
        elif row.status == "failed":
            summary["failed_matches"] += 1
        else:
            summary["pending_matches"] += 1

    summary["attack_win_rate"] = (
        summary["attack_wins"] / summary["attack_games"]
        if summary["attack_games"]
        else 0.0
    )
    summary["defense_win_rate"] = (
        summary["defense_wins"] / summary["defense_games"]
        if summary["defense_games"]
        else 0.0
    )
    total_completed = summary["completed_matches"]
    summary["overall_win_rate"] = summary["wins"] / total_completed if total_completed else 0.0
    summary["baseline_results"] = list(baseline_rows.values())
    return summary


@celery_app.task(name="koh.tasks.schedule_test_run")
def schedule_test_run(user_id: int):
    with db_session() as db:
        site_cfg = get_or_create_site_config(db)
        if site_cfg.phase != "test":
            return {"ok": False, "error": "test evaluation is only available in test phase"}

        user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
        if user is None:
            return {"ok": False, "error": "user not found"}

        attack_submission = _latest_submission(db, user_id, "attack")
        defense_submission = _latest_submission(db, user_id, "defense")
        if attack_submission is None or defense_submission is None:
            return {"ok": False, "error": "both attack and defense submissions are required"}

        baselines = (
            db.query(Baseline)
            .filter(Baseline.is_active.is_(True))
            .order_by(Baseline.sort_order.asc(), Baseline.id.asc())
            .all()
        )
        active_templates = list_map_templates(db, active_only=True)
        if not baselines:
            return {"ok": False, "error": "no active baselines configured"}
        if not active_templates:
            return {"ok": False, "error": "no active maps"}

        baseline_payloads: list[tuple[Baseline, Submission, Submission]] = []
        for baseline in baselines:
            baseline_attack = db.query(Submission).filter(Submission.id == baseline.attack_submission_id).first()
            baseline_defense = db.query(Submission).filter(Submission.id == baseline.defense_submission_id).first()
            if baseline_attack is None or baseline_defense is None:
                continue
            baseline_payloads.append((baseline, baseline_attack, baseline_defense))
        if not baseline_payloads:
            return {"ok": False, "error": "no baseline pack with both roles found"}

        bp_snapshot = _bp_snapshot(db, user_id)
        last_bundle = (
            db.query(SubmissionBundle)
            .filter(SubmissionBundle.user_id == user_id)
            .order_by(SubmissionBundle.id.desc())
            .first()
        )
        if (
            last_bundle is not None
            and last_bundle.attack_submission_id == attack_submission.id
            and last_bundle.defense_submission_id == defense_submission.id
            and (last_bundle.bp_snapshot_json or {}) == bp_snapshot
        ):
            bundle = last_bundle
        else:
            bundle = SubmissionBundle(
                user_id=user_id,
                attack_submission_id=attack_submission.id,
                defense_submission_id=defense_submission.id,
                bp_snapshot_json=bp_snapshot,
                created_at=utc_now().replace(tzinfo=None),
            )
            db.add(bundle)
            db.flush()

        map_idx_pool = set(range(len(active_templates)))
        templates_by_idx = {idx: row for idx, row in enumerate(active_templates)}
        baseline_pack_version = (
            f"b:{','.join(str(row[0].id) for row in baseline_payloads)}"
            f"|m:{','.join(str(row.id) for row in active_templates)}"
        )[:128]

        test_run = TestRun(
            bundle_id=bundle.id,
            user_id=user_id,
            baseline_pack_version=baseline_pack_version,
            status="queued",
            summary_json={},
            queued_at=utc_now().replace(tzinfo=None),
        )
        db.add(test_run)
        db.flush()

        contestant_prefs = list(bp_snapshot.get("map_preferences", []))
        now = utc_now().replace(tzinfo=None)
        for baseline, baseline_attack, baseline_defense in baseline_payloads:
            baseline_prefs: list = []  # baselines are not users, no BP preferences
            selected_map_idx = _weighted_map_pick(map_idx_pool, contestant_prefs, baseline_prefs)
            template = templates_by_idx[selected_map_idx]
            layout_payload = RoundLayout(
                round_id=0,
                map_layout=MapLayout.from_dict(template.layout_json),
            ).to_dict()

            for game_no, team_a_role in enumerate(("attack", "defense"), start=1):
                if team_a_role == "attack":
                    attack_submission_id = bundle.attack_submission_id
                    defense_submission_id = baseline_defense.id
                else:
                    attack_submission_id = baseline_attack.id
                    defense_submission_id = bundle.defense_submission_id

                db.add(
                    TestMatch(
                        test_run_id=test_run.id,
                        contestant_user_id=user_id,
                        baseline_id=baseline.id,
                        attack_submission_id=attack_submission_id,
                        defense_submission_id=defense_submission_id,
                        map_template_id=template.id,
                        map_idx=selected_map_idx,
                        map_name=template.name,
                        layout_json=layout_payload,
                        team_a_id=user_id,
                        team_b_id=None,
                        status="queued",
                        result_json={
                            "team_a_role": team_a_role,
                            "team_b_role": "defense" if team_a_role == "attack" else "attack",
                            "game_no": game_no,
                            "map_name": template.name,
                        },
                        replay_path=None,
                        created_at=now,
                        started_at=None,
                        finished_at=None,
                    )
                )

        db.commit()
        db.refresh(test_run)
        test_matches = (
            db.query(TestMatch)
            .filter(TestMatch.test_run_id == test_run.id)
            .order_by(TestMatch.id.asc())
            .all()
        )

    scheduled = group(
        celery_app.signature("koh.tasks.run_test_match", args=[row.id])
        for row in test_matches
    )
    scheduled.apply_async()
    celery_app.send_task("koh.tasks.watch_test_run", args=[test_run.id], countdown=5)
    _publish_test_run_event(
        test_run.id,
        "test_run_queued",
        {"test_run_id": test_run.id, "scheduled_matches": len(test_matches)},
    )
    return {
        "ok": True,
        "bundle_id": test_run.bundle_id,
        "test_run_id": test_run.id,
        "scheduled_matches": len(test_matches),
    }


@celery_app.task(name="koh.tasks.run_test_match")
def run_test_match(test_match_id: int):
    with db_session() as db:
        row = db.query(TestMatch).filter(TestMatch.id == test_match_id).first()
        if row is None:
            return {"ok": False, "error": "test match not found"}

        seed_result = dict(row.result_json or {})
        team_a_role = str(seed_result.get("team_a_role", "attack")).lower()
        if team_a_role == "attack":
            team_a_policy = _load_policy_from_submission(row.attack_submission_id)
            team_b_policy = _load_policy_from_submission(row.defense_submission_id)
        else:
            team_a_policy = _load_policy_from_submission(row.defense_submission_id)
            team_b_policy = _load_policy_from_submission(row.attack_submission_id)

        row.status = "running"
        row.started_at = utc_now().replace(tzinfo=None)
        test_run = db.query(TestRun).filter(TestRun.id == row.test_run_id).first()
        if test_run is not None and test_run.started_at is None:
            test_run.started_at = row.started_at
            test_run.status = "running"
        db.commit()
        _publish_test_run_event(
            row.test_run_id,
            "test_match_status_changed",
            {"test_match_id": row.id, "status": "running"},
        )

        try:
            normalized_result, replay_data = _run_battle(
                layout_payload=row.layout_json or {},
                team_a_role_seed=team_a_role,
                team_a_policy=team_a_policy,
                team_b_policy=team_b_policy,
            )
            replay_dir = _data_dir() / "test_replays"
            replay_dir.mkdir(parents=True, exist_ok=True)
            replay_path = replay_dir / f"test_match_{row.id}.json"
            if replay_data is not None:
                replay_path.write_text(
                    json.dumps(replay_data, ensure_ascii=True, separators=(",", ":")),
                    encoding="utf-8",
                )
            winner_ref = normalized_result.pop("winner_ref", None)
            winner_user_id = (
                row.team_a_id if winner_ref == "team_a"
                else row.team_b_id if (winner_ref == "team_b" and row.team_b_id is not None)
                else None
            )
            row.status = "completed"
            row.finished_at = utc_now().replace(tzinfo=None)
            row.replay_path = str(replay_path)
            row.result_json = {
                **seed_result,
                **normalized_result,
                "winner_user_id": winner_user_id,
                "test_run_id": row.test_run_id,
            }
            db.commit()
            _publish_test_run_event(
                row.test_run_id,
                "test_match_status_changed",
                {"test_match_id": row.id, "status": "completed", "winner_user_id": winner_user_id},
            )
            return {"ok": True, "test_match_id": row.id, "status": "completed"}
        except Exception as error:
            row.status = "failed"
            row.finished_at = utc_now().replace(tzinfo=None)
            row.result_json = {**seed_result, "error": str(error)}
            db.commit()
            _publish_test_run_event(
                row.test_run_id,
                "test_match_status_changed",
                {"test_match_id": row.id, "status": "failed", "error": str(error)},
            )
            return {"ok": False, "test_match_id": row.id, "status": "failed", "error": str(error)}


@celery_app.task(name="koh.tasks.finalize_test_run")
def finalize_test_run(test_run_id: int):
    with db_session() as db:
        test_run = db.query(TestRun).filter(TestRun.id == test_run_id).first()
        if test_run is None:
            return {"ok": False, "error": "test run not found"}

        pending = (
            db.query(TestMatch)
            .filter(TestMatch.test_run_id == test_run_id, TestMatch.status.in_(["queued", "running"]))
            .count()
        )
        if pending > 0:
            return {"ok": False, "error": "test run still pending", "pending_matches": pending}

        matches = (
            db.query(TestMatch)
            .filter(TestMatch.test_run_id == test_run_id)
            .order_by(TestMatch.id.asc())
            .all()
        )
        baseline_ids = {row.baseline_id for row in matches if row.baseline_id is not None}
        baselines = db.query(Baseline).filter(Baseline.id.in_(list(baseline_ids))).all() if baseline_ids else []
        baselines_by_id = {b.id: b for b in baselines}

        failed = sum(1 for row in matches if row.status == "failed")
        test_run.status = "failed" if failed > 0 else "completed"
        test_run.finished_at = utc_now().replace(tzinfo=None)
        test_run.summary_json = _build_test_run_summary(test_run, matches, baselines_by_id)
        test_run.summary_json["status"] = test_run.status
        db.commit()
        _publish_test_run_event(
            test_run_id,
            "test_run_status_changed",
            {
                "test_run_id": test_run_id,
                "status": test_run.status,
                "completed_matches": test_run.summary_json.get("completed_matches", 0),
                "failed_matches": failed,
            },
        )
        return {"ok": True, "test_run_id": test_run_id, "status": test_run.status}


@celery_app.task(name="koh.tasks.watch_test_run", bind=True, max_retries=240)
def watch_test_run(self, test_run_id: int):
    with db_session() as db:
        test_run = db.query(TestRun).filter(TestRun.id == test_run_id).first()
        if test_run is None:
            return {"ok": False, "error": "test run not found"}
        if test_run.status in {"completed", "failed"}:
            return {"ok": True, "status": test_run.status}
        pending = (
            db.query(TestMatch)
            .filter(TestMatch.test_run_id == test_run_id, TestMatch.status.in_(["queued", "running"]))
            .count()
        )
    if pending > 0:
        raise self.retry(countdown=15)
    finalize_test_run.delay(test_run_id)
    return {"ok": True, "test_run_id": test_run_id, "triggered": "finalize_test_run"}


@celery_app.task(name="koh.tasks.auto_round_reconcile")
def auto_round_reconcile():
    now = utc_now().replace(tzinfo=None)
    triggered = {"watch_finalize": 0, "finalize": 0}

    with db_session() as db:
        config = get_or_create_auto_round_config(db)
        if not config.enabled:
            return {"ok": True, "status": "disabled", "triggered": triggered}

        running_rounds = (
            db.query(Round)
            .filter(Round.status == "running", Round.created_mode != "test")
            .order_by(Round.id.desc())
            .limit(20)
            .all()
        )

        round_ids_to_watch: list[int] = []
        round_ids_to_finalize: list[int] = []

        for row in running_rounds:
            pending = (
                db.query(Match)
                .filter(Match.round_id == row.id, Match.status.in_(["queued", "running"]))
                .count()
            )
            failed = (
                db.query(Match)
                .filter(Match.round_id == row.id, Match.status == "failed")
                .count()
            )

            if pending == 0 and failed == 0:
                round_ids_to_finalize.append(row.id)
            elif (now - row.created_at).total_seconds() > 120:
                round_ids_to_watch.append(row.id)

    for round_id in round_ids_to_watch:
        celery_app.send_task("koh.tasks.watch_and_finalize", args=[round_id])
        triggered["watch_finalize"] += 1

    for round_id in round_ids_to_finalize:
        celery_app.send_task("koh.tasks.finalize_round", args=[round_id])
        triggered["finalize"] += 1

    return {"ok": True, "status": "reconciled", "triggered": triggered}
