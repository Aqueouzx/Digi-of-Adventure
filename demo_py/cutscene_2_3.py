#!/usr/bin/env python3
"""cutscene_2_3.py - 3-slide transition cutscene between Stage 2 and Stage 3."""
import os
import sys
import pygame

SLIDE_NAMES = ("cut23_1", "cut23_2", "cut23_3")   # .png / .jpg / .jpeg / .webp in assets/

SUBTITLES = [
    "Stage 2 Clear — Internship Complete!",
    "Received: Graduation Gown",
    "Character Evolved! Ready for Stage 3.",
]

SCR_W, SCR_H, PANEL_H = 1152, 648, 112
UW, UH = 960, 540
WINDOW_SIZE = (SCR_W, SCR_H + PANEL_H)
UI_SIZE = (UW, UH)
FADE_S = 0.4

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
    "H": "bcefg", "C": "adef", "U": "bcdef", "t": "defg", "-": "g", " ": "",
}


def load_slide(stem):
    for d in ASSET_DIRS:
        if not os.path.isdir(d):
            continue
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            path = os.path.join(d, stem + ext)
            if os.path.isfile(path):
                try:
                    raw = pygame.image.load(path).convert()
                    iw, ih = raw.get_size()
                    k = min(UW / iw, UH / ih)
                    scaled = pygame.transform.scale(
                        raw, (max(1, round(iw * k)), max(1, round(ih * k)))
                    )
                    canvas = pygame.Surface((UW, UH))
                    canvas.fill((12, 14, 20))
                    canvas.blit(
                        scaled,
                        ((UW - scaled.get_width()) // 2, (UH - scaled.get_height()) // 2),
                    )
                    return canvas
                except pygame.error:
                    pass
    return None


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
        self.slides = [load_slide(name) for name in SLIDE_NAMES]
        self.f_tiny = pygame.font.Font(None, 16)
        self.f_s = pygame.font.Font(None, 24)
        self.f_m = pygame.font.Font(None, 28)
        self.start()

    def start(self, handoff=None):
        self.handoff = dict(handoff) if handoff else {
            "hearts": 3, "form": 2, "armor": 0, "boost": False, "shards": 0
        }
        self.handoff["form"] = max(2, self.handoff.get("form", 2))  # Graduation gown
        self.idx = 0
        self.prev = None
        self.fade = 1.0
        self.t = 0.0
        self.exit_requested = False

    def get_handoff(self):
        return dict(self.handoff)

    def poll(self, events):
        ev = {"next": False, "back": False, "skip": False}
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1:
                    ev["next"] = True
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

        if ev["skip"]:
            self._finish()
            return

        if ev["back"] and self.idx > 0:
            self.prev, self.idx, self.fade = self.idx, self.idx - 1, 0.0
            return

        if ev["next"]:
            if self.fade < 1.0:
                self.fade = 1.0
            elif self.idx + 1 < len(SLIDE_NAMES):
                self.prev, self.idx, self.fade = self.idx, self.idx + 1, 0.0
            else:
                self._finish()

    def _finish(self):
        if self.standalone:
            self.start(self.handoff)
        else:
            self.exit_requested = True

    def draw_panel(self, screen):
        y0 = SCR_H
        pygame.draw.rect(screen, (24, 26, 32), (0, y0, SCR_W, PANEL_H))
        pygame.draw.line(screen, (70, 74, 90), (0, y0), (SCR_W, y0), 2)
        hearts = max(0, self.handoff.get("hearts", 3))
        text = f"H{hearts} CUt2-3"
        for i, ch in enumerate(text[:8]):
            draw_digit(screen, ch, 14 + i * 40, y0 + 26, 32, 52)
        hint = self.f_tiny.render(
            "BTNC (Space / Click): Next   |   Left / A: Back   |   Esc: Skip",
            True,
            (170, 170, 190),
        )
        screen.blit(hint, (360, y0 + 46))

    def draw(self, ui, screen):
        ui.fill((12, 14, 20))

        cur_img = self.slides[self.idx]
        if self.fade < 1.0 and self.prev is not None and self.slides[self.prev]:
            ui.blit(self.slides[self.prev], (0, 0))
            if cur_img:
                tmp = cur_img.copy()
                tmp.set_alpha(int(255 * self.fade))
                ui.blit(tmp, (0, 0))
        elif cur_img:
            ui.blit(cur_img, (0, 0))
        else:
            msg = self.f_m.render(
                f"Put {SLIDE_NAMES[self.idx]}.png in assets/", True, (220, 220, 230)
            )
            ui.blit(msg, msg.get_rect(center=(UW // 2, UH // 2)))

        # Slim bottom bar so characters, speech bubbles, and evolution aura stay clear
        bar = pygame.Surface((UW, 40), pygame.SRCALPHA)
        bar.fill((12, 15, 24, 205))
        ui.blit(bar, (0, UH - 40))
        pygame.draw.line(ui, (90, 100, 130), (0, UH - 40), (UW, UH - 40), 1)

        step = self.f_s.render(f"{self.idx + 1} / {len(SLIDE_NAMES)}", True, (180, 190, 210))
        ui.blit(step, (18, UH - 29))

        sub = self.f_s.render(SUBTITLES[self.idx], True, (255, 230, 120))
        ui.blit(sub, sub.get_rect(center=(UW // 2, UH - 20)))

        is_last = self.idx == len(SLIDE_NAMES) - 1
        prompt_str = "BTNC: Enter Stage 3 >>" if is_last else "BTNC: Next >>"
        if int(self.t * 2) % 2 == 0 or is_last:
            prompt = self.f_s.render(prompt_str, True, (150, 255, 170))
            ui.blit(prompt, (UW - prompt.get_width() - 18, UH - 29))

        screen.blit(pygame.transform.smoothscale(ui, (SCR_W, SCR_H)), (0, 0))
        self.draw_panel(screen)


def main():
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_caption("CPE Escape - Cutscene 2 -> 3")
    try:
        screen = pygame.display.set_mode(WINDOW_SIZE, pygame.SCALED | pygame.RESIZABLE)
    except pygame.error:
        screen = pygame.display.set_mode(WINDOW_SIZE)
    ui = pygame.Surface(UI_SIZE)
    clock = pygame.time.Clock()
    game = Game()
    while True:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        ev = game.poll(pygame.event.get())
        game.update(dt, ev)
        game.draw(ui, screen)
        pygame.display.flip()


if __name__ == "__main__":
    main()