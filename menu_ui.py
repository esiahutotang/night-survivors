"""Title, skin selection and end-screen controls. Appearance never changes rules."""
import pygame
from challenges import summary


class MenuUI:
    def __init__(self, config, sprites, font_path):
        self.width = config["screen"]["width"]
        self.height = config["screen"]["height"]
        self.skins = config["skins"]
        self.selected = 0
        self.page = "title"
        self.mode = "normal"
        self.font = pygame.font.Font(font_path, 23)
        self.small = pygame.font.Font(font_path, 16)
        self.heading = pygame.font.Font(font_path, 38)
        self.previews = [pygame.transform.scale(sprites[s["sprite"]], (110, 110)) for s in self.skins]
        self.thumbs = [pygame.transform.scale(sprites[s["sprite"]], (72, 72)) for s in self.skins]
        self.start_button = pygame.Rect(45, 452, self.width-90, 58)
        self.other_button = pygame.Rect(45, 526, self.width-90, 54)
        self.restart_button = pygame.Rect(45, 408, self.width-90, 54)
        self.title_button = pygame.Rect(45, 478, self.width-90, 54)
        self.skin_cards = [pygame.Rect(30+i*112, 236, 106, 164) for i in range(len(self.skins))]
        self.normal_button = pygame.Rect(30, 174, 160, 38)
        self.daily_button = pygame.Rect(200, 174, 160, 38)
        self.records_button = pygame.Rect(45, 592, self.width-90, 42)
        self.back_button = pygame.Rect(45, 592, self.width-90, 48)

    @property
    def sprite_name(self):
        return self.skins[self.selected]["sprite"]

    def click(self, position, finished=False):
        if self.page != "playing":
            if self.page == "records":
                if self.back_button.collidepoint(position):
                    self.page = "title"
                return None
            if self.page == "title":
                if self.normal_button.collidepoint(position):
                    self.mode = "normal"
                elif self.daily_button.collidepoint(position):
                    self.mode = "daily"
                elif self.records_button.collidepoint(position):
                    self.page = "records"
                if self.normal_button.collidepoint(position) or self.daily_button.collidepoint(position) or self.page == "records":
                    return None
            if self.start_button.collidepoint(position):
                return "start"
            if self.other_button.collidepoint(position):
                self.page = "title" if self.page == "skins" else "skins"
            elif self.page == "skins":
                for index, rect in enumerate(self.skin_cards):
                    if rect.collidepoint(position):
                        self.selected = index
            return None
        if finished:
            if self.restart_button.collidepoint(position):
                return "start"
            if self.title_button.collidepoint(position):
                return "title"
        return None

    def label(self, screen, message, center, color=(228, 237, 247), font=None):
        surface = (font or self.font).render(message, True, color)
        screen.blit(surface, surface.get_rect(center=center))

    def button(self, screen, rect, message, primary=False):
        pygame.draw.rect(screen, (55, 191, 168) if primary else (27, 43, 62), rect, border_radius=12)
        pygame.draw.rect(screen, (122, 232, 213) if primary else (66, 94, 116), rect, 2, border_radius=12)
        self.label(screen, message, rect.center, (10, 25, 33) if primary else (222, 234, 245))

    def draw(self, screen, today, records, version):
        screen.fill((10, 17, 29))
        for row in range(0, self.height, 32):
            for col in range(0, self.width, 32):
                pygame.draw.circle(screen, (24, 37, 51), (col, row), 1)
        self.label(screen, "暗夜幸存者", (self.width//2, 104), (122, 232, 213), self.heading)
        self.label(screen, "选择你的英雄，迎战暗夜", (self.width//2, 152), font=self.small)
        if self.page == "records":
            self.draw_records(screen, today, records, version)
            return
        if self.page == "skins":
            self.label(screen, "皮肤选择", (self.width//2, 204))
            for index, rect in enumerate(self.skin_cards):
                chosen = index == self.selected
                pygame.draw.rect(screen, (27, 54, 63) if chosen else (21, 32, 49), rect, border_radius=10)
                pygame.draw.rect(screen, (122, 232, 213) if chosen else (50, 68, 88), rect, 2, border_radius=10)
                sprite = self.thumbs[index]
                screen.blit(sprite, sprite.get_rect(center=(rect.centerx, rect.y+61)))
                self.label(screen, self.skins[index]["name"], (rect.centerx, rect.y+115), font=self.small)
                self.label(screen, "已选择" if chosen else "点击选择", (rect.centerx, rect.y+143),
                           (122, 232, 213) if chosen else (138, 157, 180), self.small)
        else:
            pygame.draw.circle(screen, (21, 42, 53), (self.width//2, 286), 70)
            pygame.draw.circle(screen, (58, 104, 111), (self.width//2, 286), 70, 2)
            sprite = self.previews[self.selected]
            screen.blit(sprite, sprite.get_rect(center=(self.width//2, 280)))
            self.label(screen, self.skins[self.selected]["name"], (self.width//2, 380))
            self.button(screen, self.normal_button, "普通模式", self.mode == "normal")
            self.button(screen, self.daily_button, "每日挑战", self.mode == "daily")
        if self.page == "title" and self.mode == "daily":
            self.label(screen, today['preset']['name'] + ' · ' + today['day'], (self.width//2, 412), (255, 216, 140), self.small)
            self.label(screen, today['preset']['description'], (self.width//2, 438), font=self.small)
        else:
            self.label(screen, "皮肤仅改变外观，能力完全相同", (self.width//2, 430), (150, 170, 191), self.small)
        self.button(screen, self.start_button, "开始每日挑战" if self.mode == "daily" else "开始游戏", True)
        self.button(screen, self.other_button, "返回标题" if self.page == "skins" else "皮肤选择")
        if self.page == "title":
            self.button(screen, self.records_button, "本机历史记录")
        self.label(screen, "按住屏幕行走 · 自动攻击 · P 暂停", (self.width//2, 663), (138, 157, 180), self.small)

    def draw_records(self, screen, today, records, version):
        day, preset = today['day'], today['preset']['id']
        entries = [('普通模式最佳', records.best('normal', version)),
                   ('今日挑战最佳', records.best('daily', version, day, preset)),
                   ('同类挑战历史最佳', records.best('daily', version, day, preset, history=True))]
        for index, (name, best) in enumerate(entries):
            rect = pygame.Rect(25, 190+index*126, self.width-50, 110)
            pygame.draw.rect(screen, (22, 37, 54), rect, border_radius=12)
            self.label(screen, name, (self.width//2, rect.y+24), (122, 232, 213))
            self.label(screen, summary(best), (self.width//2, rect.y+57), font=self.small)
            self.label(screen, best['day'] if best else today['day'], (self.width//2, rect.y+87),
                       (142, 162, 184), self.small)
        self.button(screen, self.back_button, "回到标题")
        self.label(screen, '保存在当前设备 / 浏览器' if records.persistent else '存储不可用 · 纪录仅本次有效',
                   (self.width//2, 668), (142, 162, 184), self.small)

    def draw_end_buttons(self, screen):
        self.button(screen, self.restart_button, "重新开始", True)
        self.button(screen, self.title_button, "回到标题")
