"""PyHope — the tiny, dependency-free game engine bundled with Python v2.

PyHope deliberately avoids pygame and native extensions.  It provides the
portable game-logic pieces (vectors, sprites, tile maps, fixed-step scenes,
ray casting, and ASCII preview rendering).  The website adds Canvas/WebGL
renderers for full visual games.
"""

from .engine import Engine, RayHit, Sprite, TileMap, Vec2, raycast

__all__ = ["Engine", "RayHit", "Sprite", "TileMap", "Vec2", "raycast"]
__version__ = "1.1.0"
