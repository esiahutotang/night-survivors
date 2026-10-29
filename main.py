"""Night Survivors — Sound and feel. Run with Python and pygame-ce."""
import asyncio
import math
import sys
from pathlib import Path
import pygame
from rules import Game, load_config
from upgrade_ui import UpgradeUI
from menu_ui import MenuUI
from challenges import challenge_day, daily_challenge, load_challenges, version_id, result_for, summary
from records import Records


class Feedback:
    """Cosmetic state only; it never changes the rules or their random generator."""
    def __init__(self, config, sprites):
        self.config = config["feel"]
        self.numbers = []
        self.flashes = []
        self.shake_left = 0.0
        self.sounds = {}
        self.channels = {}
        self.white_sprites = {}
        for kind in config["enemies"]:
            sprite = sprites[kind].copy()
            sprite.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_ADD)
            self.white_sprites[kind] = sprite
        if pygame.mixer.get_init():
            sound_dir = Path(__file__).resolve().parent / "sounds"
            names = list(config["audio"]["clips"])
            pygame.mixer.set_num_channels(len(names))
            for index, name in enumerate(names):
                path = next((sound_dir / f"{name}{suffix}" for suffix in (".ogg", ".wav")
                             if (sound_dir / f"{name}{suffix}").exists()), None)
                if path:
                    try:
                        self.sounds[name] = pygame.mixer.Sound(str(path))
                        self.channels[name] = pygame.mixer.Channel(index)
                    except pygame.error:
                        pass  # The game remains playable when audio is unavailable.

    def reset(self):
        self.numbers.clear()
        self.flashes.clear()
        self.shake_left = 0.0
        for channel in self.channels.values():
            channel.stop()

    def play(self, name):
        if name not in self.sounds:
            return
        if name in ("victory", "game_over"):
            for channel in self.channels.values():
                channel.stop()
        channel = self.channels[name]
        if not channel.get_busy():
            channel.play(self.sounds[name])

    def update(self, dt):
        self.shake_left = max(0, self.shake_left-dt)
        for number in self.numbers:
            number["age"] += dt
        for flash in self.flashes:
            flash["age"] += dt
        self.numbers = [n for n in self.numbers if n["age"] < self.config["number_lifetime"]]
        self.flashes = [f for f in self.flashes if f["age"] < self.config["flash_lifetime"]]

    def consume(self, events):
        for event in events:
            name = event["name"]
            if name in ("hit", "hurt"):
                self.numbers.append({**event, "age": 0.0})
                self.numbers = self.numbers[-self.config["max_numbers"]:]
            if name == "death":
                self.flashes.append({**event, "age": 0.0})
                self.flashes = self.flashes[-self.config["max_flashes"]:]
            elif name == "hurt":
                self.shake_left = self.config["shake_duration"]
            if name != "death":
                self.play(name)

    def shake_offset(self):
        cfg = self.config
        if not self.shake_left:
            return 0, 0
        progress = cfg["shake_duration"]-self.shake_left
        amplitude = cfg["shake_pixels"] * self.shake_left/cfg["shake_duration"]
        phase = math.tau * cfg["shake_frequency"] * progress
        return round(math.cos(phase)*amplitude), round(math.sin(phase*1.3)*amplitude)

    def draw(self, screen, origin, font):
        for flash in self.flashes:
            sprite = self.white_sprites[flash["kind"]].copy()
            sprite.set_alpha(round(255*(1-flash["age"]/self.config["flash_lifetime"])))
            position = (round(flash["x"]+origin[0]), round(flash["y"]+origin[1]))
            screen.blit(sprite, sprite.get_rect(center=position))
        for number in self.numbers:
            hurt = number["name"] == "hurt"
            label = f"{'-' if hurt else ''}{number['amount']:g}"
            color = (255, 113, 140) if hurt else (255, 247, 158)
            offset_x = self.config["hurt_number_offset_x" if hurt else "hit_number_offset_x"]
            position = (round(number["x"]+origin[0]+offset_x), round(number["y"]+origin[1]
                        - self.config["number_offset"]-number["age"]*self.config["number_rise_speed"]))
            alpha = round(255*(1-number["age"]/self.config["number_lifetime"]))
            outline = font.render(label, True, (12, 18, 30))
            outline.set_alpha(alpha)
            rect = outline.get_rect(center=position)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                screen.blit(outline, rect.move(dx, dy))
            surface = font.render(label, True, color)
            surface.set_alpha(alpha)
            screen.blit(surface, rect)


async def main():
    config = load_config()
    pygame.mixer.pre_init(config["audio"]["sample_rate"], -16, 1, 512)
    pygame.init()
    width, height = config["screen"]["width"], config["screen"]["height"]
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("暗夜幸存者")
    asset_dir = Path(__file__).resolve().parent / "assets"
    # Finished files only: Pillow and the asset builder stay outside the game.
    sprites = {path.stem: pygame.image.load(str(path)).convert_alpha()
               for path in sorted(asset_dir.glob("*.png"))}
    for skin in config["skins"]:
        name = skin["sprite"]
        sprites[name] = pygame.transform.scale(sprites[name], sprites["hero"].get_size())
    demon = sprites["demon"]
    scale = config["enemies"]["demon"]["draw_scale"]
    sprites["demon"] = pygame.transform.scale(demon, (round(demon.get_width()*scale), round(demon.get_height()*scale)))
    floor = sprites["floor"]
    floor_size = config["screen"]["floor_tile"]
    if floor.get_size() != (floor_size, floor_size):
        floor = pygame.transform.scale(floor, (floor_size, floor_size))
    clock = pygame.time.Clock()
    # Packaged Chinese font works on desktop and phones without system fonts.
    font_path = str(asset_dir / "ZCOOLKuaiLe-Regular.ttf")
    font = pygame.font.Font(font_path, 21)
    small = pygame.font.Font(font_path, 16)
    title = pygame.font.Font(font_path, 34)
    feedback = Feedback(config, sprites)
    base_config = config
    definitions = load_challenges()
    version = version_id(base_config, definitions)
    run_version = version
    records = Records()
    today = daily_challenge(base_config, definitions)
    mode = 'normal'
    run_day, run_preset = today['day'], 'normal'
    recorded = new_best = False
    game = Game(config)
    center = (width // 2, height // 2)
    pointer = None
    finger = None
    accumulator = 0.0
    running = True
    card_rects = [pygame.Rect(20, 180 + i*132, width-40, 112)
                  for i in range(config["growth"]["cards"])]
    upgrade_ui = UpgradeUI(font_path)
    menu = MenuUI(config, sprites, font_path)

    def choose_at(position):
        nonlocal pointer, finger, accumulator
        for index, rect in enumerate(card_rects):
            if rect.collidepoint(position):
                game.choose_card(index)
                pointer = None
                finger = None
                accumulator = 0.0
                break

    def text(message, position, color=(222, 230, 244), face=None, centered=False):
        surface = (face or font).render(message, True, color)
        rect = surface.get_rect(center=position) if centered else surface.get_rect(topleft=position)
        screen.blit(surface, rect)

    def restart():
        nonlocal game, config, accumulator, pointer, finger, today, mode, run_day, run_preset, recorded, new_best, run_version
        mode = menu.mode
        today = daily_challenge(base_config, definitions)
        run_day = today['day']
        run_preset = today['preset']['id'] if mode == 'daily' else 'normal'
        config = today['config'] if mode == 'daily' else base_config
        game = (Game(config, seed=today['seed'], card_seed=today['card_seed'], character=menu.character)
                if mode == 'daily' else Game(config, character=menu.character))
        run_version = version + ':' + menu.character
        recorded = new_best = False
        menu.page = "playing"
        feedback.reset()
        accumulator = 0.0
        pointer = None
        finger = None

    def menu_click(position):
        nonlocal pointer, finger, accumulator
        if menu.page == "playing" and not game.finished:
            return False
        action = menu.click(position, game.finished)
        if action == "start":
            restart()
        elif action == "title":
            menu.page = "title"
            feedback.reset()
        pointer = None
        finger = None
        accumulator = 0.0
        return True

    while running:
        frame_time = min(clock.tick(0 if sys.platform == "emscripten" else config["screen"]["fps"]) / 1000,
                         config["simulation"]["max_frame_time"])
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                  and not getattr(event, "touch", False) and menu_click(event.pos)):
                continue
            elif event.type == pygame.FINGERDOWN and menu_click((event.x * width, event.y * height)):
                continue
            elif menu.page != "playing":
                continue
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_p:
                if not game.finished and not game.cards:
                    game.paused = not game.paused
                    accumulator = 0.0
            elif event.type == pygame.MOUSEMOTION and not getattr(event, "touch", False):
                if finger is None:
                    pointer = event.pos
            elif event.type == pygame.MOUSEBUTTONDOWN and not getattr(event, "touch", False):
                if event.button == 1 and game.cards:
                    choose_at(event.pos)
                elif finger is None:
                    pointer = event.pos
            elif event.type == pygame.FINGERDOWN:
                if game.cards:
                    choose_at((event.x * width, event.y * height))
                elif finger is None:
                    finger = event.finger_id
                    pointer = (event.x * width, event.y * height)
            elif event.type == pygame.FINGERMOTION and event.finger_id == finger:
                pointer = (event.x * width, event.y * height)
            elif event.type == pygame.FINGERUP and event.finger_id == finger:
                finger = None
                pointer = None
            elif event.type == pygame.WINDOWFOCUSLOST:
                pointer = None
                finger = None

        if game.finished and not recorded:
            new_best = records.submit(result_for(game, mode, run_version, run_day, run_preset))
            recorded = True
        if menu.page != "playing":
            if challenge_day() != today['day']:
                today = daily_challenge(base_config, definitions)
            menu.draw(screen, today, records, version + ':' + menu.character)
            pygame.display.flip()
            await asyncio.sleep(0)
            continue

        if not game.paused and not game.finished and not game.cards:
            accumulator += frame_time
            dt = config["simulation"]["step"]
            while accumulator + 1e-9 >= dt:
                direction = None if pointer is None else (pointer[0]-center[0], pointer[1]-center[1])
                game.update(direction)
                accumulator -= dt
                if game.cards or game.finished:
                    accumulator = 0.0
                    break
        else:
            accumulator = 0.0

        feedback.update(0 if game.paused or game.cards else frame_time)
        feedback.consume(game.drain_events())
        shake_x, shake_y = feedback.shake_offset()
        draw_center = (center[0]+shake_x, center[1]+shake_y)
        tile = config["screen"]["floor_tile"]
        origin_x, origin_y = draw_center[0] - game.x, draw_center[1] - game.y
        start_x, start_y = math.floor(-origin_x / tile), math.floor(-origin_y / tile)
        for row in range(start_y, start_y + math.ceil(height / tile) + 1):
            for col in range(start_x, start_x + math.ceil(width / tile) + 1):
                screen.blit(floor, (round(origin_x + col*tile), round(origin_y + row*tile)))

        if "ring" in game.weapons:
            radius = game.weapon_stats("ring")["radius"]
            aura = pygame.Surface((radius*2+2, radius*2+2), pygame.SRCALPHA)
            pygame.draw.circle(aura, (255, 236, 136, 35), (radius+1, radius+1), radius)
            pygame.draw.circle(aura, (255, 236, 136, 180), (radius+1, radius+1), radius, 2)
            screen.blit(aura, (draw_center[0]-radius-1, draw_center[1]-radius-1))
        for gem in game.gems:
            sprite = sprites["coin" if gem.xp == 1 else "coin_stack"]
            screen.blit(sprite, sprite.get_rect(center=(round(gem.x+origin_x), round(gem.y+origin_y))))
        for bat in game.enemies:
            pos = (round(bat.x + origin_x), round(bat.y + origin_y))
            sprite = sprites[bat.kind]
            screen.blit(sprite, sprite.get_rect(center=pos))
        for spark in game.sparks:
            pygame.draw.circle(screen, (255, 224, 105), (round(spark.x+origin_x), round(spark.y+origin_y)), config["weapons"]["spark"]["radius"])
        hero_sprite = sprites[menu.sprite_name]
        screen.blit(hero_sprite, hero_sprite.get_rect(center=draw_center))
        for x, y in game.blade_positions():
            sprite = sprites["sword"]
            screen.blit(sprite, sprite.get_rect(center=(round(x+origin_x), round(y+origin_y))))
        feedback.draw(screen, (origin_x, origin_y), font)

        pygame.draw.rect(screen, (12, 18, 30), (0, 0, width, 102))
        text("每日挑战" if mode == 'daily' else "暗夜幸存者", (16, 12), (122, 232, 213))
        seconds = int(game.elapsed + 1e-9)
        goal = config["goal"]["survive_seconds"]
        text(f"{seconds//60}:{seconds%60:02d} / {goal//60}:{goal%60:02d}", (width-116, 14), face=small)
        pygame.draw.rect(screen, (67, 38, 53), (16, 43, width-32, 15), border_radius=5)
        pygame.draw.rect(screen, (235, 84, 111), (16, 43, round((width-32)*game.hp/game.max_hp), 15), border_radius=5)
        text(f"生命 {game.hp} / {game.max_hp}", (16, 64), face=small)
        text(f"击败 {game.kills}", (width-90, 64), face=small)
        pygame.draw.rect(screen, (30, 47, 76), (16, 85, width-120, 8), border_radius=3)
        pygame.draw.rect(screen, (74, 161, 255), (16, 85, round((width-120)*min(1, game.xp/game.xp_needed)), 8), border_radius=3)
        text(f"{game.level}级  {game.xp}/{game.xp_needed}", (width-96, 82), face=small)
        pygame.draw.rect(screen, (12, 18, 30), (0, height-94, width, 94))
        upgrade_ui.draw_equipment(screen, game, height)
        text("鼠标移动 / 按住屏幕行走 / P 暂停", (16, height-26), (147, 164, 187), small)

        if game.paused or game.finished or game.cards:
            veil = pygame.Surface((width, height), pygame.SRCALPHA)
            veil.fill((6, 10, 20, 215))
            screen.blit(veil, (0, 0))
            if game.cards:
                text("升级！", (width//2, 110), (122, 232, 213), title, True)
                text(f"达到 {game.level} 级，选择一项强化", (width//2, 146), centered=True)
                upgrade_ui.draw_cards(screen, game, card_rects)
                text("点击卡片，继续战斗", (width//2, 610), centered=True)
            elif game.finished:
                text("生存胜利" if game.victory else "游戏结束", (width//2, 180),
                     (122, 232, 213) if game.victory else (255, 138, 155), title, True)
                text(('每日挑战 · ' + run_day) if mode == 'daily' else '普通模式',
                     (width//2, 230), face=small, centered=True)
                if mode == 'daily':
                    text(today['preset']['name'], (width//2, 258), face=small, centered=True)
                text(summary(result_for(game, mode, run_version, run_day, run_preset)),
                     (width//2, 295), face=small, centered=True)
                text('刷新本机最佳！' if new_best else '本机最佳纪录', (width//2, 338),
                     (255, 216, 140), centered=True)
                text(summary(records.best(mode, run_version, run_day, run_preset)),
                     (width//2, 375), face=small, centered=True)
                menu.draw_end_buttons(screen)
                text('已保存到本机' if records.persistent else '存储不可用 · 纪录仅本次有效',
                     (width//2, 570), face=small, centered=True)
            else:
                text("已暂停", (width//2, height//2-55), (122, 232, 213), title, True)
                text("按 P 继续游戏", (width//2, height//2), centered=True)
        pygame.display.flip()
        await asyncio.sleep(0)
    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
