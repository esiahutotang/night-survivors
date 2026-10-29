"""Explicit-level stats must match real upgrades without changing the game."""
import copy
import unittest
from rules import Game, load_config


class WeaponPreviewTests(unittest.TestCase):
    def test_preview_matches_every_weapon_upgrade(self):
        for name in ("spark", "blades", "ring"):
            for level in range(5):
                with self.subTest(name=name, level=level):
                    game = Game(seed=17)
                    if level:
                        game.weapons[name] = level
                    else:
                        game.weapons.pop(name, None)
                    weapons = game.weapons.copy()
                    rng = game.rng.getstate()
                    preview = game.weapon_stats(name, level + 1)
                    self.assertEqual(game.weapons, weapons)
                    self.assertEqual(game.rng.getstate(), rng)
                    game.cards = [name]
                    self.assertTrue(game.choose_card(0))
                    self.assertEqual(preview, game.weapon_stats(name))

    def test_preview_uses_custom_config(self):
        config = load_config()
        config["weapons"]["spark"].update(damage=37, damage_per_level=7,
            interval=1.2, interval_per_level=0.1, extra_spark_levels=[2, 4])
        snapshot = copy.deepcopy(config)
        game = Game(config, seed=3)
        stats = game.weapon_stats("spark", 2)
        self.assertEqual(stats["damage"], 44)
        self.assertAlmostEqual(stats["interval"], 1.1)
        self.assertEqual(stats["count"], 2)
        self.assertEqual(config, snapshot)

    def test_default_stats_still_use_equipped_level(self):
        game = Game(seed=1)
        for name in ("spark", "blades", "ring"):
            game.weapons[name] = 4
            self.assertEqual(game.weapon_stats(name), game.weapon_stats(name, 4))
