"""
Asuri Major Baseline Template - teaching-oriented DQN baseline for 2v2 team control.

Recommended setup:
  1. Download `koh_env.py` and `koh_baseline_template.py`.
  2. Download one or more map `.txt` files from the map detail page.
  3. Train with a map pool:
     python koh_baseline_template.py --role attack --maps-dir maps --episodes 3000 --output attack.safetensors
     python koh_baseline_template.py --role defense --maps-dir maps --episodes 3000 --output defense.safetensors
"""

from __future__ import annotations

import argparse
import random
from collections import deque
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from safetensors.torch import save_file as safetensors_save

from koh_env import (
    ACTION_COUNT,
    ACTION_DELTAS,
    ACTION_DOWN,
    ACTION_FIRE_DOWN,
    ACTION_FIRE_LEFT,
    ACTION_FIRE_RIGHT,
    ACTION_FIRE_UP,
    ACTION_LEFT,
    ACTION_RIGHT,
    ACTION_STAY,
    ACTION_UP,
    FIRE_ACTIONS,
    FIRE_RANGE,
    GRID_SIZE,
    MOVE_ACTIONS,
    OBSERVATION_DIM,
    PLAYER_OBS_DIM,
    TEAM_ACTION_COUNT,
    KOHBattleEnv,
    MapLayout,
    make_round_layout,
)


ROLE = Literal["attack", "defense"]

# ---------------------------------------------------------------------------
# Scripted baseline opponents
# These rule-based policies are provided as training opponents.
# They are NOT used by the online server — online matches always run two
# submitted .safetensors models against each other.
# ---------------------------------------------------------------------------

def _action_allowed(obs: np.ndarray, offset: int, action: int) -> bool:
    return bool(obs[offset + 25 + action] > 0.5)


def _fire_action_for_delta(obs: np.ndarray, offset: int, dr: float, dc: float) -> Optional[int]:
    row_delta = dr * float(GRID_SIZE - 1)
    col_delta = dc * float(GRID_SIZE - 1)
    eps = 1e-6
    if abs(col_delta) < eps and 0 < abs(row_delta) <= FIRE_RANGE:
        action = ACTION_FIRE_DOWN if row_delta > 0 else ACTION_FIRE_UP
        return action if _action_allowed(obs, offset, action) else None
    if abs(row_delta) < eps and 0 < abs(col_delta) <= FIRE_RANGE:
        action = ACTION_FIRE_RIGHT if col_delta > 0 else ACTION_FIRE_LEFT
        return action if _action_allowed(obs, offset, action) else None
    return None


def _choose_visible_fire(obs: np.ndarray, offset: int) -> Optional[int]:
    candidates: list[tuple[float, int]] = []
    for dr_idx, dc_idx, visible_idx in ((10, 11, 12), (13, 14, 15)):
        if obs[offset + visible_idx] <= 0.5:
            continue
        dr = float(obs[offset + dr_idx])
        dc = float(obs[offset + dc_idx])
        action = _fire_action_for_delta(obs, offset, dr, dc)
        if action is not None:
            candidates.append((abs(dr) + abs(dc), action))
    if not candidates:
        return None
    return min(candidates, key=lambda x: x[0])[1]


def _site_delta(obs: np.ndarray, offset: int, player: int) -> tuple[float, float]:
    if player == 0:
        return float(obs[offset + 3]), float(obs[offset + 4])
    return float(obs[offset + 5]), float(obs[offset + 6])


def _move_towards_delta(obs: np.ndarray, offset: int, dr: float, dc: float) -> int:
    if abs(dr) < 1e-6 and abs(dc) < 1e-6:
        return ACTION_STAY
    candidates: list[tuple[float, int]] = []
    for action in (ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT):
        if not _action_allowed(obs, offset, action):
            continue
        move_dr, move_dc = ACTION_DELTAS[action]
        next_dr = dr - (move_dr / float(GRID_SIZE - 1))
        next_dc = dc - (move_dc / float(GRID_SIZE - 1))
        candidates.append((abs(next_dr) + abs(next_dc), action))
    if not candidates:
        return ACTION_STAY
    return min(candidates, key=lambda x: x[0])[1]


def _scripted_player_action(obs: np.ndarray, player: int) -> int:
    offset = player * PLAYER_OBS_DIM
    if obs[offset] < 0.5:
        return ACTION_STAY
    fire = _choose_visible_fire(obs, offset)
    if fire is not None:
        return fire
    dr, dc = _site_delta(obs, offset, player)
    return _move_towards_delta(obs, offset, dr, dc)


class ScriptedAttackPolicy:
    """Rule-based attacker: rush bomb sites, fire on sight."""

    def choose_action(self, observation: np.ndarray) -> tuple[int, int]:
        return (
            _scripted_player_action(observation, 0),
            _scripted_player_action(observation, 1),
        )


class ScriptedDefensePolicy:
    """Rule-based defender: guard bomb sites, fire on sight."""

    def choose_action(self, observation: np.ndarray) -> tuple[int, int]:
        return (
            _scripted_player_action(observation, 0),
            _scripted_player_action(observation, 1),
        )
ASCII_MAP_CHARS = {".", "#", "A", "B", "T", "C"}

# Reward design stays teaching-oriented on purpose:
# keep the signals compact and readable, but make them phase-aware so the
# baseline better matches the current two-site plant / post-plant game flow.
STEP_PENALTY = -0.05
KILL_REWARD = 5.0
DEATH_PENALTY = -4.0
DISCOVERY_REWARD = 0.25
ATTACK_PROGRESS_REWARD = 1.5
DEFENSE_DENIAL_REWARD = 1.0
PROGRESS_LOSS_PENALTY = -0.75
POST_PLANT_TICK_REWARD = 0.15
POST_PLANT_TICK_PENALTY = -0.15
DEFUSE_PROGRESS_REWARD = 2.5
DEFUSE_THREAT_PENALTY = -2.0
PLANT_SUCCESS_REWARD = 3.0
DEFUSE_SUCCESS_REWARD = 3.0
WIN_REWARD = 100.0
LOSS_REWARD = -100.0


def normalize_map_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def parse_ascii_map(text: str, *, name: str) -> MapLayout:
    normalized = normalize_map_text(text)
    lines = normalized.splitlines()
    if len(lines) != GRID_SIZE:
        raise ValueError(f"{name}: expected {GRID_SIZE} rows, got {len(lines)}")

    obstacles: list[tuple[int, int]] = []
    t_spawns: list[tuple[int, int]] = []
    ct_spawns: list[tuple[int, int]] = []
    bomb_site_a: list[tuple[int, int]] = []
    bomb_site_b: list[tuple[int, int]] = []

    for row_idx, line in enumerate(lines):
        if len(line) != GRID_SIZE:
            raise ValueError(
                f"{name}: row {row_idx + 1} must have {GRID_SIZE} columns, got {len(line)}"
            )
        for col_idx, cell in enumerate(line):
            if cell not in ASCII_MAP_CHARS:
                raise ValueError(
                    f"{name}: invalid cell '{cell}' at row {row_idx + 1}, col {col_idx + 1}"
                )
            pos = (row_idx, col_idx)
            if cell == "#":
                obstacles.append(pos)
            elif cell == "T":
                t_spawns.append(pos)
            elif cell == "C":
                ct_spawns.append(pos)
            elif cell == "A":
                bomb_site_a.append(pos)
            elif cell == "B":
                bomb_site_b.append(pos)

    if len(t_spawns) != 2:
        raise ValueError(f"{name}: expected 2 T spawns, got {len(t_spawns)}")
    if len(ct_spawns) != 2:
        raise ValueError(f"{name}: expected 2 CT spawns, got {len(ct_spawns)}")
    if len(bomb_site_a) != 1:
        raise ValueError(f"{name}: expected 1 bomb site A, got {len(bomb_site_a)}")
    if len(bomb_site_b) != 1:
        raise ValueError(f"{name}: expected 1 bomb site B, got {len(bomb_site_b)}")

    return MapLayout(
        name=name,
        grid_size=GRID_SIZE,
        t_spawns=(t_spawns[0], t_spawns[1]),
        ct_spawns=(ct_spawns[0], ct_spawns[1]),
        bomb_site_a=bomb_site_a[0],
        bomb_site_b=bomb_site_b[0],
        obstacles=tuple(sorted(obstacles)),
    )


def load_map_pool(map_file: str | None, maps_dir: str | None) -> list[MapLayout]:
    paths: list[Path] = []
    if map_file:
        paths.append(Path(map_file))
    if maps_dir:
        paths.extend(sorted(Path(maps_dir).glob("*.txt")))

    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(path)

    if not unique_paths:
        raise ValueError(
            "no maps loaded; pass --maps-dir maps or --map path/to/<name>.txt"
        )

    layouts: list[MapLayout] = []
    for path in unique_paths:
        if not path.exists():
            raise FileNotFoundError(f"map file not found: {path}")
        layouts.append(parse_ascii_map(path.read_text(encoding="utf-8"), name=path.stem))
    return layouts


class KOHTeamEnv:
    """Wraps the full environment as a single-team learning problem."""

    def __init__(
        self,
        role: ROLE,
        seed: Optional[int] = None,
        map_pool: Optional[list[MapLayout]] = None,
    ):
        if role not in ("attack", "defense"):
            raise ValueError("role must be 'attack' or 'defense'")
        self.role: ROLE = role
        self.rng = np.random.default_rng(seed)
        self.enemy_policy = (
            ScriptedDefensePolicy() if role == "attack" else ScriptedAttackPolicy()
        )
        self.map_pool = list(map_pool or [])
        if not self.map_pool:
            raise ValueError("KOHTeamEnv requires a non-empty map_pool")
        self.env = KOHBattleEnv(make_round_layout(0, self.map_pool[0]))

    def reset(self) -> np.ndarray:
        round_id = int(self.rng.integers(0, 2**31 - 1))
        map_layout = self.map_pool[int(self.rng.integers(0, len(self.map_pool)))]
        layout = make_round_layout(round_id, map_layout)
        self.env = KOHBattleEnv(layout, round_id=round_id)
        self.env.reset()
        return self.env.get_observation(self.role)

    def step(self, a1: int, a2: int) -> tuple[np.ndarray, float, bool, dict]:
        prev_obs = self.env.get_observation(self.role)
        prev_enemy_alive = self._enemy_alive_count()
        prev_own_alive = self._own_alive_count()
        prev_site_progress = self._plant_progress_total()
        prev_site_a_progress, prev_site_b_progress = self._plant_site_progress()
        prev_defuse = float(self.env.defuse_progress)
        prev_bomb_planted = bool(self.env.bomb_planted)
        prev_bomb_timer = float(self.env.bomb_timer)

        enemy_role: ROLE = "defense" if self.role == "attack" else "attack"
        enemy_obs = self.env.get_observation(enemy_role)
        enemy_a1, enemy_a2 = self.enemy_policy.choose_action(enemy_obs)

        if self.role == "attack":
            _, done, result = self.env.step(a1, a2, enemy_a1, enemy_a2)
        else:
            _, done, result = self.env.step(enemy_a1, enemy_a2, a1, a2)

        obs = self.env.get_observation(self.role)
        reward = self._reward(
            prev_obs=prev_obs,
            obs=obs,
            done=done,
            result=result,
            prev_enemy_alive=prev_enemy_alive,
            prev_own_alive=prev_own_alive,
            prev_site_progress=prev_site_progress,
            prev_site_a_progress=prev_site_a_progress,
            prev_site_b_progress=prev_site_b_progress,
            prev_defuse=prev_defuse,
            prev_bomb_planted=prev_bomb_planted,
            prev_bomb_timer=prev_bomb_timer,
        )
        return obs, reward, done, result

    def _own_alive_count(self) -> int:
        if self.role == "attack":
            return int(self.env.t1_alive) + int(self.env.t2_alive)
        return int(self.env.ct1_alive) + int(self.env.ct2_alive)

    def _enemy_alive_count(self) -> int:
        if self.role == "attack":
            return int(self.env.ct1_alive) + int(self.env.ct2_alive)
        return int(self.env.t1_alive) + int(self.env.t2_alive)

    def _plant_progress_total(self) -> float:
        return float(self.env._plant_progress_a + self.env._plant_progress_b)

    def _plant_site_progress(self) -> tuple[float, float]:
        return float(self.env._plant_progress_a), float(self.env._plant_progress_b)

    @staticmethod
    def _visible_enemy_count(obs: np.ndarray) -> int:
        total = 0
        for player_idx in range(2):
            base = player_idx * PLAYER_OBS_DIM
            total += int(obs[base + 12] > 0.5)
            total += int(obs[base + 15] > 0.5)
        return total

    def _reward(
        self,
        prev_obs: np.ndarray,
        obs: np.ndarray,
        done: bool,
        result: dict,
        prev_enemy_alive: int,
        prev_own_alive: int,
        prev_site_progress: float,
        prev_site_a_progress: float,
        prev_site_b_progress: float,
        prev_defuse: float,
        prev_bomb_planted: bool,
        prev_bomb_timer: float,
    ) -> float:
        reward = STEP_PENALTY

        enemy_kills = prev_enemy_alive - self._enemy_alive_count()
        own_losses = prev_own_alive - self._own_alive_count()
        reward += KILL_REWARD * float(enemy_kills)
        reward += DEATH_PENALTY * float(own_losses)

        newly_visible = self._visible_enemy_count(obs) - self._visible_enemy_count(
            prev_obs
        )
        if newly_visible > 0:
            reward += DISCOVERY_REWARD * float(newly_visible)

        # Phase-aware shaping: before plant reward progress / denial, after plant
        # reward holding the timer or forcing defuse progress.
        current_site_progress = self._plant_progress_total()
        site_progress_gain = max(0.0, current_site_progress - prev_site_progress)
        site_progress_loss = max(0.0, prev_site_progress - current_site_progress)
        current_site_a_progress, current_site_b_progress = self._plant_site_progress()
        newly_contested_sites = int(
            prev_site_a_progress <= 0.0 < current_site_a_progress
        ) + int(prev_site_b_progress <= 0.0 < current_site_b_progress)
        defuse_gain = max(0.0, float(self.env.defuse_progress) - prev_defuse)
        timer_delta = max(0.0, prev_bomb_timer - float(self.env.bomb_timer))

        if self.role == "attack":
            reward += ATTACK_PROGRESS_REWARD * site_progress_gain
            reward += 0.25 * float(newly_contested_sites)
            reward += PROGRESS_LOSS_PENALTY * site_progress_loss
            if self.env.bomb_planted and not prev_bomb_planted:
                reward += PLANT_SUCCESS_REWARD
            elif prev_bomb_planted and self.env.bomb_planted:
                reward += POST_PLANT_TICK_REWARD * timer_delta
            reward += DEFUSE_THREAT_PENALTY * defuse_gain
        else:
            if not prev_bomb_planted and not self.env.bomb_planted:
                reward += DEFENSE_DENIAL_REWARD * site_progress_loss
            reward += DEFUSE_PROGRESS_REWARD * defuse_gain
            if prev_bomb_planted and self.env.bomb_planted:
                reward += POST_PLANT_TICK_PENALTY * timer_delta
            if done and result.get("winner") == "defender" and prev_bomb_planted:
                reward += DEFUSE_SUCCESS_REWARD

        if done:
            winner = result.get("winner")
            if (self.role == "attack" and winner == "attacker") or (
                self.role == "defense" and winner == "defender"
            ):
                reward += WIN_REWARD
            else:
                reward += LOSS_REWARD

        return reward


class DQN(nn.Module):
    """
    Fixed submission architecture required by the platform.

    Output layout:
    - logits[0:9]   for player 1
    - logits[9:18]  for player 2
    """

    def __init__(
        self, input_dim: int = OBSERVATION_DIM, output_dim: int = TEAM_ACTION_COUNT
    ):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, output_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class ReplayBuffer:
    def __init__(self, capacity: int = 50_000):
        self.buffer: deque = deque(maxlen=capacity)

    def push(
        self,
        state: np.ndarray,
        action_p1: int,
        action_p2: int,
        reward: float,
        next_state: np.ndarray,
        done: float,
    ) -> None:
        self.buffer.append((state, action_p1, action_p2, reward, next_state, done))

    def sample(
        self, batch_size: int
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        batch = random.sample(self.buffer, batch_size)
        states, a1, a2, rewards, next_states, dones = zip(*batch)
        return (
            np.asarray(states, dtype=np.float32),
            np.asarray(a1, dtype=np.int64),
            np.asarray(a2, dtype=np.int64),
            np.asarray(rewards, dtype=np.float32),
            np.asarray(next_states, dtype=np.float32),
            np.asarray(dones, dtype=np.float32),
        )

    def __len__(self) -> int:
        return len(self.buffer)


def player_alive(state: np.ndarray, player_idx: int) -> bool:
    return bool(state[player_idx * PLAYER_OBS_DIM] > 0.5)


def select_actions(
    model: DQN,
    state: np.ndarray,
    epsilon: float,
    device: torch.device,
) -> tuple[int, int]:
    if random.random() < epsilon:
        a1 = random.randrange(ACTION_COUNT) if player_alive(state, 0) else ACTION_STAY
        a2 = random.randrange(ACTION_COUNT) if player_alive(state, 1) else ACTION_STAY
        return a1, a2

    with torch.no_grad():
        state_tensor = torch.as_tensor(
            state, dtype=torch.float32, device=device
        ).unsqueeze(0)
        logits = model(state_tensor)[0]

    a1 = (
        int(logits[:ACTION_COUNT].argmax().item())
        if player_alive(state, 0)
        else ACTION_STAY
    )
    a2 = (
        int(logits[ACTION_COUNT:].argmax().item())
        if player_alive(state, 1)
        else ACTION_STAY
    )
    return a1, a2


def optimize_model(
    policy_net: DQN,
    target_net: DQN,
    optimizer: optim.Optimizer,
    replay_buffer: ReplayBuffer,
    batch_size: int,
    gamma: float,
    device: torch.device,
) -> Optional[float]:
    if len(replay_buffer) < batch_size:
        return None

    states, actions_p1, actions_p2, rewards, next_states, dones = replay_buffer.sample(
        batch_size
    )
    s_t = torch.as_tensor(states, dtype=torch.float32, device=device)
    ns_t = torch.as_tensor(next_states, dtype=torch.float32, device=device)
    r_t = torch.as_tensor(rewards, dtype=torch.float32, device=device).unsqueeze(1)
    d_t = torch.as_tensor(dones, dtype=torch.float32, device=device).unsqueeze(1)
    a1_t = torch.as_tensor(actions_p1, dtype=torch.int64, device=device).unsqueeze(1)
    a2_t = (
        torch.as_tensor(actions_p2, dtype=torch.int64, device=device).unsqueeze(1)
        + ACTION_COUNT
    )

    p1_alive_t = (s_t[:, 0] > 0.5).float().unsqueeze(1)
    p2_alive_t = (s_t[:, PLAYER_OBS_DIM] > 0.5).float().unsqueeze(1)
    p1_alive_next = (ns_t[:, 0] > 0.5).float().unsqueeze(1)
    p2_alive_next = (ns_t[:, PLAYER_OBS_DIM] > 0.5).float().unsqueeze(1)

    all_q = policy_net(s_t)
    q_p1 = all_q.gather(1, a1_t)
    q_p2 = all_q.gather(1, a2_t)

    with torch.no_grad():
        next_q = target_net(ns_t)
        next_q_p1 = next_q[:, :ACTION_COUNT].max(dim=1, keepdim=True)[0] * p1_alive_next
        next_q_p2 = next_q[:, ACTION_COUNT:].max(dim=1, keepdim=True)[0] * p2_alive_next
        alive_next = (p1_alive_next + p2_alive_next).clamp(min=1.0)
        target_q = r_t + gamma * (next_q_p1 + next_q_p2) / alive_next * (1.0 - d_t)

    loss_p1 = (q_p1 - target_q).pow(2) * p1_alive_t
    loss_p2 = (q_p2 - target_q).pow(2) * p2_alive_t
    alive_now = (p1_alive_t + p2_alive_t).clamp(min=1.0)
    loss = (loss_p1 + loss_p2).sum() / alive_now.sum()

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    return float(loss.item())


def train(
    role: ROLE,
    episodes: int,
    output: str | None,
    seed: int = 0,
    map_pool: Optional[list[MapLayout]] = None,
) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    env = KOHTeamEnv(role=role, seed=seed, map_pool=map_pool)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    policy_net = DQN().to(device)
    target_net = DQN().to(device)
    target_net.load_state_dict(policy_net.state_dict())
    target_net.eval()

    optimizer = optim.Adam(policy_net.parameters(), lr=1e-3)
    replay_buffer = ReplayBuffer(capacity=50_000)

    gamma = 0.99
    batch_size = 128
    epsilon = 1.0
    epsilon_min = 0.05
    epsilon_decay = 0.997
    target_update_interval = 10

    recent_rewards: deque[float] = deque(maxlen=50)

    for episode in range(episodes):
        state = env.reset()
        done = False
        episode_reward = 0.0
        episode_losses: list[float] = []

        while not done:
            action_p1, action_p2 = select_actions(policy_net, state, epsilon, device)
            next_state, reward, done, _ = env.step(action_p1, action_p2)

            replay_buffer.push(
                state=state,
                action_p1=action_p1,
                action_p2=action_p2,
                reward=reward,
                next_state=next_state,
                done=float(done),
            )

            loss = optimize_model(
                policy_net=policy_net,
                target_net=target_net,
                optimizer=optimizer,
                replay_buffer=replay_buffer,
                batch_size=batch_size,
                gamma=gamma,
                device=device,
            )
            if loss is not None:
                episode_losses.append(loss)

            state = next_state
            episode_reward += reward

        if episode % target_update_interval == 0:
            target_net.load_state_dict(policy_net.state_dict())

        epsilon = max(epsilon_min, epsilon * epsilon_decay)
        recent_rewards.append(episode_reward)

        if episode % 50 == 0:
            avg_reward = sum(recent_rewards) / max(len(recent_rewards), 1)
            avg_loss = sum(episode_losses) / max(len(episode_losses), 1)
            print(
                f"ep={episode:5d} reward={episode_reward:8.1f} "
                f"avg50={avg_reward:8.1f} eps={epsilon:.3f} "
                f"loss={avg_loss:7.4f} buf={len(replay_buffer)}"
            )

    out_path = Path(output or f"{role}.safetensors")
    safetensors_save(policy_net.state_dict(), str(out_path))
    print(f"saved final weights to {out_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Asuri Major teaching baseline training")
    parser.add_argument("--role", choices=["attack", "defense"], required=True)
    parser.add_argument("--episodes", type=int, default=3000)
    parser.add_argument("--output", default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--map", dest="map_file", default=None, help="single map txt file")
    parser.add_argument(
        "--maps-dir",
        default=None,
        help="directory containing downloaded *.txt map files",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    map_pool = load_map_pool(args.map_file, args.maps_dir)
    if map_pool:
        print("loaded maps:", ", ".join(layout.name for layout in map_pool))
    else:
        print("loaded maps: default built-in layout from koh_env.py")
    train(args.role, args.episodes, args.output, seed=args.seed, map_pool=map_pool)
