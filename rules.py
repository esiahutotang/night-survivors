"""Waves rules. Each update advances exactly one fixed simulation step.
This module deliberately has no pygame dependency.
"""
import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path


def load_config():
    return json.loads((Path(__file__).parent / "data" / "game.json").read_text(encoding="utf-8"))


@dataclass(eq=False)
class Enemy:
    x: float
    y: float
    hp: float
    contact_cooldown: float = 0
    blade_cooldowns: dict = field(default_factory=dict)
    kind: str = "bat"


@dataclass
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    lifetime: float
    damage: float


@dataclass(eq=False)
class Gem:
    x: float
    y: float
    xp: int
    attracted: bool = False


class Game:
    def __init__(self, config=None, seed=None, card_seed=None):
        self.config = config if config is not None else load_config()
        self.rng = random.Random(seed)
        self.card_rng = self.rng if card_seed is None else random.Random(card_seed)
        self.x = self.y = self.elapsed = 0.0
        self.hp = self.config["hero"]["hp"]
        self.enemies = []
        self.sparks = []
        self.kills = 0
        self.game_over = False
        self.victory = False
        self.boss_spawned = False
        self.paused = False
        self.spawn_clock = 0.0
        self.attack_clock = 0.0
        self.ring_clock = 0.0
        self.gems = []
        self.level = 1
        self.xp = 0
        self.weapons = {"spark": 1}
        self.passives = {"boots": 0, "heart": 0, "magnet": 0}
        self.cards = []
        self.events = []

    def drain_events(self):
        """Hand rule notifications to the display once, including across fixed steps."""
        events, self.events = self.events, []
        return events

    def notify(self, name, **details):
        self.events.append({"name": name, **details})

    @property
    def finished(self):
        return self.game_over or self.victory

    @property
    def current_wave(self):
        return next(wave for wave in reversed(self.config["waves"])
                    if self.elapsed + 1e-9 >= wave["from"])

    def enemy_radius(self, enemy):
        return self.config["enemies"][enemy.kind]["radius"]

    def circle_position(self):
        angle = self.rng.uniform(0, math.tau)
        radius = self.config["spawn"]["radius"]
        return self.x + math.cos(angle)*radius, self.y + math.sin(angle)*radius

    def create_enemy(self, kind):
        x, y = self.circle_position()
        enemy = Enemy(x, y, self.config["enemies"][kind]["hp"], kind=kind)
        self.enemies.append(enemy)
        return enemy

    def ensure_boss(self):
        due = any(wave.get("boss") and self.elapsed + 1e-9 >= wave["from"]
                  for wave in self.config["waves"])
        if self.boss_spawned or not due:
            return 0
        # Make room at the hard cap so the scheduled boss is never delayed.
        if len(self.enemies) >= self.config["spawn"]["cap"]:
            normal = next((enemy for enemy in self.enemies if enemy.kind != "demon"), None)
            if normal is None:
                return 0
            self.enemies.remove(normal)
        self.create_enemy("demon")
        self.boss_spawned = True
        return 1

    @property
    def max_hp(self):
        return self.config["hero"]["hp"] + self.passives["heart"] * self.config["passives"]["heart_hp"]

    @property
    def speed(self):
        return self.config["hero"]["speed"] * (1 + self.passives["boots"] * self.config["passives"]["boots_speed_fraction"])

    @property
    def magnet_radius(self):
        return self.config["hero"]["magnet_radius"] + self.passives["magnet"] * self.config["passives"]["magnet_radius"]

    @property
    def xp_needed(self):
        return self.config["growth"]["initial_xp"] + (self.level-1) * self.config["growth"]["xp_per_level"]

    def weapon_stats(self, name, level=None):
        """Combat stats, or a read-only preview at an explicit level."""
        stats = self.config["weapons"][name].copy()
        extra = (self.weapons.get(name, 1) if level is None else level) - 1
        stats["damage"] += extra * stats["damage_per_level"]
        if name == "spark":
            stats["interval"] -= extra * stats["interval_per_level"]
            stats["count"] += sum(level <= extra+1 for level in stats["extra_spark_levels"])
        elif name == "blades":
            stats["count"] += sum(level <= extra+1 for level in stats["extra_blade_levels"])
        else:
            stats["radius"] += extra * stats["radius_per_level"]
        return stats

    def blade_positions(self):
        if "blades" not in self.weapons:
            return []
        stats = self.weapon_stats("blades")
        angle = self.elapsed / stats["period"] * math.tau
        return [(self.x + math.cos(angle+i*math.tau/stats["count"]) * stats["orbit_radius"],
                 self.y + math.sin(angle+i*math.tau/stats["count"]) * stats["orbit_radius"])
                for i in range(stats["count"])]

    def gain_xp(self, amount):
        self.xp += amount
        self._check_level_up()

    def _check_level_up(self):
        if self.cards or self.finished or self.xp < self.xp_needed:
            return
        self.xp -= self.xp_needed
        self.level += 1
        self.notify("level_up")
        cfg = self.config
        pool = [name for name in ("spark", "blades", "ring")
                if (name in self.weapons and self.weapons[name] < cfg["weapons"]["max_level"])
                or (name not in self.weapons and len(self.weapons) < cfg["weapons"]["max_owned"])]
        pool += [name for name, level in self.passives.items() if level < cfg["passives"]["max_level"]]
        count = cfg["growth"]["cards"]
        if not pool:
            self.cards = ["heal"] * count
        else:
            # Offer distinct choices when possible. Near the cap, repeat only eligible choices.
            self.cards = self.card_rng.sample(pool, min(count, len(pool)))
            while len(self.cards) < count:
                self.cards.append(self.card_rng.choice(pool))

    def choose_card(self, index):
        if self.finished or not 0 <= index < len(self.cards):
            return False
        name = self.cards[index]
        if name in ("spark", "blades", "ring"):
            self.weapons[name] = self.weapons.get(name, 0) + 1
        elif name in self.passives:
            self.passives[name] += 1
            if name == "heart":
                self.hp = min(self.max_hp, self.hp + self.config["passives"]["heart_heal"])
        else:
            self.hp = min(self.max_hp, self.hp + self.config["growth"]["fallback_heal"])
        self.cards = []
        self._check_level_up()  # Preserve surplus XP and handle one choice per level.
        return True

    def hurt_enemy(self, bat, damage):
        self.notify("hit", x=bat.x, y=bat.y, amount=damage)
        bat.hp -= damage
        if bat.hp <= 0:
            self.notify("death", x=bat.x, y=bat.y, kind=bat.kind)
            self.enemies.remove(bat)
            self.kills += 1
            xp = self.config["enemies"][bat.kind]["xp"]
            if xp:
                self.gems.append(Gem(bat.x, bat.y, xp))

    def spawn_enemies(self, extra_spawned=0):
        cfg = self.config
        count = min(cfg["spawn"]["per_second"] - extra_spawned,
                    self.current_wave["minimum"] - len(self.enemies),
                    cfg["spawn"]["cap"] - len(self.enemies))
        for _ in range(max(0, count)):
            self.create_enemy(self.rng.choice(self.current_wave["types"]))

    def update(self, direction=None):
        """direction is the pointer's pixel offset from the hero, or None."""
        if self.finished or self.paused or self.cards:
            return
        cfg = self.config
        dt = cfg["simulation"]["step"]
        self.elapsed += dt
        if direction is not None:
            dx, dy = direction
            distance = math.hypot(dx, dy)
            stop = cfg["controls"]["stop_distance"]
            if distance > stop:
                travel = min(self.speed * dt, distance - stop)
                self.x += dx / distance * travel
                self.y += dy / distance * travel

        self.enemies = [b for b in self.enemies if b.kind == "demon" or
                       math.hypot(b.x - self.x, b.y - self.y) <= cfg["spawn"]["remove_distance"]]
        for enemy in self.enemies:
            if (enemy.kind == "demon" and math.hypot(enemy.x-self.x, enemy.y-self.y) >
                    cfg["spawn"]["boss_return_distance"]):
                enemy.x, enemy.y = self.circle_position()
        boss_count = self.ensure_boss()
        self.spawn_clock += dt
        if self.spawn_clock + 1e-9 >= cfg["spawn"]["interval"]:
            self.spawn_clock -= cfg["spawn"]["interval"]
            self.spawn_enemies(extra_spawned=boss_count)

        for bat in self.enemies:
            bat_cfg = cfg["enemies"][bat.kind]
            dx, dy = self.x - bat.x, self.y - bat.y
            distance = math.hypot(dx, dy)
            if distance:
                travel = min(bat_cfg["speed"] * dt, distance)
                bat.x += dx / distance * travel
                bat.y += dy / distance * travel
            bat.contact_cooldown = max(0, bat.contact_cooldown - dt)
            for blade in bat.blade_cooldowns:
                bat.blade_cooldowns[blade] = max(0, bat.blade_cooldowns[blade] - dt)
            if (math.hypot(bat.x - self.x, bat.y - self.y) <=
                    cfg["hero"]["radius"] + bat_cfg["radius"] and
                    bat.contact_cooldown <= 1e-9):
                self.hp = max(0, self.hp - bat_cfg["damage"])
                self.notify("hurt", x=self.x, y=self.y, amount=bat_cfg["damage"])
                bat.contact_cooldown = cfg["contact_interval"]
                if self.hp == 0:
                    self.game_over = True
                    self.notify("game_over")
                    return

        spark_cfg = self.weapon_stats("spark")
        self.attack_clock = max(0, self.attack_clock - dt)
        if self.enemies and self.attack_clock <= 1e-9:
            targets = sorted(self.enemies, key=lambda b: (b.x-self.x)**2 + (b.y-self.y)**2)
            for i in range(spark_cfg["count"]):
                target = targets[i % len(targets)]
                dx, dy = target.x - self.x, target.y - self.y
                distance = math.hypot(dx, dy)
                if not distance:
                    dx, dy, distance = 1, 0, 1
                self.sparks.append(Spark(self.x, self.y, dx / distance * spark_cfg["speed"],
                                         dy / distance * spark_cfg["speed"], spark_cfg["lifetime"], spark_cfg["damage"]))
            self.attack_clock = spark_cfg["interval"]

        for spark in self.sparks[:]:
            old_x, old_y = spark.x, spark.y
            spark.x += spark.vx * dt
            spark.y += spark.vy * dt
            spark.lifetime -= dt
            # Test the whole travelled segment so fast sparks cannot skip a Enemy.
            sx, sy = spark.x - old_x, spark.y - old_y
            length_sq = sx*sx + sy*sy
            hit = None
            best_t = float("inf")
            for bat in self.enemies:
                t = max(0, min(1, ((bat.x-old_x)*sx + (bat.y-old_y)*sy) / length_sq)) if length_sq else 0
                if (math.hypot(old_x+t*sx-bat.x, old_y+t*sy-bat.y) <=
                        spark_cfg["radius"] + self.enemy_radius(bat) and t < best_t):
                    hit, best_t = bat, t
            if hit:
                self.hurt_enemy(hit, spark.damage)
            if hit or spark.lifetime <= 0:
                self.sparks.remove(spark)

        if "blades" in self.weapons:
            stats = self.weapon_stats("blades")
            for index, (x, y) in enumerate(self.blade_positions()):
                for bat in self.enemies[:]:
                    if (math.hypot(bat.x-x, bat.y-y) <= stats["hit_radius"] + self.enemy_radius(bat)
                            and bat.blade_cooldowns.get(index, 0) <= 1e-9):
                        bat.blade_cooldowns[index] = stats["hit_interval"]
                        self.hurt_enemy(bat, stats["damage"])

        if "ring" in self.weapons:
            stats = self.weapon_stats("ring")
            self.ring_clock = max(0, self.ring_clock - dt)
            if self.ring_clock <= 1e-9:
                for bat in self.enemies[:]:
                    if math.hypot(bat.x-self.x, bat.y-self.y) <= stats["radius"]:
                        self.hurt_enemy(bat, stats["damage"])
                self.ring_clock = stats["interval"]

        collected_xp = 0
        for gem in self.gems[:]:
            dx, dy = self.x-gem.x, self.y-gem.y
            distance = math.hypot(dx, dy)
            if distance <= self.magnet_radius:
                gem.attracted = True
            if gem.attracted:
                travel = cfg["growth"]["gem_speed"] * dt
                if distance <= travel + cfg["hero"]["radius"]:
                    self.gems.remove(gem)
                    self.notify("gem")
                    collected_xp += gem.xp
                elif distance:
                    gem.x += dx/distance * travel
                    gem.y += dy/distance * travel
        if collected_xp:
            self.gain_xp(collected_xp)
        if self.elapsed + 1e-9 >= cfg["goal"]["survive_seconds"]:
            self.elapsed = cfg["goal"]["survive_seconds"]
            self.victory = True
            self.cards = []
            self.notify("victory")
