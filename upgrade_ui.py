"""Upgrade presentation only; previewing never changes the game or its RNG."""
import pygame

NAMES = {"spark": "火花魔杖", "blades": "回旋利刃", "ring": "神圣光环",
         "boots": "疾风靴", "heart": "强健之心", "magnet": "磁铁", "heal": "治疗"}
COLORS = {"spark": (255, 210, 111), "blades": (128, 208, 255),
          "ring": (237, 213, 128), "boots": (135, 226, 186),
          "heart": (255, 136, 160), "magnet": (188, 159, 255),
          "heal": (135, 226, 186)}


def card_details(game, name):
    """Return heading, category and two compact lines from live rule values."""
    def change(label, before, after, suffix=""):
        return f"{label} {before:g} → {after:g}{suffix}"

    if name in game.config["weapons"]:
        level = game.weapons.get(name, 0)
        after = game.weapon_stats(name, level + 1)
        before = game.weapon_stats(name, level) if level else None

        def stat(label, key, suffix=""):
            if before is None:
                return f"{label} {after[key]:g}{suffix}"
            return change(label, before[key], after[key], suffix)

        rows = [stat("伤害", "damage")]
        if name == "spark":
            rows[0] += "    " + stat("数量", "count")
            rows.append(stat("攻击间隔", "interval", " 秒"))
        elif name == "blades":
            rows[0] += "    " + stat("数量", "count")
            rows.append(f"环绕攻击 · 每 {after['hit_interval']:g} 秒可命中")
        else:
            rows.append(stat("范围", "radius", " 像素"))
        category = "武器强化" if level else "新武器 · 自动攻击"
    elif name == "heal":
        healed = min(game.max_hp, game.hp + game.config["growth"]["fallback_heal"])
        return NAMES[name], "即时治疗", [change("生命", game.hp, healed),
                                          f"实际恢复 {healed-game.hp:g} 点生命"]
    else:
        level = game.passives[name]
        cfg = game.config["passives"]
        category = "被动强化"
        if name == "boots":
            rows = [change("移速", game.speed,
                           game.speed + game.config["hero"]["speed"] * cfg["boots_speed_fraction"]),
                    f"每级增加基础移速的 {cfg['boots_speed_fraction']*100:g}%"]
        elif name == "magnet":
            rows = [change("拾取范围", game.magnet_radius,
                           game.magnet_radius + cfg["magnet_radius"], " 像素"),
                    "更远处的经验宝石自动飞向你"]
        else:
            maximum = game.max_hp + cfg["heart_hp"]
            healed = min(maximum, game.hp + cfg["heart_heal"])
            rows = [change("生命上限", game.max_hp, maximum),
                    change("当前生命", game.hp, healed)]
    return f"{NAMES[name]}  {level} → {level+1}级", category, rows


def make_icons():
    """Original 16px pixel art, cached at card and equipment sizes."""
    icons = {}
    for name, color in COLORS.items():
        icon = pygame.Surface((16, 16), pygame.SRCALPHA)
        dark, light = (41, 52, 75), (246, 250, 255)
        if name == "spark":
            pygame.draw.line(icon, (166, 116, 77), (4, 13), (10, 7), 3)
            pygame.draw.polygon(icon, color, [(10, 1), (11, 4), (14, 5), (11, 7), (10, 10), (8, 7), (5, 5), (8, 4)])
            pygame.draw.rect(icon, light, (9, 4, 2, 2))
        elif name == "blades":
            pygame.draw.polygon(icon, dark, [(3, 1), (14, 12), (12, 14), (1, 3)])
            pygame.draw.polygon(icon, color, [(11, 1), (14, 1), (14, 4), (6, 12), (4, 10)])
            pygame.draw.line(icon, light, (7, 9), (12, 4), 1)
            pygame.draw.line(icon, (232, 181, 99), (2, 8), (8, 14), 2)
            pygame.draw.line(icon, (166, 116, 77), (1, 14), (5, 10), 2)
        elif name == "ring":
            pygame.draw.circle(icon, color, (8, 8), 6, 3)
            pygame.draw.circle(icon, light, (8, 8), 4, 1)
            pygame.draw.rect(icon, light, (11, 2, 3, 3))
        elif name == "boots":
            pygame.draw.polygon(icon, color, [(5, 2), (11, 2), (10, 9), (14, 10), (14, 13), (3, 13), (3, 10), (5, 9)])
            pygame.draw.rect(icon, light, (6, 3, 4, 2))
            pygame.draw.line(icon, dark, (3, 14), (14, 14), 2)
            pygame.draw.line(icon, color, (1, 5), (3, 5), 1)
            pygame.draw.line(icon, color, (0, 8), (2, 8), 1)
        elif name == "heart":
            pygame.draw.polygon(icon, color, [(2, 3), (5, 2), (8, 5), (11, 2), (14, 3), (15, 7), (8, 14), (1, 7)])
            pygame.draw.rect(icon, light, (3, 4, 3, 2))
        elif name == "magnet":
            pygame.draw.rect(icon, color, (2, 2, 4, 9))
            pygame.draw.rect(icon, (255, 136, 160), (10, 2, 4, 9))
            pygame.draw.rect(icon, color, (4, 10, 8, 4))
            pygame.draw.rect(icon, light, (2, 2, 4, 3))
            pygame.draw.rect(icon, light, (10, 2, 4, 3))
        else:
            pygame.draw.rect(icon, color, (1, 1, 14, 14), border_radius=3)
            pygame.draw.rect(icon, light, (6, 3, 4, 10))
            pygame.draw.rect(icon, light, (3, 6, 10, 4))
        icons[name] = {size: pygame.transform.scale(icon, (size, size)) for size in (20, 40)}
    return icons


class UpgradeUI:
    def __init__(self, font_path):
        self.heading = pygame.font.Font(font_path, 20)
        self.detail = pygame.font.Font(font_path, 16)
        self.caption = pygame.font.Font(font_path, 14)
        self.icons = make_icons()

    def label(self, screen, message, position, font, color, max_width):
        # The bundled Chinese font has no arrow glyph. Draw arrows explicitly
        # so phones and desktops show the same comparison without system fonts.
        parts = [font.render(part, True, color) for part in message.split("→")]
        arrow_width = 16
        surface = pygame.Surface((sum(p.get_width() for p in parts)
                                  + arrow_width*(len(parts)-1), font.get_height()), pygame.SRCALPHA)
        x = 0
        for index, part in enumerate(parts):
            if index:
                y = surface.get_height()//2
                pygame.draw.line(surface, color, (x+2, y), (x+12, y), 2)
                pygame.draw.lines(surface, color, False, [(x+8, y-4), (x+12, y), (x+8, y+4)], 2)
                x += arrow_width
            surface.blit(part, (x, 0))
            x += part.get_width()
        # Keep config-driven numbers inside the card even with custom settings.
        if surface.get_width() > max_width:
            ratio = max_width / surface.get_width()
            surface = pygame.transform.smoothscale(surface, (max_width, max(1, round(surface.get_height()*ratio))))
        screen.blit(surface, position)

    def draw_cards(self, screen, game, rects):
        for name, rect in zip(game.cards, rects):
            accent = COLORS[name]
            pygame.draw.rect(screen, (25, 37, 57), rect, border_radius=12)
            pygame.draw.rect(screen, accent, rect, 2, border_radius=12)
            badge = pygame.Rect(rect.x+12, rect.y+10, 48, 48)
            pygame.draw.rect(screen, (37, 51, 74), badge, border_radius=8)
            screen.blit(self.icons[name][40], (badge.x+4, badge.y+4))
            heading, category, rows = card_details(game, name)
            self.label(screen, heading, (rect.x+72, rect.y+12), self.heading,
                       (238, 244, 255), rect.width-84)
            self.label(screen, category, (rect.x+72, rect.y+38), self.caption,
                       accent, rect.width-84)
            for index, row in enumerate(rows):
                self.label(screen, row, (rect.x+16, rect.y+66+index*22), self.detail,
                           (196, 212, 232), rect.width-32)

    def draw_equipment(self, screen, game, height):
        for items, y in ((game.weapons, height-82), (game.passives, height-54)):
            for index, (name, level) in enumerate((n, v) for n, v in items.items() if v):
                x = 16 + index * 120
                screen.blit(self.icons[name][20], (x, y))
                short = {"spark": "魔杖", "blades": "利刃", "ring": "光环",
                         "boots": "疾风靴", "heart": "生命", "magnet": "磁铁"}
                self.label(screen, f"{short[name]} {level}", (x+25, y+2),
                           self.caption, (222, 230, 244), 90)
