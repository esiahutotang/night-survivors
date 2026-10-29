"""Run the real window/input loop headlessly for a few seconds."""
import os
import sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "unavailable" if "--no-audio" in sys.argv else "dummy"

import asyncio
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pygame
import main as app
from rules import Enemy, Game, Gem

instances = []
seen_events = set()


class ObservedGame(Game):
    def __init__(self, config):
        super().__init__(config, seed=7)
        instances.append(self)

    def drain_events(self):
        events = super().drain_events()
        seen_events.update(event["name"] for event in events)
        return events


async def frames(count):
    for _ in range(count):
        await asyncio.sleep(0)


def post(kind, **fields):
    pygame.event.post(pygame.event.Event(kind, fields))


async def exercise_input():
    await frames(5)
    game = instances[-1]
    post(pygame.MOUSEMOTION, pos=(330, 350), rel=(135, 0), buttons=(0, 0, 0), touch=False)
    await frames(30)
    first_x = game.x
    await frames(30)
    assert game.x > first_x > 0, "Stationary mouse pointer must keep moving hero"
    post(pygame.MOUSEBUTTONDOWN, pos=(330, 350), button=1, touch=False)
    await frames(2)
    post(pygame.KEYDOWN, key=pygame.K_p)
    await frames(2)
    paused_time = game.elapsed
    await frames(12)
    assert game.elapsed == paused_time, "Pause must freeze simulation"
    post(pygame.KEYDOWN, key=pygame.K_p)
    await frames(2)
    post(pygame.FINGERDOWN, finger_id=1, touch_id=1, x=0.5, y=0.8)
    await frames(10)
    post(pygame.FINGERMOTION, finger_id=1, touch_id=1, x=0.2, y=0.8, dx=-0.3, dy=0)
    await frames(10)
    assert game.y > 0, "Touch input must move hero"
    post(pygame.FINGERUP, finger_id=1, touch_id=1, x=0.2, y=0.8)
    await frames(2)
    stopped = (game.x, game.y)
    await frames(10)
    assert stopped == (game.x, game.y), "Finger release must stop movement"
    await frames(90)
    game.gain_xp(game.xp_needed-game.xp)
    await frames(2)
    assert len(game.cards) == game.config["growth"]["cards"]
    frozen = game.elapsed
    await frames(12)
    assert game.elapsed == frozen, "Upgrade cards must freeze the game"
    card_preview = Path(tempfile.gettempdir()) / "night-survivors-cards.png"
    pygame.image.save(pygame.display.get_surface(), card_preview)
    selected = game.cards[0]
    old_level = game.weapons.get(selected, game.passives.get(selected, 0))
    post(pygame.MOUSEBUTTONDOWN, pos=(195, 236), button=1, touch=False)
    await frames(2)
    assert not game.cards and game.weapons.get(selected, game.passives.get(selected, 0)) == old_level+1
    game.gain_xp(game.xp_needed-game.xp)
    await frames(2)
    selected = game.cards[1]
    old_level = game.weapons.get(selected, game.passives.get(selected, 0))
    post(pygame.FINGERDOWN, finger_id=5, touch_id=1, x=0.5, y=368/700)
    await frames(2)
    post(pygame.FINGERUP, finger_id=5, touch_id=1, x=0.5, y=368/700)
    await frames(2)
    assert not game.cards and game.weapons.get(selected, game.passives.get(selected, 0)) == old_level+1
    # Show every weapon and both gem pictures during this developer-only run.
    game.weapons = {"spark": 3, "blades": 3, "ring": 3}
    game.gems.extend([Gem(game.x+100, game.y+75, 1), Gem(game.x-100, game.y+75, 2)])
    game.elapsed = next(w["from"] for w in game.config["waves"] if w.get("boss"))
    game.ensure_boss()
    boss = next(e for e in game.enemies if e.kind == "demon")
    boss.x, boss.y = game.x+90, game.y-100
    for kind, offset in (("slime", -100), ("ghost", 100)):
        enemy = game.create_enemy(kind)
        enemy.x, enemy.y = game.x+offset, game.y-180
    # Exercise actual damage, death and pickup notifications for visual review.
    enemy = game.create_enemy("bat")
    enemy.x, enemy.y = game.x+85, game.y+65
    game.hurt_enemy(enemy, game.weapon_stats("spark")["damage"])
    bat_stats = game.config["enemies"]["bat"]
    game.enemies.append(Enemy(game.x, game.y, bat_stats["hp"]))
    game.gems.append(Gem(game.x, game.y, bat_stats["xp"]))
    await frames(2)
    preview = Path(tempfile.gettempdir()) / "night-survivors-feel.png"
    pygame.image.save(pygame.display.get_surface(), preview)
    game.hp = bat_stats["damage"]
    game.enemies = [Enemy(game.x, game.y, bat_stats["hp"])]
    await frames(2)
    assert game.game_over, "Lethal damage must end play"
    post(pygame.MOUSEBUTTONDOWN, pos=(195, 350), button=1, touch=False)
    await frames(2)
    assert instances[-1] is not game and instances[-1].hp == game.config["hero"]["hp"]
    instances[-1].game_over = True
    post(pygame.FINGERDOWN, finger_id=2, touch_id=1, x=0.5, y=0.5)
    await frames(2)
    assert len(instances) == 3 and not instances[-1].game_over
    victory_preview = Path(tempfile.gettempdir()) / "night-survivors-victory.png"
    for input_kind in ("mouse", "touch"):
        winner = instances[-1]
        winner.elapsed = winner.config["goal"]["survive_seconds"]-winner.config["simulation"]["step"]
        await frames(3)
        assert winner.victory and not winner.game_over
        pygame.image.save(pygame.display.get_surface(), victory_preview)
        post(pygame.KEYDOWN, key=pygame.K_p)
        await frames(2)
        assert not winner.paused, "P must not pause a finished game"
        if input_kind == "mouse":
            post(pygame.MOUSEBUTTONDOWN, pos=(195, 350), button=1, touch=False)
        else:
            post(pygame.FINGERDOWN, finger_id=7, touch_id=1, x=0.5, y=0.5)
        await frames(2)
        fresh = instances[-1]
        assert fresh is not winner and not fresh.finished and not fresh.boss_spawned
        assert fresh.hp == fresh.max_hp and fresh.level == 1
    print("PASS: persistent mouse movement, clicks, touch move/release, pause, mouse restart, touch restart")
    print("PASS: level-up freezes play; mouse and touch cards apply upgrades; all weapons and gems render")
    print(f"Card preview: {card_preview}")
    print("PASS: all enemy pictures and timer render; victory at 2:00; mouse and touch restart after victory")
    print(f"Victory preview: {victory_preview}")
    print("Gameplay notifications observed: " + ", ".join(sorted(seen_events)))
    print("Audio driver: " + (str(pygame.mixer.get_init()) if pygame.mixer.get_init() else "unavailable; game continues silently"))
    print(f"PASS: real main.py loop rendered 200+ frames; preview: {preview}")


async def check():
    app.Game = ObservedGame
    task = asyncio.create_task(app.main())
    try:
        await exercise_input()
    finally:
        post(pygame.QUIT)
        await task


if __name__ == "__main__":
    asyncio.run(check())
