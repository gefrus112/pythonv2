"""Portable game-logic primitives for the PyHope engine.

The module uses only the Python standard library.  It is intentionally small,
easy to read, and renderer-neutral: game state can be previewed as ASCII in a
terminal or consumed by Canvas/WebGL on the web.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Callable, Iterable


@dataclass(frozen=True, slots=True)
class Vec2:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vec2":
        return Vec2(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    @property
    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def normalized(self) -> "Vec2":
        size = self.length
        return Vec2() if size == 0 else Vec2(self.x / size, self.y / size)

    def dot(self, other: "Vec2") -> float:
        return self.x * other.x + self.y * other.y


@dataclass(slots=True)
class Sprite:
    name: str
    position: Vec2
    glyph: str = "*"
    velocity: Vec2 = field(default_factory=Vec2)
    tags: set[str] = field(default_factory=set)
    alive: bool = True


class TileMap:
    """An immutable rectangular tile map. `.` and spaces are walkable."""

    def __init__(self, rows: Iterable[str]):
        self.rows = tuple(str(row) for row in rows)
        if not self.rows:
            raise ValueError("a TileMap needs at least one row")
        self.width = max(map(len, self.rows))
        self.rows = tuple(row.ljust(self.width, "#") for row in self.rows)
        self.height = len(self.rows)

    @classmethod
    def from_text(cls, text: str) -> "TileMap":
        return cls(text.splitlines())

    def at(self, x: int, y: int) -> str:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return "#"
        return self.rows[y][x]

    def solid(self, x: int, y: int) -> bool:
        return self.at(x, y) not in {".", " "}


@dataclass(frozen=True, slots=True)
class RayHit:
    tile: str
    position: Vec2
    distance: float
    side: int
    steps: int


def raycast(world: TileMap, origin: Vec2, direction: Vec2, max_steps: int = 128) -> RayHit:
    """Cast one grid ray with DDA and return the first solid tile hit."""

    ray = direction.normalized()
    if ray.length == 0:
        raise ValueError("ray direction must not be zero")

    map_x, map_y = math.floor(origin.x), math.floor(origin.y)
    delta_x = abs(1 / ray.x) if ray.x else math.inf
    delta_y = abs(1 / ray.y) if ray.y else math.inf

    if ray.x < 0:
        step_x = -1
        side_x = (origin.x - map_x) * delta_x
    else:
        step_x = 1
        side_x = (map_x + 1 - origin.x) * delta_x
    if ray.y < 0:
        step_y = -1
        side_y = (origin.y - map_y) * delta_y
    else:
        step_y = 1
        side_y = (map_y + 1 - origin.y) * delta_y

    side = 0
    for steps in range(1, max_steps + 1):
        if side_x < side_y:
            side_x += delta_x
            map_x += step_x
            side = 0
        else:
            side_y += delta_y
            map_y += step_y
            side = 1
        tile = world.at(map_x, map_y)
        if world.solid(map_x, map_y):
            distance = (
                (map_x - origin.x + (1 - step_x) / 2) / ray.x
                if side == 0
                else (map_y - origin.y + (1 - step_y) / 2) / ray.y
            )
            position = origin + ray * max(0.0, distance)
            return RayHit(tile, position, max(0.0, distance), side, steps)
    raise RuntimeError(f"ray did not hit within {max_steps} grid steps")


class Engine:
    """Tiny fixed-step scene manager used by PyHope examples and tests."""

    def __init__(self, world: TileMap, *, width: int = 80, height: int = 24, tick_rate: int = 60):
        self.world = world
        self.width = max(8, int(width))
        self.height = max(5, int(height))
        self.tick_rate = max(1, int(tick_rate))
        self.time = 0.0
        self.frame = 0
        self.sprites: list[Sprite] = []
        self._systems: list[Callable[["Engine", float], None]] = []

    def add(self, sprite: Sprite) -> Sprite:
        if any(item.name == sprite.name for item in self.sprites):
            raise ValueError(f"sprite name already exists: {sprite.name}")
        self.sprites.append(sprite)
        return sprite

    def find(self, name: str) -> Sprite | None:
        return next((item for item in self.sprites if item.name == name and item.alive), None)

    def system(self, callback: Callable[["Engine", float], None]) -> Callable[["Engine", float], None]:
        self._systems.append(callback)
        return callback

    def move(self, sprite: Sprite, delta: Vec2) -> None:
        target_x = sprite.position.x + delta.x
        target_y = sprite.position.y + delta.y
        x, y = sprite.position.x, sprite.position.y
        if not self.world.solid(math.floor(target_x), math.floor(y)):
            x = target_x
        if not self.world.solid(math.floor(x), math.floor(target_y)):
            y = target_y
        sprite.position = Vec2(x, y)

    def step(self, dt: float | None = None) -> None:
        dt = 1 / self.tick_rate if dt is None else max(0.0, min(float(dt), 0.25))
        for callback in tuple(self._systems):
            callback(self, dt)
        for sprite in self.sprites:
            if sprite.alive and sprite.velocity.length:
                self.move(sprite, sprite.velocity * dt)
        self.time += dt
        self.frame += 1

    def render_ascii(self) -> str:
        """Render the full tile map and live sprites as a terminal preview."""

        canvas = [list(row) for row in self.world.rows]
        for sprite in self.sprites:
            if not sprite.alive:
                continue
            x, y = math.floor(sprite.position.x), math.floor(sprite.position.y)
            if 0 <= x < self.world.width and 0 <= y < self.world.height:
                canvas[y][x] = (sprite.glyph or "*")[0]
        return "\n".join("".join(row) for row in canvas)
