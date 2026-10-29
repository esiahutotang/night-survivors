import math
import unittest
from rules import Enemy, Game, load_config


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()
        self.game = Game(self.cfg, seed=1)

    def advance(self, seconds, direction=None):
        for _ in range(round(seconds / self.cfg["simulation"]["step"])):
            self.game.update(direction)

    def test_persistent_pointer_and_dead_zone(self):
        self.advance(1, (100, 0))
        self.assertAlmostEqual(self.game.x, self.cfg["hero"]["speed"])
        x = self.game.x
        self.game.update((self.cfg["controls"]["stop_distance"], 0))
        self.assertEqual(self.game.x, x)
        self.game.update(None)
        self.assertEqual(self.game.x, x)

    def test_diagonal_speed(self):
        self.advance(0.5, (100, 100))
        self.assertAlmostEqual(math.hypot(self.game.x, self.game.y), self.cfg["hero"]["speed"] * 0.5)

    def test_spawn_budget_radius_minimum_and_cap(self):
        self.game.spawn_enemies()
        self.assertEqual(len(self.game.enemies), self.cfg["spawn"]["per_second"])
        for bat in self.game.enemies:
            self.assertAlmostEqual(math.hypot(bat.x, bat.y), self.cfg["spawn"]["radius"])
        self.game.spawn_enemies()
        self.assertEqual(len(self.game.enemies), self.cfg["waves"][0]["minimum"])
        self.cfg["waves"][0]["minimum"] = self.cfg["spawn"]["cap"] + 10
        for _ in range(30):
            self.game.spawn_enemies()
        self.assertEqual(len(self.game.enemies), self.cfg["spawn"]["cap"])

    def test_spawn_clock_and_distant_removal(self):
        self.advance(self.cfg["spawn"]["interval"] - self.cfg["simulation"]["step"])
        self.assertEqual(len(self.game.enemies), 0)
        self.game.update()
        self.assertEqual(len(self.game.enemies), self.cfg["spawn"]["per_second"])
        self.game.enemies = [Enemy(self.cfg["spawn"]["remove_distance"]+1, 0, 8)]
        self.game.update()
        self.assertEqual(self.game.enemies, [])

    def test_contact_damage_cooldown_and_game_over(self):
        self.game.attack_clock = float("inf")  # Isolate contact damage from automatic attacks.
        self.game.enemies = [Enemy(0, 0, self.cfg["enemies"]["bat"]["hp"])]
        damage = self.cfg["enemies"]["bat"]["damage"]
        self.game.update()
        self.assertEqual(self.game.hp, self.cfg["hero"]["hp"] - damage)
        self.advance(self.cfg["contact_interval"] - self.cfg["simulation"]["step"])
        self.assertEqual(self.game.hp, self.cfg["hero"]["hp"] - damage)
        self.game.update()
        self.assertEqual(self.game.hp, self.cfg["hero"]["hp"] - 2*damage)
        self.game.hp = damage
        self.advance(self.cfg["contact_interval"])
        self.assertTrue(self.game.game_over)
        self.assertEqual(self.game.hp, 0)
        elapsed = self.game.elapsed
        self.game.update((100, 0))
        self.assertEqual(self.game.elapsed, elapsed)

    def test_wand_aims_at_nearest_and_kills(self):
        hp = self.cfg["enemies"]["bat"]["hp"]
        near, far = Enemy(100, 0, hp), Enemy(0, 200, hp)
        self.game.enemies = [far, near]
        self.game.update()
        self.assertGreater(self.game.sparks[0].vx, 0)
        self.assertEqual(self.game.sparks[0].vy, 0)
        self.advance(0.3)
        self.assertNotIn(near, self.game.enemies)
        self.assertIn(far, self.game.enemies)
        self.assertEqual(self.game.kills, 1)
        self.assertEqual(len(self.game.gems), 1)
        self.assertEqual(self.game.gems[0].xp, self.cfg["enemies"]["bat"]["xp"])

    def test_pause_and_fresh_restart(self):
        self.game.paused = True
        self.advance(1, (100, 0))
        self.assertEqual(self.game.elapsed, 0)
        self.assertEqual(self.game.x, 0)
        fresh = Game(self.cfg)
        self.assertEqual(fresh.hp, self.cfg["hero"]["hp"])
        self.assertFalse(fresh.game_over)
        self.assertEqual(fresh.kills, 0)


if __name__ == "__main__":
    unittest.main()
