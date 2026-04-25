from __future__ import annotations

from collections import Counter
from typing import Iterable

BASE_WIN = 1.0
BASE_DRAW = 0.4
BASE_LOSS = 0.0

BP_BREADTH_FLOOR = 0.85
BP_BREADTH_CEILING = 1.15
ACTIVE_CHALLENGE_FLOOR = 0.70
ACTIVE_CHALLENGE_CEILING = 1.00
MAP_FACTOR_CAP = 1.50
ROUND_SCORE_CAP = 10.0
ROUND_HISTORY_WINDOW = 8
HIGH_REWARD_THRESHOLD = 1.25
MAX_SINGLE_GAME_SCORE = (
    BASE_WIN * MAP_FACTOR_CAP * BP_BREADTH_CEILING * ACTIVE_CHALLENGE_CEILING
)


def sanitize_bp_preferences(
    map_preferences: list[int] | None,
    valid_map_indices: Iterable[int],
) -> list[int]:
    valid = set(valid_map_indices)
    seen: set[int] = set()
    sanitized: list[int] = []
    for map_idx in map_preferences or []:
        if map_idx in valid and map_idx not in seen:
            seen.add(map_idx)
            sanitized.append(map_idx)
    return sanitized


def bp_breadth_factor(covered_maps: int, total_maps: int) -> float:
    if total_maps <= 0 or covered_maps <= 0:
        return BP_BREADTH_FLOOR
    coverage = min(covered_maps, total_maps) / total_maps
    return BP_BREADTH_FLOOR + 0.30 * (coverage ** 0.5)


def active_challenge_factor(
    ranked_map_preferences: list[int],
    map_idx: int,
    total_maps: int,
) -> float:
    if total_maps <= 1:
        return ACTIVE_CHALLENGE_CEILING if map_idx in ranked_map_preferences else ACTIVE_CHALLENGE_FLOOR
    try:
        rank = ranked_map_preferences.index(map_idx) + 1
    except ValueError:
        return ACTIVE_CHALLENGE_FLOOR
    return ACTIVE_CHALLENGE_CEILING - 0.30 * ((rank - 1) / (total_maps - 1))


def base_score_for_outcome(outcome: str) -> float:
    normalized = str(outcome or "").lower()
    if normalized == "win":
        return BASE_WIN
    if normalized == "draw":
        return BASE_DRAW
    return BASE_LOSS


def map_reward_factor(coldness: float, difficulty: float) -> float:
    factor = 1.0 + 0.25 * max(0.0, min(1.0, coldness)) + 0.25 * max(0.0, min(1.0, difficulty))
    return min(MAP_FACTOR_CAP, factor)


def compute_coldness_by_key(
    current_map_keys: list[str],
    recent_round_map_keys: list[str],
) -> dict[str, float]:
    if not current_map_keys:
        return {}
    counts = Counter(key for key in recent_round_map_keys if key in set(current_map_keys))
    total = sum(counts.values())
    if total <= 0:
        return {key: 0.5 for key in current_map_keys}

    sorted_keys = sorted(
        current_map_keys,
        key=lambda key: (counts.get(key, 0) / total, key),
    )
    if len(sorted_keys) == 1:
        return {sorted_keys[0]: 0.5}

    coldness: dict[str, float] = {}
    denom = len(sorted_keys) - 1
    for idx, key in enumerate(sorted_keys):
        coldness[key] = 1.0 - (idx / denom)
    return coldness


def normalize_round_score(raw_score: float, participant_count: int) -> float:
    if participant_count < 2:
        return 0.0
    raw_max = 2 * (participant_count - 1) * MAX_SINGLE_GAME_SCORE
    if raw_max <= 0:
        return 0.0
    return ROUND_SCORE_CAP * raw_score / raw_max


def infer_outcomes(
    result_json: dict,
    *,
    fallback_failed_to_draw: bool = False,
) -> tuple[str, str]:
    team_a_outcome = str(result_json.get("team_a_outcome", "")).lower()
    team_b_outcome = str(result_json.get("team_b_outcome", "")).lower()
    valid = {"win", "loss", "draw"}
    if team_a_outcome in valid and team_b_outcome in valid:
        return team_a_outcome, team_b_outcome

    winner = str(result_json.get("winner", "draw")).lower()
    team_a_role = str(result_json.get("team_a_role", "attack")).lower()
    if winner == "attacker":
        team_a_outcome = "win" if team_a_role == "attack" else "loss"
    elif winner == "defender":
        team_a_outcome = "win" if team_a_role == "defense" else "loss"
    elif fallback_failed_to_draw:
        team_a_outcome = "draw"
    else:
        team_a_outcome = "draw"

    if team_a_outcome == "win":
        team_b_outcome = "loss"
    elif team_a_outcome == "loss":
        team_b_outcome = "win"
    else:
        team_b_outcome = "draw"
    return team_a_outcome, team_b_outcome


def round_delta_class(delta: float) -> str:
    if delta > 0.05:
        return "up"
    if delta < -0.05:
        return "down"
    return "flat"
