import math
import unittest
from rules import Enemy, Game, Gem, load_config


class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()
        self.game = Game(self.cfg, seed=3)
        self.dt = self.cfg["simulation"]["step"]

    def advance(self, seconds):
        for _ in range(round(seconds / self.dt)):
            self.game.update()

    def upgrade(self, name):
        self.game.cards = [name]
        self.assertTrue(self.game.choose_card(0))

    def test_gem_magnet_range_speed_latching_and_collection(self):
        g = self.game
        distant = Gem(g.magnet_radius+1, 0, 1)
        near = Gem(g.magnet_radius, 0, 1)
        g.gems = [distant, near]
        g.update()
        self.assertEqual(distant.x, g.magnet_radius+1)
        g.gems.remove(distant)
        self.assertAlmostEqual(near.x, g.magnet_radius-self.cfg["growth"]["gem_speed"]*self.dt)
        g.x = -g.magnet_radius*2
        x = near.x
        g.update()
        self.assertLess(near.x, x)  # A gem already flying keeps following.
        g.x = near.x
        g.update()
        self.assertNotIn(near, g.gems)
        self.assertEqual(g.xp, near.xp)

    def test_xp_threshold_overflow_and_level_up_freeze(self):
        g = self.game
        first = g.xp_needed
        g.gain_xp(first-1)
        self.assertFalse(g.cards)
        g.gain_xp(1 + first + self.cfg["growth"]["xp_per_level"])
        self.assertEqual(g.level, 2)
        self.assertEqual(g.xp, g.xp_needed)
        before = (g.x, g.y, g.elapsed, g.spawn_clock)
        g.update((100, 0))
        self.assertEqual((g.x, g.y, g.elapsed, g.spawn_clock), before)
        self.assertTrue(g.choose_card(0))
        self.assertEqual(g.level, 3)
        self.assertEqual(g.xp, 0)
        self.assertEqual(len(g.cards), self.cfg["growth"]["cards"])
        self.assertTrue(g.choose_card(0))
        self.assertFalse(g.cards)
        self.assertFalse(g.choose_card(0))

    def test_card_eligibility_caps_and_three_choices(self):
        g = self.game
        g.weapons = {"spark": self.cfg["weapons"]["max_level"]}
        g.passives["boots"] = self.cfg["passives"]["max_level"]
        g.gain_xp(g.xp_needed)
        self.assertEqual(len(g.cards), self.cfg["growth"]["cards"])
        self.assertEqual(len(set(g.cards)), len(g.cards))
        self.assertNotIn("spark", g.cards)
        self.assertNotIn("boots", g.cards)
        # A smaller configured weapon capacity must also prevent new weapons.
        self.cfg["weapons"]["max_owned"] = len(g.weapons)
        g.cards = []
        g.gain_xp(g.xp_needed)
        self.assertNotIn("blades", g.cards)
        self.assertNotIn("ring", g.cards)

    def test_last_upgrade_and_heal_fallback(self):
        g = self.game
        maximum = self.cfg["weapons"]["max_level"]
        g.weapons = dict.fromkeys(("spark", "blades", "ring"), maximum)
        g.passives = dict.fromkeys(g.passives, self.cfg["passives"]["max_level"])
        g.passives["magnet"] -= 1
        g.gain_xp(g.xp_needed)
        self.assertEqual(set(g.cards), {"magnet"})
        g.choose_card(0)
        g.hp = g.max_hp - self.cfg["growth"]["fallback_heal"] + 1
        g.gain_xp(g.xp_needed)
        self.assertEqual(set(g.cards), {"heal"})
        g.choose_card(0)
        self.assertEqual(g.hp, g.max_hp)
        self.assertFalse(g.choose_card(-1))

    def test_passive_speed_hp_heal_and_magnet(self):
        g = self.game
        self.upgrade("boots")
        g.update((100, 0))
        self.assertAlmostEqual(g.x, self.cfg["hero"]["speed"]*(1+self.cfg["passives"]["boots_speed_fraction"])*self.dt)
        g.hp -= self.cfg["passives"]["heart_heal"]
        old_hp = g.hp
        self.upgrade("heart")
        self.assertEqual(g.max_hp, self.cfg["hero"]["hp"] + self.cfg["passives"]["heart_hp"])
        self.assertEqual(g.hp, old_hp + self.cfg["passives"]["heart_heal"])
        self.upgrade("magnet")
        self.assertEqual(g.magnet_radius, self.cfg["hero"]["magnet_radius"] + self.cfg["passives"]["magnet_radius"])

    def test_weapon_progression_and_multiple_sparks(self):
        g = self.game
        for level in range(1, self.cfg["weapons"]["max_level"]+1):
            g.weapons["spark"] = level
            stats = g.weapon_stats("spark")
            base = self.cfg["weapons"]["spark"]
            self.assertEqual(stats["damage"], base["damage"]+(level-1)*base["damage_per_level"])
            self.assertAlmostEqual(stats["interval"], base["interval"]-(level-1)*base["interval_per_level"])
            self.assertEqual(stats["count"], base["count"] + sum(v <= level for v in base["extra_spark_levels"]))
        hp = self.cfg["enemies"]["bat"]["hp"]
        g.enemies = [Enemy(200, 0, hp), Enemy(0, 220, hp), Enemy(-240, 0, hp)]
        g.update()
        self.assertEqual(len(g.sparks), g.weapon_stats("spark")["count"])
        for name in ("blades", "ring"):
            for level in range(1, self.cfg["weapons"]["max_level"]+1):
                g.weapons[name] = level
                base = self.cfg["weapons"][name]
                stats = g.weapon_stats(name)
                self.assertEqual(stats["damage"], base["damage"]+(level-1)*base["damage_per_level"])
                if name == "ring":
                    self.assertEqual(stats["radius"], base["radius"]+(level-1)*base["radius_per_level"])
                else:
                    self.assertEqual(stats["count"], base["count"]+sum(v <= level for v in base["extra_blade_levels"]))

    def test_ring_hits_every_enemy_inside_on_interval(self):
        g = self.game
        g.weapons["ring"] = 1
        self.cfg["enemies"]["bat"]["speed"] = 0
        stats = g.weapon_stats("ring")
        hp = stats["damage"] * 10
        inside = [Enemy(stats["radius"]-1, 0, hp), Enemy(0, -stats["radius"], hp)]
        outside = Enemy(stats["radius"]+1, 0, hp)
        g.enemies = inside + [outside]
        g.attack_clock = float("inf")
        g.update()
        self.advance(stats["interval"]-self.dt)
        self.assertTrue(all(b.hp == hp-stats["damage"] for b in inside))
        g.update()
        self.assertTrue(all(b.hp == hp-2*stats["damage"] for b in inside))
        self.assertEqual(outside.hp, hp)

    def test_blades_orbit_and_per_blade_hit_cooldown(self):
        g = self.game
        g.weapons["blades"] = 1
        stats = g.weapon_stats("blades")
        start = g.blade_positions()[0]
        g.elapsed = stats["period"]/4
        quarter = g.blade_positions()[0]
        self.assertAlmostEqual(start[0], stats["orbit_radius"])
        self.assertAlmostEqual(quarter[0], 0)
        self.assertAlmostEqual(quarter[1], stats["orbit_radius"])
        # Keep one blade over one enemy to measure its hit interval precisely.
        g.elapsed = 0
        self.cfg["weapons"]["blades"]["period"] = 1e9
        self.cfg["enemies"]["bat"]["speed"] = 0
        hp = stats["damage"]*10
        bat = Enemy(stats["orbit_radius"], 0, hp)
        g.enemies = [bat]
        g.attack_clock = float("inf")
        g.update()
        self.advance(stats["hit_interval"]-self.dt)
        self.assertEqual(bat.hp, hp-stats["damage"])
        g.update()
        self.assertEqual(bat.hp, hp-2*stats["damage"])

    def test_each_weapon_kill_drops_one_gem(self):
        for name in ("blades", "ring"):
            with self.subTest(weapon=name):
                g = Game(load_config(), seed=2)
                g.weapons[name] = 1
                g.attack_clock = float("inf")
                radius = g.weapon_stats(name).get("orbit_radius", g.weapon_stats(name).get("radius"))
                g.enemies = [Enemy(radius, 0, 1)]
                g.update()
                self.assertEqual(g.kills, 1)
                self.assertEqual(len(g.gems), 1)
                self.assertEqual(g.gems[0].xp, self.cfg["enemies"]["bat"]["xp"])


if __name__ == "__main__":
    unittest.main()
