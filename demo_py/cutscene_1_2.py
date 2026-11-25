#!/usr/bin/env python3
"""cutscene_1_2.py - 1-image transition cutscene between Stage 1 and Stage 2."""
import os
import sys
import pygame

IMAGE_NAME = "cutscene1_2"   # looks for .png, .jpg, .jpeg, .webp in assets/

SCR_W, SCR_H, PANEL_H = 1152, 648, 112
UW, UH = 960, 540
WINDOW_SIZE = (SCR_W, SCR_H + PANEL_H)
UI_SIZE = (UW, UH)

FADE_S = 0.6
ZOOM_MAX = 1.08              # subtle slow zoom to give life to a single image

LINES = [
    "You cracked the Final Exam door locks and escaped Room 402!",
    "STAGE EVOLUTION: Student Uniform  ->  Workshop Shirt",
    "Next stop: your Engineering Internship. Time to put your hardware skills to work.",
]

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


def load_cutscene_image(stem):
    for d in ASSET_DIRS:
        if not os.path.isdir(d):
            continue
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            path = os.path.join(d, stem + ext)
            if os.path.isfile(path):
                try:
                    raw = pygame.image.load(path).convert()
                    # Fit inside 960x540 while preserving aspect ratio
                    iw, ih = raw.get_size()
                    k = min(UW / iw, UH / ih)
                    scaled = pygame.transform.smoothscale(
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
        self.bg = load_cutscene_image(IMAGE_NAME)
        self.f_s = pygame.font.Font(None, 22)
        self.f_m = pygame.font.Font(None, 28)
        self.f_l = pygame.font.Font(None, 36)
        self.f_tiny = pygame.font.Font(None, 16)
        self.start()

    def start(self, handoff=None):
        self.handoff = dict(handoff) if handoff else {
            "hearts": 3, "form": 1, "armor": 0, "boost": False, "shards": 0
        }
        self.handoff["form"] = max(1, self.handoff.get("form", 1))
        self.idx = 0
        self.t = 0.0
        self.exit_requested = False

    def get_handoff(self):
        return dict(self.handoff)

    def poll(self, events):
        ev = {"next": False, "skip": False}
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                ev["next"] = True
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_RIGHT, pygame.K_d):
                    ev["next"] = True
                elif e.key == pygame.K_ESCAPE:
                    ev["skip"] = True
        return ev

    def update(self, dt, ev):
        self.t += dt
        if ev["skip"]:
            self._finish()
            return
        if ev["next"]:
            if self.t < FADE_S:
                self.t = FADE_S
            elif self.idx + 1 < len(LINES):
                self.idx += 1
            else:
                self._finish()

    def _finish(self):
        if self.standalone:
            self.start(self.handoff)
        else:
            self.exit_requested = True

    def _wrap(self, text, width):
        words, lines, cur = text.split(" "), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if self.f_m.size(test)[0] <= width or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def draw_panel(self, screen):
        y0 = SCR_H
        pygame.draw.rect(screen, (24, 26, 32), (0, y0, SCR_W, PANEL_H))
        pygame.draw.line(screen, (70, 74, 90), (0, y0), (SCR_W, y0), 2)
        hearts = max(0, self.handoff.get("hearts", 3))
        text = f"H{hearts} CUt1-2"
        for i, ch in enumerate(text[:8]):
            draw_digit(screen, ch, 14 + i * 40, y0 + 26, 32, 52)
        hint = self.f_tiny.render(
            "BTNC (Space / Click): Next   |   Esc: Skip Cutscene", True, (170, 170, 190)
        )
        screen.blit(hint, (360, y0 + 46))

    def draw(self, ui, screen):
        ui.fill((12, 14, 20))

        # 1. Draw single picture with slow zoom-in motion
        if self.bg:
            zoom = 1.0 + (ZOOM_MAX - 1.0) * min(1.0, self.t / 12.0)
            zw, zh = round(UW * zoom), round(UH * zoom)
            scaled = pygame.transform.smoothscale(self.bg, (zw, zh))
            ui.blit(scaled, ((UW - zw) // 2, (UH - zh) // 2))
        else:
            msg = self.f_m.render(
                f"Put {IMAGE_NAME}.png (or .jpg) in assets/", True, (220, 220, 230)
            )
            ui.blit(msg, msg.get_rect(center=(UW // 2, UH // 2 - 40)))

        # 2. Fade-in from black
        if self.t < FADE_S:
            fade = pygame.Surface((UW, UH))
            fade.fill((0, 0, 0))
            fade.set_alpha(int(255 * (1.0 - self.t / FADE_S)))
            ui.blit(fade, (0, 0))

        # 3. Dialogue / caption box
        box = pygame.Rect(40, 396, 880, 124)
        panel = pygame.Surface((box.w, box.h), pygame.SRCALPHA)
        panel.fill((14, 18, 28, 220))
        ui.blit(panel, box.topleft)
        pygame.draw.rect(ui, (255, 230, 120), box, 2, border_radius=10)

        tag = self.f_s.render("STAGE 1  ->  STAGE 2", True, (255, 230, 120))
        ui.blit(tag, (box.x + 22, box.y + 12))

        for i, line in enumerate(self._wrap(LINES[self.idx], box.w - 44)):
            txt = self.f_m.render(line, True, (245, 245, 250))
            ui.blit(txt, (box.x + 22, box.y + 42 + i * 28))

        prompt_str = "BTNC: Enter Stage 2 >>" if self.idx == len(LINES) - 1 else "BTNC: Next"
        if int(self.t * 2) % 2 == 0 or self.idx == len(LINES) - 1:
            prompt = self.f_s.render(prompt_str, True, (150, 255, 170))
            ui.blit(prompt, (box.right - prompt.get_width() - 20, box.bottom - 28))

        step = self.f_s.render(f"{self.idx + 1} / {len(LINES)}", True, (160, 170, 190))
        ui.blit(step, (box.x + 22, box.bottom - 28))

        screen.blit(pygame.transform.smoothscale(ui, (SCR_W, SCR_H)), (0, 0))
        self.draw_panel(screen)


def main():
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_caption("CPE Escape - Cutscene 1 -> 2")
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