#!/usr/bin/env python3
"""open.py - Title screen (assets/title.png) + opening story slides (assets/1.jpg ... 6.jpg).
Works both standalone (`python open.py`) and inside `demo_hub.py`.
"""
import os
import sys
import pygame

TITLE_NAME = "title"                            # looks for title.png / .jpg / .jpeg / .webp in assets/
SCR_W, SCR_H, PANEL_H = 1152, 648, 112
UW, UH = 960, 540
WINDOW_SIZE = (SCR_W, SCR_H + PANEL_H)
UI_SIZE = (UW, UH)

ENTER_BTN = pygame.Rect(0, 0, 250, 54)          # "ENTER THE ROOM" button on the last picture
ENTER_BTN.center = (506, 405)
FADE_S = 0.45

_HERE = os.path.dirname(os.path.abspath(__file__))
ASSET_DIRS = [
    os.path.join(os.path.dirname(_HERE), "assets"),
    os.path.join(_HERE, "assets"),
    _HERE,
    os.path.join(os.getcwd(), "assets"),
    os.getcwd(),
]

SEG_MAP = {
    "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg",
    "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg",
    "H": "bcefg", "O": "abcdef", "P": "abefg", "E": "adefg", "n": "ceg", " ": "",
}


def find_title():
    for d in ASSET_DIRS:
        if not os.path.isdir(d):
            continue
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            p = os.path.join(d, TITLE_NAME + ext)
            if os.path.isfile(p):
                return p
    return None


def find_pages(max_n=99):
    """1.jpg, 2.jpg, ... in order (also .png / .jpeg / .webp); stops at the first missing number."""
    pages, n = [], 1
    while n <= max_n:
        hit = None
        for d in ASSET_DIRS:
            if not os.path.isdir(d):
                continue
            for ext in (".jpg", ".png", ".jpeg", ".webp"):
                p = os.path.join(d, "%d%s" % (n, ext))
                if os.path.isfile(p):
                    hit = p
                    break
            if hit:
                break
        if not hit:
            break
        pages.append(hit)
        n += 1
    return pages


def fit(img, w=UW, h=UH, smooth=True):
    iw, ih = img.get_size()
    k = min(w / iw, h / ih)
    scale_fn = pygame.transform.smoothscale if smooth else pygame.transform.scale
    out = scale_fn(img, (max(1, round(iw * k)), max(1, round(ih * k))))
    s = pygame.Surface((w, h))
    s.fill((0, 0, 0))
    s.blit(out, ((w - out.get_width()) // 2, (h - out.get_height()) // 2))
    return s


def draw_digit(scr, ch, x, y, w, h):
    t = max(3, w // 6)
    h2 = h // 2
    segs = {
        "a": (x + t, y, w - 2 * t, t),
        "b": (x + w - t, y + t, t, h2 - t),
        "c": (x + w - t, y + h2, t, h2 - t),
        "d": (x + t, y + h - t, w - 2 * t, t),
        "e": (x, y + h2, t, h2 - t),
        "f": (x, y + t, t, h2 - t),
        "g": (x + t, y + h2 - t // 2, w - 2 * t, t),
    }
    on = SEG_MAP.get(ch, "")
    for k, r in segs.items():
        pygame.draw.rect(scr, (255, 60, 40) if k in on else (50, 22, 22), r)


class Game:
    def __init__(self):
        self.standalone = True
        self.pages = []
        self.has_title = False

        tp = find_title()
        if tp:
            try:
                self.pages.append(fit(pygame.image.load(tp).convert(), smooth=False))
                self.has_title = True
            except pygame.error as e:
                print("[open] could not read %s: %s" % (tp, e))

        for p in find_pages():
            try:
                self.pages.append(fit(pygame.image.load(p).convert()))
            except pygame.error as e:
                print("[open] could not read %s: %s" % (p, e))

        if not self.pages:
            print("[open] no title.png or 1.jpg ... found in", ASSET_DIRS[0])

        self.font = pygame.font.Font(None, 26)
        self.f_btn = pygame.font.Font(None, 36)
        self.f_tiny = pygame.font.Font(None, 16)
        self.mouse_ui = (0, 0)
        self.start()

    def start(self, handoff=None):
        self.handoff = dict(handoff) if handoff else {
            "hearts": 3, "form": 0, "armor": 0, "boost": False, "shards": 0
        }
        self.i, self.prev, self.fade, self.t = 0, None, 1.0, 0.0
        self.exit_requested = False
        self.go_stage1 = False
        self.hover = False

    def get_handoff(self):
        return dict(self.handoff)

    def is_title(self):
        return self.has_title and self.i == 0

    def on_last(self):
        return (
            bool(self.pages)
            and not self.is_title()
            and self.i == len(self.pages) - 1
            and self.fade >= 1.0
        )

    def next(self):
        if self.fade < 1.0:
            self.fade = 1.0
            return
        if self.is_title() and len(self.pages) == 1:
            self.enter()
            return
        if self.i + 1 >= len(self.pages):
            return
        self.prev, self.i, self.fade = self.i, self.i + 1, 0.0

    def back(self):
        if self.i > 0:
            self.prev, self.i, self.fade = self.i, self.i - 1, 0.0

    def enter(self):
        self.go_stage1 = True
        self.exit_requested = True

    def _to_ui(self, pos):
        return (pos[0] * UW / SCR_W, pos[1] * UH / SCR_H)

    def poll(self, events):
        ev = {"next": False, "back": False, "skip": False, "click": None}
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif e.type == pygame.MOUSEMOTION:
                if e.pos[1] < SCR_H:
                    self.mouse_ui = self._to_ui(e.pos)
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.pos[1] < SCR_H:
                    ui_pos = self._to_ui(e.pos)
                    self.mouse_ui = ui_pos
                    if e.button == 1:
                        ev["click"] = ui_pos
                    elif e.button == 3:
                        ev["back"] = True
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_RIGHT, pygame.K_d):
                    ev["next"] = True
                elif e.key in (pygame.K_LEFT, pygame.K_a, pygame.K_BACKSPACE):
                    ev["back"] = True
                elif e.key == pygame.K_ESCAPE:
                    ev["skip"] = True
        return ev

    def update(self, dt, ev):
        self.t += dt
        if self.fade < 1.0:
            self.fade = min(1.0, self.fade + dt / FADE_S)
        if not self.pages:
            self.exit_requested = True
            return

        self.hover = self.on_last() and ENTER_BTN.collidepoint(self.mouse_ui)

        if ev["skip"]:
            self.enter()
        elif ev["back"]:
            self.back()
        elif ev["click"] is not None:
            if self.on_last():
                if ENTER_BTN.collidepoint(ev["click"]):
                    self.enter()
            else:
                self.next()
        elif ev["next"]:
            if self.on_last():
                self.enter()
            else:
                self.next()

    def draw_panel(self, screen):
        y0 = SCR_H
        pygame.draw.rect(screen, (24, 26, 32), (0, y0, SCR_W, PANEL_H))
        pygame.draw.line(screen, (70, 74, 90), (0, y0), (SCR_W, y0), 2)
        hearts = max(0, self.handoff.get("hearts", 3))
        text = f"H{hearts}  OPEn"
        for i, ch in enumerate(text[:8]):
            draw_digit(screen, ch, 14 + i * 40, y0 + 26, 32, 52)
        hint = self.f_tiny.render(
            "BTNC (Space / Click): Next   |   Left / A: Back   |   Esc: Skip to Stage 1",
            True,
            (170, 170, 190),
        )
        screen.blit(hint, (360, y0 + 46))

    def draw(self, ui, screen):
        ui.fill((0, 0, 0))
        if self.pages:
            cur = self.pages[self.i]
            if self.fade < 1.0 and self.prev is not None:
                ui.blit(self.pages[self.prev], (0, 0))
                cur = cur.copy()
                cur.set_alpha(int(255 * self.fade))
            ui.blit(cur, (0, 0))

            if not self.is_title():
                last = self.i == len(self.pages) - 1
                if last:
                    if self.fade >= 1.0:
                        pulse = 0.5 + 0.5 * abs((self.t * 1.2) % 2 - 1)
                        col = (
                            (255, 215, 90)
                            if self.hover
                            else (int(235 + 20 * pulse), int(235 + 20 * pulse), 255)
                        )
                        bg = (30, 60, 130) if self.hover else (18, 28, 60)
                        pygame.draw.rect(ui, bg, ENTER_BTN, border_radius=10)
                        pygame.draw.rect(ui, col, ENTER_BTN, 3, border_radius=10)
                        t = self.f_btn.render("ENTER THE ROOM", True, col)
                        ui.blit(t, t.get_rect(center=ENTER_BTN.center))
                elif int(self.t * 1.6) % 2 == 0:
                    s = self.font.render("click to continue", True, (255, 255, 255))
                    sh = self.font.render("click to continue", True, (0, 0, 0))
                    x, y = UW - s.get_width() - 18, UH - 30
                    ui.blit(sh, (x + 2, y + 2))
                    ui.blit(s, (x, y))

                offset = 1 if self.has_title else 0
                n = self.font.render(
                    "%d / %d" % (self.i + 1 - offset, len(self.pages) - offset),
                    True,
                    (230, 230, 230),
                )
                ui.blit(n, (16, UH - 30))

        screen.blit(pygame.transform.smoothscale(ui, (SCR_W, SCR_H)), (0, 0))
        self.draw_panel(screen)


Opening = Game


def main():
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_caption("Digi of Adventure - Opening")
    try:
        screen = pygame.display.set_mode(WINDOW_SIZE, pygame.SCALED | pygame.RESIZABLE)
    except pygame.error:
        screen = pygame.display.set_mode(WINDOW_SIZE)
    ui = pygame.Surface(UI_SIZE)
    clock = pygame.time.Clock()
    game = Game()
    while not game.exit_requested:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        ev = game.poll(pygame.event.get())
        game.update(dt, ev)
        game.draw(ui, screen)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()