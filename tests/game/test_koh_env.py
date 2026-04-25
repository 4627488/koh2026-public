import numpy as np

from koh.game.koh_env import (
    ACTION_COUNT,
    ACTION_DOWN,
    ACTION_FIRE_DOWN,
    ACTION_FIRE_LEFT,
    ACTION_FIRE_RIGHT,
    ACTION_FIRE_UP,
    ACTION_LEFT,
    ACTION_RIGHT,
    ACTION_STAY,
    ACTION_UP,
    BOMB_TIMER,
    DEFUSE_STEPS,
    FIRE_COOLDOWN_STEPS,
    GRID_SIZE,
    KOHBattleEnv,
    LOS_RANGE,
    MAX_STEPS,
    OBSERVATION_DIM,
    PLAYER_OBS_DIM,
    PLANT_STEPS,
    TEAM_ACTION_COUNT,
    DEFAULT_MAP,
    make_round_layout,
)


def _step(env, t1=ACTION_STAY, t2=ACTION_STAY, ct1=ACTION_STAY, ct2=ACTION_STAY):
    return env.step(t1, t2, ct1, ct2)


def _env(seed: int) -> KOHBattleEnv:
    return KOHBattleEnv(make_round_layout(seed, DEFAULT_MAP))


def test_constants():
    assert GRID_SIZE == 25
    assert MAX_STEPS == 200
    assert PLAYER_OBS_DIM == 36
    assert OBSERVATION_DIM == 77
    assert ACTION_COUNT == 9
    assert TEAM_ACTION_COUNT == 18
    assert PLANT_STEPS == 3
    assert DEFUSE_STEPS == 3
    assert BOMB_TIMER == 30


def test_observation_shape():
    env = _env(1)
    atk = env.get_observation("attack")
    dfn = env.get_observation("defense")
    assert atk.shape == (77,)
    assert dfn.shape == (77,)
    assert atk.dtype == np.float32


def test_global_observation_exposes_site_progress_before_plant():
    env = _env(14)
    site = env.map.bomb_site_a
    env.t1_pos = site

    _step(env, t1=ACTION_STAY)
    obs = env.get_observation("attack")

    assert obs[72] == np.float32(1.0 / PLANT_STEPS)
    assert obs[73] == 0.0


def test_global_observation_exposes_planted_site_identity():
    env = _env(15)
    site = env.map.bomb_site_b
    env.t1_pos = site

    _step(env, t1=ACTION_STAY)
    _step(env, t1=ACTION_STAY)
    _step(env, t1=ACTION_STAY)
    obs = env.get_observation("attack")

    assert env.bomb_planted
    assert obs[72] == 0.0
    assert obs[73] == 1.0


def test_dead_player_block_is_zero():
    env = _env(2)
    env.t1_alive = False
    obs = env.get_observation("attack")
    assert np.allclose(obs[0:PLAYER_OBS_DIM], 0.0)


def test_visibility_blocked_by_wall():
    env = _env(3)
    env.t1_pos = (10, 9)
    env.ct1_pos = (10, 11)
    env.map = env.layout.map_layout
    env._obstacle_set = frozenset(set(env._obstacle_set) | {(10, 10)})
    obs = env.get_observation("attack")
    assert obs[10] == 0.0
    assert obs[11] == 0.0
    assert obs[12] == 0.0


def test_visibility_grazing_obstacle_corner_is_blocked():
    env = _env(31)
    env.t1_pos = (0, 0)
    env.ct1_pos = (2, 2)
    env._obstacle_set = frozenset({(0, 1)})
    obs = env.get_observation("attack")
    assert obs[10] == 0.0
    assert obs[11] == 0.0
    assert obs[12] == 0.0


def test_visibility_out_of_range():
    env = _env(4)
    env.t1_pos = (0, 0)
    env.ct1_pos = (0, LOS_RANGE + 1)
    obs = env.get_observation("attack")
    assert obs[12] == 0.0


def test_fire_kills_in_line():
    env = _env(5)
    env.t1_pos = (10, 10)
    env.ct1_pos = (10, 13)
    _step(env, t1=ACTION_FIRE_RIGHT)
    assert not env.ct1_alive


def test_fire_trade_possible():
    env = _env(6)
    env.t1_pos = (2, 2)
    env.ct1_pos = (2, 4)
    _step(env, t1=ACTION_FIRE_RIGHT, ct1=ACTION_FIRE_LEFT)
    assert not env.t1_alive
    assert not env.ct1_alive


def test_fire_cooldown_two_steps():
    env = _env(7)
    env.t1_pos = (10, 10)
    env.ct1_pos = (10, 14)

    _step(env, t1=ACTION_FIRE_RIGHT)
    first_cd = env.t1_cooldown
    assert first_cd > 0

    _step(env, t1=ACTION_FIRE_RIGHT)
    assert env.t1_cooldown > 0

    _step(env, t1=ACTION_FIRE_RIGHT)
    assert env.t1_cooldown >= 0


def test_move_blocked_by_alive_occupancy():
    env = _env(8)
    env.t1_pos = (10, 10)
    env.t2_pos = (10, 11)
    _step(env, t1=ACTION_RIGHT)
    assert env.t1_pos == (10, 10)


def test_plant_requires_continuous_stationary_presence():
    env = _env(9)
    site = env.map.bomb_site_a
    env.t1_pos = site

    _step(env, t1=ACTION_STAY)
    assert env.plant_progress == 1

    _step(env, t1=ACTION_UP)
    assert env.plant_progress == 0

    env.t1_pos = site
    _step(env, t1=ACTION_STAY)
    assert env.plant_progress == 1

    _step(env, t1=ACTION_STAY)
    _step(env, t1=ACTION_STAY)
    assert env.bomb_planted
    assert env.bomb_site_planted == site


def test_two_attackers_same_site_do_not_stack_plant_progress():
    env = _env(91)
    site = env.map.bomb_site_a
    env.t1_pos = site
    env.t2_pos = site

    _step(env, t1=ACTION_STAY, t2=ACTION_STAY)
    assert env.plant_progress == 1

    _step(env, t1=ACTION_STAY, t2=ACTION_STAY)
    assert env.plant_progress == 2

    _step(env, t1=ACTION_STAY, t2=ACTION_STAY)
    assert env.bomb_planted


def test_defuse_requires_continuous_stationary_presence():
    env = _env(10)
    site = env.map.bomb_site_a
    env.t1_pos = site
    _step(env)
    _step(env)
    _step(env)
    assert env.bomb_planted

    env.ct1_pos = site
    _step(env)
    _step(env, ct1=ACTION_UP)
    assert env.defuse_progress == 0

    env.ct1_pos = site
    _step(env)
    _step(env)
    _step(env)
    assert env.defuse_progress >= DEFUSE_STEPS


def test_bomb_explosion_priority_over_defuse():
    env = _env(11)
    site = env.map.bomb_site_a
    env.t1_pos = site
    _step(env)
    _step(env)
    _step(env)
    assert env.bomb_planted

    env.bomb_timer = 1
    env.ct1_pos = site
    env.defuse_progress = DEFUSE_STEPS - 1
    _, done, result = _step(env)
    assert done
    assert result["winner"] == "attacker"
    assert result["reason"] == "bomb_exploded"


def test_timeout_without_bomb_is_defender_win():
    env = _env(12)
    env.step_count = MAX_STEPS - 1
    _, done, result = _step(env)
    assert done
    assert result["winner"] == "defender"
    assert result["reason"] == "timeout"


def test_ascii_render_has_grid_shape():
    env = _env(13)
    board = env.render_ascii().split("\n")
    assert len(board) == GRID_SIZE
    assert all(len(line.split()) == GRID_SIZE for line in board)
