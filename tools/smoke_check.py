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
menus = []
record_stores = []


class ObservedMenu(app.MenuUI):
    def __init__(self, *args):
        super().__init__(*args)
        menus.append(self)


class ObservedGame(Game):
    def __init__(self, config, **kwargs):
        if not kwargs:
            kwargs['seed'] = 7
        super().__init__(config, **kwargs)
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
    menu = menus[-1]
    title_game = instances[-1]
    await frames(10)
    assert title_game.elapsed == 0 and not title_game.enemies, "Title must not start a game"
    post(pygame.KEYDOWN, key=pygame.K_p)
    post(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=1, touch=False)
    await frames(2)
    assert menu.page == "title" and not title_game.paused
    preview_dir = Path(__file__).resolve().parents[1] / "build" / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    pygame.image.save(pygame.display.get_surface(), preview_dir / "title.png")
    post(pygame.MOUSEBUTTONDOWN, pos=menu.other_button.center, button=1, touch=False)
    await frames(2)
    assert menu.page == "skins"
    for index in range(len(menu.skins)):
        post(pygame.MOUSEBUTTONDOWN, pos=menu.skin_cards[index].center, button=1, touch=False)
        await frames(2)
        assert menu.selected == index
    pygame.image.save(pygame.display.get_surface(), preview_dir / "skins.png")
    post(pygame.FINGERDOWN, finger_id=9, touch_id=1, x=menu.skin_cards[1].centerx/390, y=menu.skin_cards[1].centery/700)
    await frames(2)
    post(pygame.FINGERUP, finger_id=9, touch_id=1, x=0.5, y=0.5)
    await frames(2)
    assert menu.selected == 1 and title_game.elapsed == 0
    post(pygame.MOUSEBUTTONDOWN, pos=menu.other_button.center, button=1, touch=False)
    await frames(2)
    assert menu.page == "title" and menu.selected == 1
    pygame.image.save(pygame.display.get_surface(), preview_dir / "title-mage.png")
    post(pygame.FINGERDOWN, finger_id=9, touch_id=1, x=menu.start_button.centerx/390, y=menu.start_button.centery/700)
    await frames(2)
    post(pygame.FINGERUP, finger_id=9, touch_id=1, x=0.5, y=0.5)
    await frames(2)
    game = instances[-1]
    assert menu.page == "playing" and game is not title_game
    assert (game.x, game.y) == (0, 0), "Start touch must not leak into movement"
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
    pygame.image.save(pygame.display.get_surface(), preview_dir / "game-over.png")
    post(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=1, touch=False)
    await frames(2)
    assert instances[-1] is game, "End screen background must not restart"
    post(pygame.MOUSEBUTTONDOWN, pos=menu.restart_button.center, button=1, touch=False)
    await frames(2)
    assert instances[-1] is not game and instances[-1].hp == game.config["hero"]["hp"]
    instances[-1].game_over = True
    post(pygame.FINGERDOWN, finger_id=2, touch_id=1, x=0.5, y=menu.title_button.centery/700)
    await frames(2)
    assert menu.page == "title" and menu.selected == 1
    post(pygame.MOUSEBUTTONDOWN, pos=menu.start_button.center, button=1, touch=False)
    await frames(2)
    assert len(instances) == 4 and not instances[-1].game_over
    victory_preview = Path(tempfile.gettempdir()) / "night-survivors-victory.png"
    for input_kind in ("mouse", "touch"):
        winner = instances[-1]
        winner.elapsed = winner.config["goal"]["survive_seconds"]-winner.config["simulation"]["step"]
        await frames(3)
        assert winner.victory and not winner.game_over
        pygame.image.save(pygame.display.get_surface(), victory_preview)
        pygame.image.save(pygame.display.get_surface(), preview_dir / "victory.png")
        post(pygame.KEYDOWN, key=pygame.K_p)
        await frames(2)
        assert not winner.paused, "P must not pause a finished game"
        if input_kind == "mouse":
            post(pygame.MOUSEBUTTONDOWN, pos=menu.title_button.center, button=1, touch=False)
            await frames(2)
            assert menu.page == "title" and menu.selected == 1
            post(pygame.MOUSEBUTTONDOWN, pos=menu.start_button.center, button=1, touch=False)
        else:
            post(pygame.FINGERDOWN, finger_id=7, touch_id=1, x=0.5, y=menu.restart_button.centery/700)
        await frames(2)
        fresh = instances[-1]
        assert fresh is not winner and not fresh.finished and not fresh.boss_spawned
        assert fresh.hp == fresh.max_hp and fresh.level == 1
        assert menu.selected == 1
    fresh.victory = True
    await frames(2)
    post(pygame.MOUSEBUTTONDOWN, pos=menu.title_button.center, button=1, touch=False)
    await frames(2)
    post(pygame.FINGERDOWN, finger_id=12, touch_id=1, x=menu.daily_button.centerx/390, y=menu.daily_button.centery/700)
    await frames(2)
    assert menu.mode == 'daily' and menu.page == 'title'
    pygame.image.save(pygame.display.get_surface(), preview_dir / 'daily-title.png')
    post(pygame.MOUSEBUTTONDOWN, pos=menu.start_button.center, button=1, touch=False)
    await frames(2)
    daily = instances[-1]
    assert daily.card_rng is not daily.rng and menu.selected == 1
    daily.gain_xp(daily.xp_needed)
    cards = daily.cards[:]
    daily.cards = []
    daily.elapsed = daily.config['goal']['survive_seconds']
    daily.victory = True
    await frames(3)
    pygame.image.save(pygame.display.get_surface(), preview_dir / 'daily-result.png')
    post(pygame.FINGERDOWN, finger_id=13, touch_id=1, x=0.5, y=menu.restart_button.centery/700)
    await frames(2)
    retry = instances[-1]
    assert retry is not daily and retry.config == daily.config
    retry.gain_xp(retry.xp_needed)
    assert retry.cards == cards, 'Daily retry must preserve challenge and card seeds'
    retry.cards = []
    retry.game_over = True
    await frames(2)
    post(pygame.MOUSEBUTTONDOWN, pos=menu.title_button.center, button=1, touch=False)
    await frames(2)
    post(pygame.MOUSEBUTTONDOWN, pos=menu.records_button.center, button=1, touch=False)
    await frames(2)
    assert menu.page == 'records'
    pygame.image.save(pygame.display.get_surface(), preview_dir / 'records.png')
    entries = record_stores[-1].entries
    assert any(k.startswith('normal:') for k in entries)
    assert any(k.startswith('daily:') for k in entries)
    assert any(k.startswith('best:') for k in entries)
    post(pygame.FINGERDOWN, finger_id=14, touch_id=1, x=0.5, y=menu.back_button.centery/700)
    await frames(2)
    assert menu.page == 'title' and menu.selected == 1
    post(pygame.MOUSEBUTTONDOWN, pos=menu.normal_button.center, button=1, touch=False)
    await frames(2)
    post(pygame.MOUSEBUTTONDOWN, pos=menu.start_button.center, button=1, touch=False)
    await frames(2)
    assert instances[-1].config['hero']['hp'] == app.load_config()['hero']['hp']
    assert instances[-1].card_rng is instances[-1].rng
    print('PASS: daily mode, retry seeds, normal-mode restoration, local records page and skin retention')
    print("PASS: title stays idle; all 3 skins selectable; mouse/touch start, return to title and restart; skin retained")
    print(f"Menu previews: {preview_dir}")
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
    app.MenuUI = ObservedMenu
    from records import Records
    temporary = tempfile.TemporaryDirectory()
    def record_factory():
        store = Records(path=Path(temporary.name)/'records.json')
        record_stores.append(store)
        return store
    app.Records = record_factory
    task = asyncio.create_task(app.main())
    try:
        await exercise_input()
    finally:
        post(pygame.QUIT)
        await task
        temporary.cleanup()


if __name__ == "__main__":
    asyncio.run(check())
