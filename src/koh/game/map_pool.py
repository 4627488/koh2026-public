from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from sqlalchemy.orm import Session

from koh.db.models import GameMap, MapTemplate
from koh.game.koh_env import GRID_SIZE, MapLayout, RoundLayout
from koh.security import utc_now

ASCII_MAP_CHARS = {".", "#", "A", "B", "T", "C"}


class MapFormatError(ValueError):
    pass


def normalize_map_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def map_slug_from_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_name).strip("-").lower()
    return slug or "map"


def parse_ascii_map(text: str, *, name: str) -> MapLayout:
    normalized = normalize_map_text(text)
    lines = normalized.splitlines()
    if len(lines) != GRID_SIZE:
        raise MapFormatError(f"expected {GRID_SIZE} rows, got {len(lines)}")

    obstacles: list[tuple[int, int]] = []
    t_spawns: list[tuple[int, int]] = []
    ct_spawns: list[tuple[int, int]] = []
    bomb_site_a: list[tuple[int, int]] = []
    bomb_site_b: list[tuple[int, int]] = []

    for row_idx, line in enumerate(lines):
        if len(line) != GRID_SIZE:
            raise MapFormatError(
                f"row {row_idx + 1} must have {GRID_SIZE} columns, got {len(line)}"
            )
        for col_idx, cell in enumerate(line):
            if cell not in ASCII_MAP_CHARS:
                raise MapFormatError(
                    f"invalid cell '{cell}' at row {row_idx + 1}, col {col_idx + 1}"
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
        raise MapFormatError(f"expected 2 T spawns, got {len(t_spawns)}")
    if len(ct_spawns) != 2:
        raise MapFormatError(f"expected 2 CT spawns, got {len(ct_spawns)}")
    if len(bomb_site_a) != 1:
        raise MapFormatError(f"expected 1 bomb site A, got {len(bomb_site_a)}")
    if len(bomb_site_b) != 1:
        raise MapFormatError(f"expected 1 bomb site B, got {len(bomb_site_b)}")

    return MapLayout(
        name=name,
        grid_size=GRID_SIZE,
        t_spawns=(t_spawns[0], t_spawns[1]),
        ct_spawns=(ct_spawns[0], ct_spawns[1]),
        bomb_site_a=bomb_site_a[0],
        bomb_site_b=bomb_site_b[0],
        obstacles=tuple(sorted(obstacles)),
    )


def serialize_ascii_map(layout: MapLayout) -> str:
    grid = [["." for _ in range(layout.grid_size)] for _ in range(layout.grid_size)]

    def place(pos: tuple[int, int], token: str) -> None:
        row, col = pos
        if not (0 <= row < layout.grid_size and 0 <= col < layout.grid_size):
            raise MapFormatError(f"position out of bounds: {pos}")
        if grid[row][col] != ".":
            raise MapFormatError(f"position collision at {pos}")
        grid[row][col] = token

    for pos in layout.obstacles:
        place(pos, "#")
    place(layout.bomb_site_a, "A")
    place(layout.bomb_site_b, "B")
    for pos in layout.t_spawns:
        place(pos, "T")
    for pos in layout.ct_spawns:
        place(pos, "C")
    return "\n".join("".join(row) for row in grid)


def list_map_templates(db: Session, *, active_only: bool = False) -> list[MapTemplate]:
    query = db.query(MapTemplate)
    if active_only:
        query = query.filter(MapTemplate.is_active.is_(True))
    return query.order_by(MapTemplate.sort_order.asc(), MapTemplate.id.asc()).all()


def create_or_update_map_template(
    db: Session,
    *,
    name: str,
    source_text: str,
    sort_order: int,
    difficulty: float,
    is_active: bool,
    created_by_user_id: int | None,
    template: MapTemplate | None = None,
) -> MapTemplate:
    normalized_name = name.strip()
    if not normalized_name:
        raise MapFormatError("map name is required")

    layout = parse_ascii_map(source_text, name=normalized_name)
    now = utc_now().replace(tzinfo=None)

    if template is None:
        template = MapTemplate(
            slug=_unique_slug(db, map_slug_from_name(normalized_name)),
            name=normalized_name,
            source_text=serialize_ascii_map(layout),
            layout_json=layout.to_dict(),
            sort_order=sort_order,
            difficulty=max(0.0, min(1.0, float(difficulty))),
            is_active=is_active,
            created_by_user_id=created_by_user_id,
            created_at=now,
            updated_at=now,
        )
        db.add(template)
    else:
        template.name = normalized_name
        template.source_text = serialize_ascii_map(layout)
        template.layout_json = layout.to_dict()
        template.sort_order = sort_order
        template.difficulty = max(0.0, min(1.0, float(difficulty)))
        template.is_active = is_active
        template.updated_at = now
    db.flush()
    return template


def ensure_round_maps(db: Session, round_id: int) -> list[GameMap]:
    rows = (
        db.query(GameMap)
        .filter(GameMap.round_id == round_id)
        .order_by(GameMap.map_idx.asc())
        .all()
    )
    if rows:
        return rows

    templates = list_map_templates(db, active_only=True)
    if not templates:
        raise MapFormatError("no active maps available")

    created: list[GameMap] = []
    for map_idx, template in enumerate(templates):
        round_layout = RoundLayout(
            round_id=round_id,
            map_layout=MapLayout.from_dict(template.layout_json),
        )
        row = GameMap(
            round_id=round_id,
            template_id=template.id,
            map_idx=map_idx,
            seed=template.slug,
            difficulty=template.difficulty,
            layout_json=round_layout.to_dict(),
        )
        db.add(row)
        created.append(row)
    db.flush()
    return created


def _unique_slug(db: Session, base_slug: str) -> str:
    slug = base_slug or "map"
    candidate = slug
    suffix = 2
    while (
        db.query(MapTemplate.id).filter(MapTemplate.slug == candidate).first() is not None
    ):
        candidate = f"{slug}-{suffix}"
        suffix += 1
    return candidate
