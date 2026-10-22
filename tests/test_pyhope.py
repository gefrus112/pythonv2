"""Tests for the dependency-free PyHope engine."""

import unittest

from pyhope import Engine, Sprite, TileMap, Vec2, raycast


class TestVec2(unittest.TestCase):
    def test_vector_math_and_normalize(self):
        a = Vec2(3, 4)
        self.assertEqual(a.length, 5)
        self.assertEqual(a + Vec2(1, 2), Vec2(4, 6))
        self.assertEqual(a - Vec2(1, 2), Vec2(2, 2))
        self.assertEqual(a * 2, Vec2(6, 8))
        self.assertAlmostEqual(a.normalized().length, 1)
        self.assertEqual(Vec2().normalized(), Vec2())


class TestTileMap(unittest.TestCase):
    def test_padding_bounds_and_solidity(self):
        world = TileMap(["###", "#.", "###"])
        self.assertEqual((world.width, world.height), (3, 3))
        self.assertFalse(world.solid(1, 1))
        self.assertTrue(world.solid(2, 1))
        self.assertTrue(world.solid(-1, 1))

    def test_empty_map_rejected(self):
        with self.assertRaises(ValueError):
            TileMap([])


class TestRaycast(unittest.TestCase):
    def setUp(self):
        self.world = TileMap.from_text("#####\n#...#\n#...#\n#####")

    def test_cardinal_hit(self):
        hit = raycast(self.world, Vec2(1.5, 1.5), Vec2(1, 0))
        self.assertEqual(hit.tile, "#")
        self.assertAlmostEqual(hit.distance, 2.5)
        self.assertEqual(hit.side, 0)

    def test_diagonal_hit(self):
        hit = raycast(self.world, Vec2(2.5, 1.5), Vec2(1, 1))
        self.assertEqual(hit.tile, "#")
        self.assertGreater(hit.distance, 0)

    def test_zero_ray_rejected(self):
        with self.assertRaises(ValueError):
            raycast(self.world, Vec2(1.5, 1.5), Vec2())


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.world = TileMap.from_text("#####\n#...#\n#...#\n#####")

    def test_sprite_add_find_duplicate(self):
        engine = Engine(self.world)
        hero = engine.add(Sprite("hero", Vec2(1.5, 1.5), "@"))
        self.assertIs(engine.find("hero"), hero)
        with self.assertRaises(ValueError):
            engine.add(Sprite("hero", Vec2(2, 2)))
        hero.alive = False
        self.assertIsNone(engine.find("hero"))

    def test_fixed_step_system_and_collision(self):
        engine = Engine(self.world, tick_rate=20)
        hero = engine.add(Sprite("hero", Vec2(1.5, 1.5), "@", Vec2(1, 0)))
        called = []

        @engine.system
        def remember(scene, dt):
            called.append((scene.frame, dt))

        engine.step()
        self.assertAlmostEqual(hero.position.x, 1.55)
        self.assertEqual(called, [(0, 0.05)])
        self.assertEqual(engine.frame, 1)
        engine.move(hero, Vec2(10, 0))
        self.assertAlmostEqual(hero.position.x, 1.55)  # wall collision

    def test_ascii_renderer(self):
        engine = Engine(self.world)
        engine.add(Sprite("hero", Vec2(1.5, 1.5), "@"))
        rendered = engine.render_ascii()
        self.assertIn("#@..#", rendered)
        self.assertEqual(len(rendered.splitlines()), self.world.height)


if __name__ == "__main__":
    unittest.main()
