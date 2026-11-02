import copy
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


class ModifierTests(unittest.TestCase):
    """Behaviour of the four special daily words on the rules layer."""

    def setUp(self):
        self.base = load_config()

    def make_game(self, behaviour):
        cfg = copy.deepcopy(self.base)
        if behaviour:
            cfg["modifiers"] = dict(behaviour)
        game = Game(cfg, seed=1)
        game.attack_clock = float("inf")  # keep automatic attacks out of the way
        return game

    def touch_with_bat(self, game, hp=None):
        bat_hp = hp if hp is not None else self.base["enemies"]["bat"]["hp"]
        bat = Enemy(0, 0, bat_hp, kind="bat", max_hp=bat_hp)
        game.enemies = [bat]
        game.update(None)
        return bat

    def test_basics_scales_damage_linearly_and_doubles_hp(self):
        cfg = copy.deepcopy(self.base)
        cfg["hero"]["hp"] *= 2  # the HP doubling is applied by challenges.py
        cfg["modifiers"] = {"no_cards": True, "basics_damage_scale": 3,
                            "basics_damage_scale_per_level": 0.05}
        game = Game(cfg, seed=1)
        base_damage = self.base["weapons"]["spark"]["damage"]
        self.assertEqual(game.max_hp, self.base["hero"]["hp"] * 2)
        self.assertAlmostEqual(game.weapon_stats("spark")["damage"], base_damage * 3)
        game.level = 2
        self.assertAlmostEqual(game.weapon_stats("spark")["damage"], base_damage * 3.05)
        game.level = 6
        self.assertAlmostEqual(game.weapon_stats("spark")["damage"], base_damage * 3.25)

    def test_basics_day_offers_no_cards_and_stacks_levels(self):
        game = self.make_game({"no_cards": True, "basics_damage_scale": 3,
                               "basics_damage_scale_per_level": 0.05})
        for expected_level in (2, 3):
            game.gain_xp(game.xp_needed)
            self.assertEqual(game.cards, [])
            self.assertEqual(game.level, expected_level)
            self.assertEqual(game.xp, 0)

    def test_instakill_locks_hp_and_kills_every_hit(self):
        game = self.make_game({"instakill": True, "mercy_invincible_seconds": 1.5})
        self.assertEqual(game.max_hp, 1)
        self.assertEqual(game.hp, 1)
        bat = self.touch_with_bat(game, hp=999)
        game.hurt_enemy(bat, 1)  # any hit, even 1 damage, must kill a 999 HP enemy
        self.assertEqual(game.kills, 1)
        self.assertEqual(game.enemies, [])

    def test_instakill_mercy_window_forgives_once_then_kills(self):
        game = self.make_game({"instakill": True, "mercy_invincible_seconds": 1.5})
        self.touch_with_bat(game)
        self.assertFalse(game.game_over)
        self.assertEqual(game.hp, 1)
        self.assertGreater(game.invincible, 0)          # mercy window open
        self.touch_with_bat(game)                        # immune inside the window
        self.assertFalse(game.game_over)
        self.advance_seconds(game, 1.5)                  # window expires
        self.assertLessEqual(game.invincible, 1e-9)
        self.touch_with_bat(game)                        # next hit is lethal
        self.assertTrue(game.game_over)
        self.assertEqual(game.hp, 0)

    def test_instakill_without_mercy_is_pure_mutual_kill(self):
        game = self.make_game({"instakill": True, "mercy_invincible_seconds": 0})
        self.touch_with_bat(game)
        self.assertTrue(game.game_over)
        self.assertEqual(game.hp, 0)

    def advance_seconds(self, game, seconds):
        for _ in range(round(seconds / self.base["simulation"]["step"])):
            game.update(None)

    def test_feast_heals_the_hero_per_damage_dealt(self):
        game = self.make_game({"lifesteal": 0.05})
        game.hp = 1
        bat = Enemy(50, 0, 100, kind="bat", max_hp=100)
        game.enemies = [bat]
        game.hurt_enemy(bat, 20)                        # 20 damage cannot kill a 100 HP bat
        self.assertAlmostEqual(game.hp, 1 + 20 * 0.05)
        game.hp = game.max_hp
        game.hurt_enemy(bat, 20)  # healing is capped at max HP
        self.assertEqual(game.hp, game.max_hp)

    def test_feast_heals_enemies_per_damage_dealt(self):
        game = self.make_game({"lifesteal": 0.05})
        game.enemies = [Enemy(0, 0, 90, kind="bat", max_hp=100)]  # wounded bat bites back
        game.update(None)
        damage = self.base["enemies"]["bat"]["damage"]
        self.assertAlmostEqual(game.enemies[0].hp, 90 + damage * 0.05)

    def test_feast_never_heals_an_enemy_above_its_spawn_hp(self):
        game = self.make_game({"lifesteal": 0.05})
        bat_hp = self.base["enemies"]["bat"]["hp"]
        bat = Enemy(0, 0, bat_hp, kind="bat", max_hp=bat_hp)
        bat.hp = bat_hp - 0.01                       # one sliver below full
        game.enemies = [bat]
        game.hp = 50
        game.update(None)
        self.assertLessEqual(bat.hp, bat_hp)

    def test_reserved_shield_absorbs_one_lethal_hit(self):
        game = self.make_game({"instakill": True, "mercy_invincible_seconds": 0})
        game.shield = 1
        self.touch_with_bat(game)
        self.assertFalse(game.game_over)
        self.assertEqual(game.shield, 0)
        self.touch_with_bat(game)                     # shield spent, mercy disabled
        self.assertTrue(game.game_over)

    def test_normal_runs_have_no_modifier_behaviour(self):
        game = self.make_game(None)
        self.touch_with_bat(game)
        expected = self.base["hero"]["hp"] - self.base["enemies"]["bat"]["damage"]
        self.assertEqual(game.hp, expected)
        self.assertEqual(game.invincible, 0)
        self.assertFalse(game.mercy_spent)

    def quiet_config(self, **behaviour):
        """A config with no normal spawns, so boss timing can be observed alone."""
        cfg = copy.deepcopy(self.base)
        cfg["spawn"]["per_second"] = 0
        if behaviour:
            cfg["modifiers"] = dict(behaviour)
        return cfg

    def test_boss_at_spawns_the_single_boss_early(self):
        cfg = self.quiet_config(boss_at=45)
        game = Game(cfg, seed=1)
        self.advance_seconds(game, 45 - cfg["simulation"]["step"])
        self.assertEqual([e for e in game.enemies if e.kind == "demon"], [])
        game.update(None)
        demons = [e for e in game.enemies if e.kind == "demon"]
        self.assertEqual(len(demons), 1)
        self.assertEqual(demons[0].boss_scale, 1.0)

    def test_boss_rush_spawns_four_escalating_bosses(self):
        cfg = self.quiet_config(boss_schedule=[
            {"at": 60, "scale": 1.0}, {"at": 90, "scale": 1.3},
            {"at": 105, "scale": 1.6}, {"at": 115, "scale": 2.0}])
        cfg["hero"]["hp"] = 10 ** 6  # survive being cornered for two minutes
        game = Game(cfg, seed=1)
        game.attack_clock = float("inf")  # keep bosses alive for the check
        self.advance_seconds(game, 116)
        demons = [e for e in game.enemies if e.kind == "demon"]
        self.assertEqual([round(d.hp) for d in demons], [800, 1040, 1280, 1600])
        self.assertEqual([d.boss_scale for d in demons], [1.0, 1.3, 1.6, 2.0])

    def test_boss_scale_multiplies_speed(self):
        games = {}
        for scale in (1.0, 2.0):
            game = Game(self.quiet_config(), seed=1)
            game.attack_clock = float("inf")
            game.create_enemy("demon", boss_scale=scale)
            game.enemies[-1].x, game.enemies[-1].y = 40, 0
            game.update(None)
            games[scale] = game.enemies[0].x
        demon_speed = self.base["enemies"]["demon"]["speed"]
        self.assertAlmostEqual(games[1.0], 40 - demon_speed * self.base["simulation"]["step"])
        self.assertAlmostEqual(games[2.0], 40 - 2 * demon_speed * self.base["simulation"]["step"])

    def test_boss_scale_multiplies_contact_damage(self):
        game = Game(self.quiet_config(), seed=1)
        game.attack_clock = float("inf")
        game.create_enemy("demon", boss_scale=2.0)
        game.enemies[-1].x, game.enemies[-1].y = 0, 0  # move it on top of the hero
        game.update(None)  # it bites immediately
        self.assertEqual(game.hp,
                         self.base["hero"]["hp"] - 2 * self.base["enemies"]["demon"]["damage"])

    def test_offer_count_follows_growth_cards(self):
        for cards, expected in ((1, 1), (3, 3), (4, 4)):
            cfg = self.quiet_config()
            cfg["growth"]["cards"] = cards
            game = Game(cfg, seed=1)
            game.gain_xp(game.xp_needed)
            self.assertEqual(len(game.cards), expected)


if __name__ == "__main__":
    unittest.main()
