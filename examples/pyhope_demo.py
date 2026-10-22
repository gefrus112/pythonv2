"""Small PyHope demo. Run: python3 examples/pyhope_demo.py"""

# Keep the source-checkout demo runnable before installation. Once installed,
# the normal package import below is used without any special setup.
if __package__ in {None, ""}:
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pyhope import Engine, Sprite, TileMap, Vec2, raycast

WORLD = TileMap.from_text(
    """
##############
#............#
#..###.......#
#.........M..#
#............#
##############
""".strip()
)

engine = Engine(WORLD)
hero = engine.add(Sprite("comet", Vec2(2.5, 2.5), "@", Vec2(0.5, 0)))
engine.add(Sprite("beast", Vec2(10.5, 3.5), "M"))

for _ in range(4):
    engine.step(0.25)

print(engine.render_ascii())
hit = raycast(WORLD, hero.position, Vec2(1, 0.1))
print(f"Ray hit {hit.tile!r} at distance {hit.distance:.2f}")
