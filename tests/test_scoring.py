from koh.scoring import (
    active_challenge_factor,
    bp_breadth_factor,
    compute_coldness_by_key,
    map_reward_factor,
    normalize_round_score,
    sanitize_bp_preferences,
)


def test_sanitize_bp_preferences_keeps_unique_valid_order():
    assert sanitize_bp_preferences([3, 2, 3, 9, 1], [1, 2, 3]) == [3, 2, 1]


def test_bp_breadth_factor_hits_floor_and_ceiling():
    assert bp_breadth_factor(0, 5) == 0.85
    assert bp_breadth_factor(5, 5) == 1.15


def test_active_challenge_factor_respects_rank_and_floor():
    ranked = [4, 1, 3, 2]
    assert active_challenge_factor(ranked, 4, 4) == 1.0
    assert active_challenge_factor(ranked, 2, 4) == 0.70
    assert active_challenge_factor(ranked, 9, 4) == 0.70


def test_compute_coldness_by_key_orders_by_recent_pick_frequency():
    coldness = compute_coldness_by_key(
        ["a", "b", "c"],
        ["a", "a", "b"],
    )
    assert coldness["c"] == 1.0
    assert coldness["b"] == 0.5
    assert coldness["a"] == 0.0


def test_map_reward_factor_and_round_normalization_are_bounded():
    assert map_reward_factor(1.0, 1.0) == 1.5
    assert round(normalize_round_score(0.0, 5), 6) == 0.0
    assert round(normalize_round_score(13.8, 5), 6) == 10.0
