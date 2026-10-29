import math
import unittest
from rules import Enemy, Game, load_config


class WaveTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()
        self.game = Game(self.cfg, seed=9)
        self.dt = self.cfg["simulation"]["step"]

    def test_all_wave_boundaries_types_minima_and_spawn_budget(self):
        for index, wave in enumerate(self.cfg["waves"]):
            with self.subTest(time=wave["from"]):
                g = Game(load_config(), seed=9)
                g.elapsed = wave["from"]
                self.assertEqual(g.current_wave, wave)
                if index:
                    g.elapsed -= self.dt
                    self.assertEqual(g.current_wave, self.cfg["waves"][index-1])
                    g.elapsed += self.dt
                g.spawn_enemies()
                self.assertEqual(len(g.enemies), min(wave["minimum"], self.cfg["spawn"]["per_second"]))
                for _ in range(wave["minimum"]):
                    before = len(g.enemies)
                    g.spawn_enemies()
                    self.assertLessEqual(len(g.enemies)-before, self.cfg["spawn"]["per_second"])
                self.assertEqual(len(g.enemies), wave["minimum"])
                self.assertEqual({e.kind for e in g.enemies}, set(wave["types"]))
                for enemy in g.enemies:
                    self.assertEqual(enemy.hp, self.cfg["enemies"][enemy.kind]["hp"])
                    self.assertAlmostEqual(math.hypot(enemy.x, enemy.y), self.cfg["spawn"]["radius"])

    def test_transition_applies_at_exact_simulation_tick(self):
        for wave in self.cfg["waves"][1:]:
            g = Game(load_config(), seed=2)
            g.elapsed = wave["from"]-self.dt
            g.spawn_clock = self.cfg["spawn"]["interval"]-self.dt
            g.update()
            self.assertEqual(g.current_wave, wave)
            self.assertLessEqual(len(g.enemies), self.cfg["spawn"]["per_second"])
            self.assertTrue(all(e.kind in wave["types"] or e.kind == "demon" for e in g.enemies))

    def test_enemy_speeds_contact_damage_and_cooldowns(self):
        for kind, stats in self.cfg["enemies"].items():
            with self.subTest(kind=kind):
                g = Game(load_config())
                g.attack_clock = float("inf")
                enemy = Enemy(200, 0, stats["hp"], kind=kind)
                g.enemies = [enemy]
                g.update()
                self.assertAlmostEqual(enemy.x, 200-stats["speed"]*self.dt)
                enemy.x = enemy.y = 0
                g.update()
                hp = self.cfg["hero"]["hp"]-stats["damage"]
                self.assertEqual(g.hp, hp)
                for _ in range(round(self.cfg["contact_interval"]/self.dt)-1):
                    g.update()
                self.assertEqual(g.hp, hp)
                g.update()
                self.assertEqual(g.hp, hp-stats["damage"])

    def test_boss_once_at_scheduled_time_including_after_death(self):
        g = self.game
        boss_time = next(w["from"] for w in self.cfg["waves"] if w.get("boss"))
        g.elapsed = boss_time-self.dt
        self.assertEqual(g.ensure_boss(), 0)
        g.elapsed = boss_time
        self.assertEqual(g.ensure_boss(), 1)
        boss = next(e for e in g.enemies if e.kind == "demon")
        self.assertEqual(boss.hp, self.cfg["enemies"]["demon"]["hp"])
        self.assertEqual(g.ensure_boss(), 0)
        g.hurt_enemy(boss, boss.hp)
        self.assertEqual(g.kills, 1)
        self.assertEqual(g.gems, [])
        self.assertEqual(g.ensure_boss(), 0)

    def test_boss_at_cap_and_normal_spawns_never_exceed_cap(self):
        g = self.game
        g.elapsed = next(w["from"] for w in self.cfg["waves"] if w.get("boss"))
        for _ in range(self.cfg["spawn"]["cap"]):
            g.create_enemy("bat")
        self.assertEqual(g.ensure_boss(), 1)
        self.assertEqual(len(g.enemies), self.cfg["spawn"]["cap"])
        self.assertEqual(sum(e.kind == "demon" for e in g.enemies), 1)
        g.spawn_enemies()
        self.assertEqual(len(g.enemies), self.cfg["spawn"]["cap"])

    def test_normal_despawn_and_boss_return_preserves_health(self):
        g = self.game
        for kind in ("bat", "slime", "ghost"):
            g.enemies.append(Enemy(self.cfg["spawn"]["remove_distance"]+1, 0,
                                   self.cfg["enemies"][kind]["hp"], kind=kind))
        hp = self.cfg["enemies"]["demon"]["hp"] / 2
        boss = Enemy(self.cfg["spawn"]["remove_distance"]+1, 0, hp, kind="demon")
        g.enemies.append(boss)
        g.update()
        self.assertEqual(g.enemies, [boss])
        self.assertAlmostEqual(math.hypot(boss.x, boss.y),
                               self.cfg["spawn"]["radius"]-self.cfg["enemies"]["demon"]["speed"]*self.dt)
        self.assertEqual(boss.hp, hp)

    def test_all_enemy_xp_and_weapons_against_new_enemies(self):
        for kind, stats in self.cfg["enemies"].items():
            for weapon in ("spark", "blades", "ring"):
                with self.subTest(kind=kind, weapon=weapon):
                    g = Game(load_config())
                    if weapon == "spark":
                        x = 100
                    else:
                        g.weapons[weapon] = 1
                        g.attack_clock = float("inf")
                        x = g.weapon_stats(weapon).get("orbit_radius", g.weapon_stats(weapon).get("radius"))-1
                    enemy = Enemy(x, 0, stats["hp"], kind=kind)
                    g.enemies = [enemy]
                    for _ in range(round(0.3/self.dt) if weapon == "spark" else 1):
                        g.update()
                    self.assertLess(enemy.hp, stats["hp"])
                    if enemy in g.enemies:
                        g.hurt_enemy(enemy, enemy.hp)
                    self.assertEqual(g.kills, 1)
                    self.assertEqual(sum(gem.xp for gem in g.gems)+g.xp, stats["xp"])

    def test_victory_exactly_at_goal_freezes_and_restart_is_fresh(self):
        g = self.game
        goal = self.cfg["goal"]["survive_seconds"]
        g.elapsed = goal-2*self.dt
        g.paused = True
        g.update()
        self.assertAlmostEqual(g.elapsed, goal-2*self.dt)
        g.paused = False
        g.gain_xp(g.xp_needed)
        g.update()
        self.assertAlmostEqual(g.elapsed, goal-2*self.dt)
        g.choose_card(0)
        g.update()
        self.assertFalse(g.victory)
        g.update()
        self.assertTrue(g.victory)
        self.assertFalse(g.game_over)
        self.assertEqual(g.elapsed, goal)
        before = (g.x, g.hp, g.kills, len(g.enemies))
        g.update((100, 0))
        self.assertEqual((g.x, g.hp, g.kills, len(g.enemies)), before)
        fresh = Game(self.cfg)
        self.assertFalse(fresh.finished)
        self.assertFalse(fresh.boss_spawned)
        self.assertEqual(fresh.elapsed, 0)
        self.assertEqual(fresh.level, 1)

    def test_lethal_contact_on_final_tick_is_game_over(self):
        g = self.game
        stats = self.cfg["enemies"]["bat"]
        g.hp = stats["damage"]
        g.elapsed = self.cfg["goal"]["survive_seconds"]-self.dt
        g.enemies = [Enemy(0, 0, stats["hp"])]
        g.update()
        self.assertTrue(g.game_over)
        self.assertFalse(g.victory)

    def test_full_two_minute_simulation_with_upgrade_choices(self):
        # Extra HP isolates the complete wave schedule from player skill.
        self.cfg["hero"]["hp"] *= 1000
        g = Game(self.cfg, seed=4)
        seen = set()
        for _ in range(round(self.cfg["goal"]["survive_seconds"]/self.dt)):
            while g.cards:
                g.choose_card(0)
            g.update((100, 0))
            seen.update(e.kind for e in g.enemies)
            self.assertLessEqual(len(g.enemies), self.cfg["spawn"]["cap"])
        self.assertTrue(g.victory)
        self.assertTrue(g.boss_spawned)
        self.assertEqual(seen, set(self.cfg["enemies"]))


if __name__ == "__main__":
    unittest.main()
