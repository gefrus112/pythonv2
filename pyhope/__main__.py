"""Command line entry point for PyHope."""

from __future__ import annotations

import argparse

from . import __version__
from .engine import Engine, Sprite, TileMap, Vec2, raycast


def _demo() -> None:
    world = TileMap.from_text(
        """
###########
#.........#
#..##.....#
#......M..#
#.........#
###########
""".strip("\n")
    )
    engine = Engine(world, width=42, height=16)
    engine.add(Sprite("comet", Vec2(2.5, 2.5), glyph="@"))
    engine.add(Sprite("monster", Vec2(7.5, 3.5), glyph="M"))
    print("PyHope demo — dependency-free ASCII scene\n")
    print(engine.render_ascii())
    hit = raycast(world, Vec2(2.5, 2.5), Vec2(1.0, 0.22))
    print(f"\nRay hit tile {hit.tile!r} at {hit.distance:.2f} units after {hit.steps} steps.")


def _check() -> None:
    world = TileMap.from_text("###\n#.#\n###")
    assert world.solid(0, 0)
    assert not world.solid(1, 1)
    hit = raycast(world, Vec2(1.5, 1.5), Vec2(1, 0))
    assert hit.tile == "#" and hit.distance > 0
    engine = Engine(world)
    engine.add(Sprite("hero", Vec2(1.5, 1.5)))
    engine.step(1 / 60)
    print(f"PyHope {__version__}: OK (no pygame, zero dependencies)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pyhope", description="PyHope game engine tools")
    parser.add_argument("--version", action="version", version=f"PyHope {__version__}")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--demo", action="store_true", help="render the built-in ASCII demo")
    group.add_argument("--check", action="store_true", help="run a quick installation check")
    group.add_argument("--studio", action="store_true", help="open the Python v2 + PyHope desktop workspace")
    args = parser.parse_args(argv)
    if args.studio:
        from pyv2.launcher import main as launch_studio
        return launch_studio()
    if args.check:
        _check()
    else:
        _demo()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
