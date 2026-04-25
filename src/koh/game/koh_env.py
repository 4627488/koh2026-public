from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal, Optional, Protocol, Tuple, cast

import numpy as np

Role = Literal["attack", "defense"]
Winner = Literal["attacker", "defender", "draw", "ongoing"]
Position = Tuple[int, int]

GRID_SIZE = 25
MAX_STEPS = 200
PLANT_STEPS = 3
DEFUSE_STEPS = 3
BOMB_TIMER = 30
LOS_RANGE = 10
FIRE_RANGE = 5
FIRE_COOLDOWN_STEPS = 2

PLAYER_OBS_DIM = 36          # per-agent block: 1 alive + 2 pos + 4 sites + 3 tm + 6 enemies + 8 rays + 1 cd + 9 action_mask + 2 path_dist
OBSERVATION_DIM = PLAYER_OBS_DIM * 2 + 5   # 77: two player blocks + 5 global fields
ACTION_COUNT = 9
TEAM_ACTION_COUNT = 18

ACTION_UP = 0
ACTION_DOWN = 1
ACTION_LEFT = 2
ACTION_RIGHT = 3
ACTION_STAY = 4
ACTION_FIRE_UP = 5
ACTION_FIRE_DOWN = 6
ACTION_FIRE_LEFT = 7
ACTION_FIRE_RIGHT = 8

MOVE_ACTIONS = {ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_STAY}
FIRE_ACTIONS = {ACTION_FIRE_UP, ACTION_FIRE_DOWN, ACTION_FIRE_LEFT, ACTION_FIRE_RIGHT}

ACTION_DELTAS = {
    ACTION_UP: (-1, 0),
    ACTION_DOWN: (1, 0),
    ACTION_LEFT: (0, -1),
    ACTION_RIGHT: (0, 1),
    ACTION_STAY: (0, 0),
    ACTION_FIRE_UP: (0, 0),
    ACTION_FIRE_DOWN: (0, 0),
    ACTION_FIRE_LEFT: (0, 0),
    ACTION_FIRE_RIGHT: (0, 0),
}

FIRE_DELTAS = {
    ACTION_FIRE_UP: (-1, 0),
    ACTION_FIRE_DOWN: (1, 0),
    ACTION_FIRE_LEFT: (0, -1),
    ACTION_FIRE_RIGHT: (0, 1),
}

RAYCAST_DIRS: list[Position] = [
    (-1, 0),
    (1, 0),
    (0, -1),
    (0, 1),
    (-1, -1),
    (1, -1),
    (-1, 1),
    (1, 1),
]


@dataclass(frozen=True)
class MapLayout:
    name: str
    grid_size: int
    t_spawns: Tuple[Position, Position]
    ct_spawns: Tuple[Position, Position]
    bomb_site_a: Position
    bomb_site_b: Position
    obstacles: Tuple[Position, ...]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "grid_size": self.grid_size,
            "t_spawns": [list(p) for p in self.t_spawns],
            "ct_spawns": [list(p) for p in self.ct_spawns],
            "bomb_site_a": list(self.bomb_site_a),
            "bomb_site_b": list(self.bomb_site_b),
            "obstacles": [list(p) for p in self.obstacles],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MapLayout":
        return cls(
            name=str(d["name"]),
            grid_size=int(d["grid_size"]),
            t_spawns=(
                cast(Position, tuple(int(v) for v in d["t_spawns"][0])),
                cast(Position, tuple(int(v) for v in d["t_spawns"][1])),
            ),
            ct_spawns=(
                cast(Position, tuple(int(v) for v in d["ct_spawns"][0])),
                cast(Position, tuple(int(v) for v in d["ct_spawns"][1])),
            ),
            bomb_site_a=cast(Position, tuple(int(v) for v in d["bomb_site_a"])),
            bomb_site_b=cast(Position, tuple(int(v) for v in d["bomb_site_b"])),
            obstacles=tuple(
                cast(Position, tuple(int(v) for v in p)) for p in d["obstacles"]
            ),
        )


DEFAULT_MAP = MapLayout(
    name="default",
    grid_size=25,
    t_spawns=((23, 21), (23, 23)),
    ct_spawns=((1, 1), (1, 3)),
    bomb_site_a=(3, 12),
    bomb_site_b=(21, 12),
    obstacles=(
        (6, 4),
        (6, 5),
        (6, 6),
        (6, 18),
        (6, 19),
        (6, 20),
        (9, 10),
        (9, 11),
        (9, 13),
        (9, 14),
        (10, 10),
        (10, 14),
        (11, 10),
        (11, 12),
        (11, 14),
        (12, 10),
        (12, 14),
        (13, 10),
        (13, 12),
        (13, 14),
        (14, 10),
        (14, 14),
        (15, 10),
        (15, 11),
        (15, 13),
        (15, 14),
        (18, 4),
        (18, 5),
        (18, 6),
        (18, 18),
        (18, 19),
        (18, 20),
    ),
)


@dataclass(frozen=True)
class RoundLayout:
    round_id: int
    map_layout: MapLayout

    def to_dict(self) -> dict:
        return {
            "round_id": self.round_id,
            "map_layout": self.map_layout.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RoundLayout":
        return cls(
            round_id=int(d["round_id"]),
            map_layout=MapLayout.from_dict(d["map_layout"]),
        )


def make_round_layout(
    round_id: int, map_layout: Optional[MapLayout] = None
) -> RoundLayout:
    return RoundLayout(round_id=round_id, map_layout=map_layout or DEFAULT_MAP)


class PolicyLike(Protocol):
    def choose_action(self, observation: np.ndarray) -> Tuple[int, int]: ...


def _in_bounds(pos: Position, grid_size: int = GRID_SIZE) -> bool:
    return 0 <= pos[0] < grid_size and 0 <= pos[1] < grid_size


def _manhattan(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _los_clear(src: Position, dst: Position, obstacles: frozenset[Position]) -> bool:
    """
    Returns True iff the closed line segment from the source cell centre to the
    destination cell centre does not intersect any obstacle cell.

    Per the competition rules, touching an obstacle edge or corner counts as an
    intersection and therefore blocks visibility.
    """
    if src == dst:
        return True

    x0 = src[1] + 0.5
    y0 = src[0] + 0.5
    x1 = dst[1] + 0.5
    y1 = dst[0] + 0.5

    dx = x1 - x0
    dy = y1 - y0

    for row, col in obstacles:
        t0 = 0.0
        t1 = 1.0
        clipped = True

        for p, q in (
            (-dx, x0 - col),
            (dx, (col + 1.0) - x0),
            (-dy, y0 - row),
            (dy, (row + 1.0) - y0),
        ):
            if p == 0.0:
                if q < 0.0:
                    clipped = False
                    break
                continue

            t = q / p
            if p < 0.0:
                if t > t1:
                    clipped = False
                    break
                t0 = max(t0, t)
            else:
                if t < t0:
                    clipped = False
                    break
                t1 = min(t1, t)

        if clipped and t0 <= t1:
            return False
    return True


def _bfs_distances(
    start: Position, grid_size: int, obstacles: frozenset[Position]
) -> dict[Position, int]:
    """BFS from *start*; returns a mapping of reachable position → distance."""
    dist: dict[Position, int] = {start: 0}
    queue: deque[Position] = deque([start])
    while queue:
        pos = queue.popleft()
        r, c = pos
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            npos: Position = (r + dr, c + dc)
            if (
                0 <= npos[0] < grid_size
                and 0 <= npos[1] < grid_size
                and npos not in obstacles
                and npos not in dist
            ):
                dist[npos] = dist[pos] + 1
                queue.append(npos)
    return dist


class KOHBattleEnv:
    def __init__(self, layout: Optional[RoundLayout] = None, round_id: int = 0):
        self.layout = layout or make_round_layout(round_id)
        self.map = self.layout.map_layout
        self.grid_size = self.map.grid_size
        self._obstacle_set: frozenset[Position] = frozenset(self.map.obstacles)
        self._bomb_site_set: frozenset[Position] = frozenset(
            [self.map.bomb_site_a, self.map.bomb_site_b]
        )
        # Precompute shortest-path distances from each bomb site (obstacles are static).
        self._dist_to_a: dict[Position, int] = _bfs_distances(
            self.map.bomb_site_a, self.grid_size, self._obstacle_set
        )
        self._dist_to_b: dict[Position, int] = _bfs_distances(
            self.map.bomb_site_b, self.grid_size, self._obstacle_set
        )
        self.reset()

    def reset(self) -> None:
        self.step_count = 0
        self.t1_pos = self.map.t_spawns[0]
        self.t2_pos = self.map.t_spawns[1]
        self.ct1_pos = self.map.ct_spawns[0]
        self.ct2_pos = self.map.ct_spawns[1]

        self.t1_alive = True
        self.t2_alive = True
        self.ct1_alive = True
        self.ct2_alive = True

        self.t1_cooldown = 0
        self.t2_cooldown = 0
        self.ct1_cooldown = 0
        self.ct2_cooldown = 0

        self.bomb_planted = False
        self.bomb_site_planted: Optional[Position] = None
        self.bomb_timer = 0

        self._plant_progress_a = 0
        self._plant_progress_b = 0
        self.plant_progress = 0
        self.defuse_progress = 0

        self.last_result: dict = {}

    def snapshot(self) -> dict:
        site_a_progress, site_b_progress = self._site_progress_steps()
        return {
            "step": self.step_count,
            "round_id": self.layout.round_id,
            "grid_size": self.grid_size,
            "t1_position": list(self.t1_pos) if self.t1_alive else None,
            "t2_position": list(self.t2_pos) if self.t2_alive else None,
            "ct1_position": list(self.ct1_pos) if self.ct1_alive else None,
            "ct2_position": list(self.ct2_pos) if self.ct2_alive else None,
            "t1_alive": self.t1_alive,
            "t2_alive": self.t2_alive,
            "ct1_alive": self.ct1_alive,
            "ct2_alive": self.ct2_alive,
            "t1_cooldown": self.t1_cooldown,
            "t2_cooldown": self.t2_cooldown,
            "ct1_cooldown": self.ct1_cooldown,
            "ct2_cooldown": self.ct2_cooldown,
            "bomb_planted": self.bomb_planted,
            "site_a_progress": site_a_progress,
            "site_b_progress": site_b_progress,
            "plant_progress": self.plant_progress,
            "defuse_progress": self.defuse_progress,
            "bomb_timer": self.bomb_timer,
            "bomb_site": (
                list(self.bomb_site_planted) if self.bomb_site_planted else None
            ),
        }

    def render_ascii(self) -> str:
        board = [["." for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        for r, c in self._obstacle_set:
            board[r][c] = "X"
        ar, ac = self.map.bomb_site_a
        br, bc = self.map.bomb_site_b
        board[ar][ac] = "A"
        board[br][bc] = "B"
        if self.bomb_planted and self.bomb_site_planted is not None:
            pr, pc = self.bomb_site_planted
            board[pr][pc] = "*"
        if self.t1_alive:
            board[self.t1_pos[0]][self.t1_pos[1]] = "1"
        if self.t2_alive:
            board[self.t2_pos[0]][self.t2_pos[1]] = "2"
        if self.ct1_alive:
            board[self.ct1_pos[0]][self.ct1_pos[1]] = "3"
        if self.ct2_alive:
            board[self.ct2_pos[0]][self.ct2_pos[1]] = "4"
        return "\n".join(" ".join(row) for row in board)

    def _get_team_state(self, role: Role):
        if role == "attack":
            own = [
                (self.t1_pos, self.t1_alive, self.t1_cooldown),
                (self.t2_pos, self.t2_alive, self.t2_cooldown),
            ]
            enemy = [(self.ct1_pos, self.ct1_alive), (self.ct2_pos, self.ct2_alive)]
        else:
            own = [
                (self.ct1_pos, self.ct1_alive, self.ct1_cooldown),
                (self.ct2_pos, self.ct2_alive, self.ct2_cooldown),
            ]
            enemy = [(self.t1_pos, self.t1_alive), (self.t2_pos, self.t2_alive)]
        return own, enemy

    def _wall_ray_value(self, pos: Position, direction: Position) -> float:
        r, c = pos
        dr, dc = direction
        free_dist = 0
        while True:
            nr, nc = r + dr, c + dc
            if not _in_bounds((nr, nc), self.grid_size):
                return 1.0 / (free_dist + 1.0)
            if (nr, nc) in self._obstacle_set:
                return 1.0 / (free_dist + 1.0)
            free_dist += 1
            r, c = nr, nc

    def _is_visible(self, src: Position, dst: Position) -> bool:
        if _manhattan(src, dst) > LOS_RANGE:
            return False
        return _los_clear(src, dst, self._obstacle_set)

    def _encode_player_obs(
        self,
        self_pos: Position,
        self_alive: bool,
        self_cd: int,
        teammate_pos: Position,
        teammate_alive: bool,
        enemies: list[tuple[Position, bool]],
        occupied: frozenset[Position],
    ) -> list[float]:
        # Index layout (PLAYER_OBS_DIM = 36):
        #  [0]      alive flag (1.0 = alive, 0.0 = dead)
        #  [1-2]    self position (row, col) normalised
        #  [3-6]    relative offset to bomb-site A and B
        #  [7-9]    teammate relative offset + alive flag
        #  [10-12]  enemy-1 relative offset + visible flag
        #  [13-15]  enemy-2 relative offset + visible flag
        #  [16-23]  wall-ray distances (8 directions)
        #  [24]     fire-cooldown active (1.0 / 0.0)
        #  [25-33]  action mask for actions 0-8
        #  [34-35]  path distance to bomb-site A and B
        if not self_alive:
            return [0.0] * PLAYER_OBS_DIM

        factor = float(self.grid_size - 1)
        values: list[float] = [1.0, self_pos[0] / factor, self_pos[1] / factor]

        for site in (self.map.bomb_site_a, self.map.bomb_site_b):
            values.append((site[0] - self_pos[0]) / factor)
            values.append((site[1] - self_pos[1]) / factor)

        if teammate_alive:
            values.append((teammate_pos[0] - self_pos[0]) / factor)
            values.append((teammate_pos[1] - self_pos[1]) / factor)
            values.append(1.0)
        else:
            values.extend([0.0, 0.0, 0.0])

        for enemy_pos, enemy_alive in enemies:
            if enemy_alive and self._is_visible(self_pos, enemy_pos):
                values.append((enemy_pos[0] - self_pos[0]) / factor)
                values.append((enemy_pos[1] - self_pos[1]) / factor)
                values.append(1.0)
            else:
                values.extend([0.0, 0.0, 0.0])

        for direction in RAYCAST_DIRS:
            values.append(self._wall_ray_value(self_pos, direction))

        values.append(1.0 if self_cd > 0 else 0.0)

        # [25-33] action mask: 1.0 if the action is currently valid
        others = occupied - {self_pos}
        for action in range(ACTION_COUNT):
            if action == ACTION_STAY:
                values.append(1.0)
            elif action in MOVE_ACTIONS:
                dr, dc = ACTION_DELTAS[action]
                target: Position = (self_pos[0] + dr, self_pos[1] + dc)
                valid = (
                    _in_bounds(target, self.grid_size)
                    and target not in self._obstacle_set
                    and target not in others
                )
                values.append(1.0 if valid else 0.0)
            else:  # fire actions
                values.append(0.0 if self_cd > 0 else 1.0)

        # [34-35] shortest-path distance to each bomb site, capped and normalised
        _MAX_DIST = 48.0
        dist_a = self._dist_to_a.get(self_pos)
        dist_b = self._dist_to_b.get(self_pos)
        values.append(min(dist_a, _MAX_DIST) / _MAX_DIST if dist_a is not None else 1.0)
        values.append(min(dist_b, _MAX_DIST) / _MAX_DIST if dist_b is not None else 1.0)

        return values

    def get_observation(self, role: Role) -> np.ndarray:
        own, enemy = self._get_team_state(role)
        p1_pos, p1_alive, p1_cd = own[0]
        p2_pos, p2_alive, p2_cd = own[1]
        e1, e2 = enemy

        occupied: frozenset[Position] = frozenset(
            pos
            for pos, alive in [(p1_pos, p1_alive), (p2_pos, p2_alive), e1, e2]
            if alive
        )

        values: list[float] = []
        values.extend(
            self._encode_player_obs(p1_pos, p1_alive, p1_cd, p2_pos, p2_alive, [e1, e2], occupied)
        )
        values.extend(
            self._encode_player_obs(p2_pos, p2_alive, p2_cd, p1_pos, p1_alive, [e1, e2], occupied)
        )

        site_a_progress, site_b_progress = self._site_progress_ratios()
        values.append(site_a_progress)
        values.append(site_b_progress)
        values.append(min(float(self.defuse_progress) / DEFUSE_STEPS, 1.0))
        values.append(self.bomb_timer / BOMB_TIMER if self.bomb_planted else 0.0)
        values.append(max(0.0, (MAX_STEPS - self.step_count) / MAX_STEPS))

        return np.asarray(values, dtype=np.float32)

    def get_observations(self) -> dict:
        return {
            "attack": self.get_observation("attack"),
            "defense": self.get_observation("defense"),
        }

    def _decrement_cooldowns(self) -> None:
        self.t1_cooldown = max(0, self.t1_cooldown - 1)
        self.t2_cooldown = max(0, self.t2_cooldown - 1)
        self.ct1_cooldown = max(0, self.ct1_cooldown - 1)
        self.ct2_cooldown = max(0, self.ct2_cooldown - 1)

    def _site_progress_steps(self) -> tuple[int, int]:
        if self.bomb_planted:
            if self.bomb_site_planted == self.map.bomb_site_a:
                return PLANT_STEPS, 0
            if self.bomb_site_planted == self.map.bomb_site_b:
                return 0, PLANT_STEPS
        return self._plant_progress_a, self._plant_progress_b

    def _site_progress_ratios(self) -> tuple[float, float]:
        site_a_progress, site_b_progress = self._site_progress_steps()
        return (
            min(float(site_a_progress) / PLANT_STEPS, 1.0),
            min(float(site_b_progress) / PLANT_STEPS, 1.0),
        )

    def _fire_hit_target(
        self,
        shooter_pos: Position,
        fire_action: int,
        enemy_positions: list[tuple[str, Position, bool]],
    ) -> Optional[str]:
        dr, dc = FIRE_DELTAS[fire_action]
        r, c = shooter_pos
        for _ in range(FIRE_RANGE):
            r += dr
            c += dc
            cell = (r, c)
            if not _in_bounds(cell, self.grid_size) or cell in self._obstacle_set:
                return None
            for name, pos, alive in enemy_positions:
                if alive and pos == cell:
                    return name
        return None

    def _resolve_fire(
        self, actions: dict[str, int], old_state: dict[str, tuple[Position, bool, int]]
    ) -> set[str]:
        to_kill: set[str] = set()
        fired: set[str] = set()

        enemy_map = {
            "t1": ["ct1", "ct2"],
            "t2": ["ct1", "ct2"],
            "ct1": ["t1", "t2"],
            "ct2": ["t1", "t2"],
        }

        for shooter in ("t1", "t2", "ct1", "ct2"):
            pos, alive, cd = old_state[shooter]
            action = int(actions.get(shooter, ACTION_STAY))
            if (not alive) or (action not in FIRE_ACTIONS) or cd > 0:
                continue
            target_names = enemy_map[shooter]
            enemies = [
                (name, old_state[name][0], old_state[name][1]) for name in target_names
            ]
            hit = self._fire_hit_target(pos, action, enemies)
            if hit is not None:
                to_kill.add(hit)
            fired.add(shooter)

        for shooter in fired:
            if shooter == "t1":
                self.t1_cooldown = FIRE_COOLDOWN_STEPS + 1
            elif shooter == "t2":
                self.t2_cooldown = FIRE_COOLDOWN_STEPS + 1
            elif shooter == "ct1":
                self.ct1_cooldown = FIRE_COOLDOWN_STEPS + 1
            else:
                self.ct2_cooldown = FIRE_COOLDOWN_STEPS + 1

        return to_kill

    def _apply_deaths(self, dead: set[str]) -> None:
        if "t1" in dead:
            self.t1_alive = False
        if "t2" in dead:
            self.t2_alive = False
        if "ct1" in dead:
            self.ct1_alive = False
        if "ct2" in dead:
            self.ct2_alive = False

    def _resolve_movements(
        self, actions: dict[str, int], old_state: dict[str, tuple[Position, bool, int]]
    ) -> None:
        start_positions = {
            name: state[0] for name, state in old_state.items() if state[1]
        }
        occupied_start = set(start_positions.values())

        proposed: dict[str, Position] = {}
        for name in ("t1", "t2", "ct1", "ct2"):
            pos, alive, _ = old_state[name]
            if not alive:
                continue
            action = int(actions.get(name, ACTION_STAY))
            if action not in MOVE_ACTIONS:
                proposed[name] = pos
                continue

            dr, dc = ACTION_DELTAS[action]
            target = (pos[0] + dr, pos[1] + dc)
            if action == ACTION_STAY:
                proposed[name] = pos
                continue
            if (not _in_bounds(target, self.grid_size)) or (
                target in self._obstacle_set
            ):
                proposed[name] = pos
                continue
            if target in occupied_start:
                proposed[name] = pos
                continue
            proposed[name] = target

        target_count: dict[Position, int] = {}
        for target in proposed.values():
            target_count[target] = target_count.get(target, 0) + 1

        for name in ("t1", "t2", "ct1", "ct2"):
            pos, alive, _ = old_state[name]
            if not alive:
                continue
            target = proposed.get(name, pos)
            if target_count.get(target, 0) > 1 and target != pos:
                target = pos
            if name == "t1":
                self.t1_pos = target
            elif name == "t2":
                self.t2_pos = target
            elif name == "ct1":
                self.ct1_pos = target
            else:
                self.ct2_pos = target

    def _update_bomb_state(self, actions: dict[str, int]) -> None:
        if not self.bomb_planted:
            contributors_a = 0
            contributors_b = 0

            if self.t1_alive and int(actions.get("t1", ACTION_STAY)) == ACTION_STAY:
                if self.t1_pos == self.map.bomb_site_a:
                    contributors_a += 1
                elif self.t1_pos == self.map.bomb_site_b:
                    contributors_b += 1
            if self.t2_alive and int(actions.get("t2", ACTION_STAY)) == ACTION_STAY:
                if self.t2_pos == self.map.bomb_site_a:
                    contributors_a += 1
                elif self.t2_pos == self.map.bomb_site_b:
                    contributors_b += 1

            if contributors_a > 0:
                self._plant_progress_a += 1
            else:
                self._plant_progress_a = 0

            if contributors_b > 0:
                self._plant_progress_b += 1
            else:
                self._plant_progress_b = 0

            self.plant_progress = max(self._plant_progress_a, self._plant_progress_b)
            if self._plant_progress_a >= PLANT_STEPS:
                self.bomb_planted = True
                self.bomb_site_planted = self.map.bomb_site_a
                self.bomb_timer = BOMB_TIMER
                self.plant_progress = PLANT_STEPS
            elif self._plant_progress_b >= PLANT_STEPS:
                self.bomb_planted = True
                self.bomb_site_planted = self.map.bomb_site_b
                self.bomb_timer = BOMB_TIMER
                self.plant_progress = PLANT_STEPS
        else:
            self.bomb_timer = max(0, self.bomb_timer - 1)
            if self.bomb_site_planted is not None:
                contributors_defuse = 0
                if (
                    self.ct1_alive
                    and self.ct1_pos == self.bomb_site_planted
                    and int(actions.get("ct1", ACTION_STAY)) == ACTION_STAY
                ):
                    contributors_defuse += 1
                if (
                    self.ct2_alive
                    and self.ct2_pos == self.bomb_site_planted
                    and int(actions.get("ct2", ACTION_STAY)) == ACTION_STAY
                ):
                    contributors_defuse += 1
                if contributors_defuse > 0:
                    self.defuse_progress += 1
                else:
                    self.defuse_progress = 0

    def _build_result(self, winner: Winner, reason: str) -> dict:
        site_a_progress, site_b_progress = self._site_progress_steps()
        return {
            "winner": winner,
            "reason": reason,
            "steps": self.step_count,
            "t1_alive": self.t1_alive,
            "t2_alive": self.t2_alive,
            "ct1_alive": self.ct1_alive,
            "ct2_alive": self.ct2_alive,
            "bomb_planted": self.bomb_planted,
            "bomb_site": (
                list(self.bomb_site_planted) if self.bomb_site_planted else None
            ),
            "bomb_timer": self.bomb_timer,
            "site_a_progress": site_a_progress,
            "site_b_progress": site_b_progress,
            "plant_progress": self.plant_progress,
            "defuse_progress": self.defuse_progress,
            "t1_position": list(self.t1_pos),
            "t2_position": list(self.t2_pos),
            "ct1_position": list(self.ct1_pos),
            "ct2_position": list(self.ct2_pos),
            "round_id": self.layout.round_id,
        }

    def _check_win(self) -> Optional[tuple[Winner, str]]:
        t_alive = self.t1_alive or self.t2_alive
        ct_alive = self.ct1_alive or self.ct2_alive

        # 1. 任务终局判定 (最高优先级)
        if self.bomb_planted and self.bomb_timer <= 0:
            return ("attacker", "bomb_exploded")
        if self.defuse_progress >= DEFUSE_STEPS:
            return ("defender", "bomb_defused")

        # 2. 全歼判定 (Elimination)
        # 优先级 A: 若进攻方在未下包前全灭，防守方获胜 (包括双方同时阵亡的情况)
        if (not t_alive) and (not self.bomb_planted):
            return ("defender", "all_t_dead")
        
        # 优先级 B: 若防守方全灭，进攻方获胜 (无论是否下包)
        # 因为若已下包，防守方全灭意味着已无人可拆弹，进攻方获胜
        if not ct_alive:
            return ("attacker", "all_ct_dead")

        # 3. 超时判定 (Timeout)
        if self.step_count >= MAX_STEPS and (not self.bomb_planted):
            return ("defender", "timeout")

        # 4. 若进攻方在已下包后全灭，对局持续 (等待爆炸或幸存的防守方拆弹)
        return None

    def step(
        self, t1_action: int, t2_action: int, ct1_action: int, ct2_action: int
    ) -> tuple[dict, bool, dict]:
        self.step_count += 1
        self._decrement_cooldowns()

        old_state = {
            "t1": (self.t1_pos, self.t1_alive, self.t1_cooldown),
            "t2": (self.t2_pos, self.t2_alive, self.t2_cooldown),
            "ct1": (self.ct1_pos, self.ct1_alive, self.ct1_cooldown),
            "ct2": (self.ct2_pos, self.ct2_alive, self.ct2_cooldown),
        }
        actions = {
            "t1": int(t1_action),
            "t2": int(t2_action),
            "ct1": int(ct1_action),
            "ct2": int(ct2_action),
        }

        dead = self._resolve_fire(actions, old_state)
        self._apply_deaths(dead)

        move_state = {
            "t1": (self.t1_pos, self.t1_alive, self.t1_cooldown),
            "t2": (self.t2_pos, self.t2_alive, self.t2_cooldown),
            "ct1": (self.ct1_pos, self.ct1_alive, self.ct1_cooldown),
            "ct2": (self.ct2_pos, self.ct2_alive, self.ct2_cooldown),
        }
        self._resolve_movements(actions, move_state)
        self._update_bomb_state(actions)

        win = self._check_win()
        if win is not None:
            winner, reason = win
            result = self._build_result(winner, reason)
            self.last_result = result
            return self.get_observations(), True, result

        result = self._build_result("ongoing", "in_progress")
        self.last_result = result
        return self.get_observations(), False, result

    def run_match(
        self, t_policy: PolicyLike, ct_policy: PolicyLike, capture_replay: bool = False
    ) -> dict:
        self.reset()
        replay: Optional[dict] = None
        if capture_replay:
            replay = {
                "layout": self.layout.to_dict(),
                "max_steps": MAX_STEPS,
                "frames": [
                    {
                        "step": 0,
                        "phase": "start",
                        "t_actions": None,
                        "ct_actions": None,
                        "state": self.snapshot(),
                        "result": None,
                    }
                ],
            }

        while True:
            t_obs = self.get_observation("attack")
            ct_obs = self.get_observation("defense")
            t1_action, t2_action = t_policy.choose_action(t_obs)
            ct1_action, ct2_action = ct_policy.choose_action(ct_obs)
            _, done, result = self.step(t1_action, t2_action, ct1_action, ct2_action)

            if capture_replay and replay is not None:
                replay["frames"].append(
                    {
                        "step": self.step_count,
                        "phase": "end" if done else "in_progress",
                        "t_actions": [int(t1_action), int(t2_action)],
                        "ct_actions": [int(ct1_action), int(ct2_action)],
                        "state": self.snapshot(),
                        "result": result if done else None,
                    }
                )

            if done:
                payload: dict = {"result": result}
                if capture_replay and replay is not None:
                    replay["result"] = result
                    payload["replay"] = replay
                return payload
