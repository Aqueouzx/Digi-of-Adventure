#!/usr/bin/env python3
"""cutscene_ending.py - Graduation & Career Ending Cutscene (9 endings based on most-picked card)."""
import math
import os
import sys
import pygame

try:
    import card_assets
except ImportError:
    card_assets = None

SCR_W, SCR_H, PANEL_H = 1152, 648, 112
UW, UH = 960, 540
WINDOW_SIZE = (SCR_W, SCR_H + PANEL_H)
UI_SIZE = (UW, UH)
FADE_S = 0.6
REVEAL_LOCK_S = 1.2   # ignore exit/finish taps right after revealing the ending

CONFIRM_BOX = pygame.Rect(250, 172, 460, 196)
BTN_KEEP = pygame.Rect(280, 290, 185, 48)
BTN_REPLAY = pygame.Rect(495, 290, 185, 48)

# Mapping: career (0=Green/AIR, 1=Yellow/EARTH, 2=Red/WATER) -> (left, middle, right) ending number
ENDING_MAP = {
    0: (3, 1, 2),   # Green:  left=ending3, middle=ending1, right=ending2
    1: (4, 5, 6),   # Yellow: left=ending4, middle=ending5, right=ending6
    2: (7, 8, 9),   # Red:    left=ending7, middle=ending8, right=ending9
}

CAREER_INFO = {
    0: ("Green", (80, 200, 105)),
    1: ("Yellow", (235, 195, 60)),
    2: ("Red", (220, 85, 70)),
}

CARD_NAMES = {
    0: ("Fart", "Wing", "Plane"),     # Green:  left=fart, middle=wing, right=plane
    1: ("Boat", "Wrench", "Money"),   # Yellow: left=boat, middle=wrench, right=money
    2: ("Worm", "Flag", "Plug"),      # Red:    left=worm, middle=flag, right=plug
}

ENDINGS = {
    1: ("Fried Grasshopper Seller", "Green / Wing"),
    2: ("Aircon Technician", "Green / Plane"),
    3: ("Astronaut", "Green / Fart"),
    4: ("Noodle Seller", "Yellow / Boat"),
    5: ("Software Engineer", "Yellow / Wrench"),
    6: ("Lottery Seller", "Yellow / Money"),
    7: ("Fisherman", "Red / Worm"),
    8: ("Pirate", "Red / Flag"),
    9: ("Subsea Network Engineer", "Red / Plug"),
}

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
    "H": "bcefg", "E": "adefg", "n": "ceg", "d": "bcdeg", "-": "g", " ": "",
}


def find_asset(stem):
    for d in ASSET_DIRS:
        if not os.path.isdir(d):
            continue
        for ext in (".jpg", ".png", ".jpeg", ".webp"):
            path = os.path.join(d, stem + ext)
            if os.path.isfile(path):
                return path
    return None


def load_ending_image(ending_num):
    path = find_asset(f"ending{ending_num}")
    if not path:
        return None
    try:
        raw = pygame.image.load(path).convert()
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
        return None


def load_grad_sprite(form=2, height=130):
    candidates = [f"player_form{form}_front_stand.png", "player_form2_front_stand.png", "player_form0_front_stand.png"]
    for name in candidates:
        for d in ASSET_DIRS:
            path = os.path.join(d, name)
            if os.path.isfile(path):
                try:
                    raw = pygame.image.load(path).convert_alpha()
                    w = max(1, round(raw.get_width() * height / raw.get_height()))
                    return pygame.transform.smoothscale(raw, (w, height))
                except (pygame.error, ValueError):
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


def resolve_ending(handoff):
    """Return (career, most_pos, counts, ending_num) from handoff card data."""
    career = handoff.get("career")
    if career not in (0, 1, 2):
        career = 0
    raw_backs = handoff.get("card_backs") or []
    picks = [int(x) for x in raw_backs if x in (0, 1, 2)]
    counts = [0, 0, 0]
    last_idx = [-1, -1, -1]
    for i, pos in enumerate(picks):
        counts[pos] += 1
        last_idx[pos] = i
    most_pos = max((0, 1, 2), key=lambda p: (counts[p], last_idx[p])) if picks else 1
    ending_num = ENDING_MAP[career][most_pos]
    return career, most_pos, counts, ending_num


class Game:
    CHECKPOINTS = [
        ("grad", "Graduation ceremony"),
        ("reveal", "Ending career reveal"),
    ]
    ACTIONS = [
        (f"end_{i}", f"Ending {i}: {ENDINGS[i][0]}")
        for i in range(1, 10)
    ]

    def __init__(self):
        self.standalone = True
        self.ending_images = {i: load_ending_image(i) for i in range(1, 10)}
        self.card_art = card_assets.CardAssets(card_size=(96, 96)) if card_assets else None
        self.grad_sprites = {
            2: load_grad_sprite(2, 132),
            3: load_grad_sprite(3, 132),
        }
        self.f_tiny = pygame.font.Font(None, 16)
        self.f_s = pygame.font.Font(None, 22)
        self.f_m = pygame.font.Font(None, 28)
        self.f_l = pygame.font.Font(None, 44)
        self.confetti = [
            (
                (i * 73) % UW,
                (i * 41) % UH,
                28 + (i * 19) % 45,
                ((i * 7) % 5) + 3,
                [(255, 220, 90), (120, 220, 255), (140, 245, 160), (255, 140, 160), (210, 160, 255)][i % 5],
            )
            for i in range(42)
        ]
        self.start()

    def start(self, handoff=None):
        self.handoff = dict(handoff) if handoff else {
            "hearts": 3, "form": 2, "armor": 0, "boost": False, "shards": 0,
            "career": 0, "card_backs": [1, 1, 1],
        }
        self.career, self.most_pos, self.counts, self.ending_num = resolve_ending(self.handoff)
        self.step = 0
        self.t = 0.0
        self.step_t = 0.0
        self.fade_t = 0.0
        self.confirm_open = False
        self.confirm_choice = 0   # 0 = Keep Viewing (safe default), 1 = Play Again
        self.exit_requested = False

    def get_handoff(self):
        return dict(self.handoff)

    def get_progress(self):
        return self.step

    def jump_to(self, key):
        self.step = 1 if key == "reveal" else 0
        self.step_t = REVEAL_LOCK_S if self.step == 1 else 0.0
        self.fade_t = 0.0 if self.step == 1 else FADE_S
        self.confirm_open = False
        self.confirm_choice = 0

    def do_action(self, key):
        if key.startswith("end_"):
            try:
                num = int(key.split("_")[1])
            except (IndexError, ValueError):
                return
            if 1 <= num <= 9:
                for c, row in ENDING_MAP.items():
                    if num in row:
                        self.career = c
                        self.most_pos = row.index(num)
                        break
                self.ending_num = num
                self.counts = [1 if i == self.most_pos else 0 for i in range(3)]
                self.step = 1
                self.step_t = REVEAL_LOCK_S
                self.fade_t = 0.0
                self.confirm_open = False
                self.confirm_choice = 0

    def _to_ui(self, pos):
        return (pos[0] * UW / SCR_W, pos[1] * UH / SCR_H)

    def poll(self, events):
        ev = {
            "next": False,
            "back": False,
            "skip": False,
            "left": False,
            "right": False,
            "click_pos": None,
        }
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1 and e.pos[1] < SCR_H:
                    ev["click_pos"] = self._to_ui(e.pos)
                elif e.button == 3:
                    ev["back"] = True
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    ev["next"] = True
                elif e.key in (pygame.K_RIGHT, pygame.K_d):
                    ev["right"] = True
                elif e.key in (pygame.K_LEFT, pygame.K_a):
                    ev["left"] = True
                elif e.key == pygame.K_BACKSPACE:
                    ev["back"] = True
                elif e.key == pygame.K_ESCAPE:
                    ev["skip"] = True
        return ev

    def update(self, dt, ev):
        self.t += dt
        self.step_t += dt
        self.fade_t += dt

        if self.step == 0:
            if ev["skip"]:
                self.step = 1
                self.step_t = 0.0
                self.fade_t = 0.0
                self.confirm_open = False
                self.confirm_choice = 0
                return
            if ev["next"] or ev["right"] or ev["click_pos"] is not None:
                if self.fade_t < FADE_S:
                    self.fade_t = FADE_S
                else:
                    self.step = 1
                    self.step_t = 0.0
                    self.fade_t = 0.0
                    self.confirm_open = False
                    self.confirm_choice = 0
            return

        # Step 1: Ending Career Reveal (protected against accidental BTNC / click restart)
        if self.confirm_open:
            if ev["left"] or ev["right"]:
                self.confirm_choice = 1 - self.confirm_choice
            elif ev["back"] or ev["skip"]:
                self.confirm_open = False
                self.confirm_choice = 0
            elif ev["click_pos"] is not None:
                pos = ev["click_pos"]
                if BTN_REPLAY.collidepoint(pos):
                    self._finish()
                else:
                    self.confirm_open = False
                    self.confirm_choice = 0
            elif ev["next"]:
                if self.confirm_choice == 1:
                    self._finish()
                else:
                    self.confirm_open = False
                    self.confirm_choice = 0
            return

        if ev["back"] or ev["left"]:
            self.step = 0
            self.step_t = 0.0
            self.fade_t = 0.0
            self.confirm_open = False
            return

        # Require the reveal lock period to pass before opening the restart prompt
        if self.step_t >= REVEAL_LOCK_S and (
            ev["next"] or ev["skip"] or ev["click_pos"] is not None
        ):
            self.confirm_open = True
            self.confirm_choice = 0

    def _finish(self):
        if self.standalone:
            self.start(self.handoff)
        else:
            self.exit_requested = True

    def _draw_graduation(self, ui):
        ui.fill((16, 22, 38))
        for y in range(0, UH, 12):
            tone = int(16 + 18 * (y / UH))
            pygame.draw.rect(ui, (tone, tone + 6, tone + 24), (0, y, UW, 12))

        # Subtle animated celebration confetti
        for x0, y0, spd, sz, col in self.confetti:
            cy = (y0 + self.t * spd) % (UH + 20) - 10
            cx = (x0 + math.sin(self.t * 2.0 + y0) * 14) % UW
            pygame.draw.rect(ui, col, (int(cx), int(cy), sz, sz))

        # Banner
        title = self.f_l.render("CONGRATULATIONS, GRADUATE!", True, (255, 230, 110))
        ui.blit(title, title.get_rect(center=(UW // 2, 62)))
        sub = self.f_m.render(
            "You cleared Stage 3 and officially graduated from CPE!", True, (235, 240, 250)
        )
        ui.blit(sub, sub.get_rect(center=(UW // 2, 104)))

        # Center card showing character & card tally
        box = pygame.Rect(110, 142, 740, 300)
        panel = pygame.Surface((box.w, box.h), pygame.SRCALPHA)
        panel.fill((12, 16, 28, 225))
        ui.blit(panel, box.topleft)
        pygame.draw.rect(ui, (255, 220, 110), box, 2, border_radius=14)

        # Left side: graduation character sprite
        form_idx = 3 if self.handoff.get("form", 2) >= 3 else 2
        spr = self.grad_sprites.get(form_idx) or self.grad_sprites.get(2)
        portrait = pygame.Rect(box.x + 28, box.y + 34, 170, 210)
        pygame.draw.rect(ui, (26, 34, 54), portrait, border_radius=12)
        pygame.draw.rect(ui, (90, 110, 155), portrait, 2, border_radius=12)
        if spr:
            bob = round(math.sin(self.t * 3.0) * 4)
            ui.blit(spr, spr.get_rect(center=(portrait.centerx, portrait.centery + bob)))
        cap = self.f_s.render("Class of CPE", True, (200, 215, 245))
        ui.blit(cap, cap.get_rect(center=(portrait.centerx, portrait.bottom + 20)))

        # Right side: Career path & most-picked card summary
        rx = portrait.right + 34
        career_name, career_col = CAREER_INFO[self.career]
        card_names = CARD_NAMES[self.career]
        lbl = self.f_s.render("YOUR CARD JOURNEY", True, (170, 190, 230))
        ui.blit(lbl, (rx, box.y + 28))

        path_txt = self.f_m.render(f"Career Color: {career_name}", True, career_col)
        ui.blit(path_txt, (rx, box.y + 58))

        for pos in range(3):
            slot = pygame.Rect(rx + pos * 158, box.y + 102, 138, 140)
            is_top = (pos == self.most_pos)
            bg_col = (44, 54, 82) if is_top else (24, 30, 48)
            edge_col = (255, 225, 110) if is_top else (75, 85, 115)
            pygame.draw.rect(ui, bg_col, slot, border_radius=10)
            pygame.draw.rect(ui, edge_col, slot, 3 if is_top else 1, border_radius=10)

            icon_rect = pygame.Rect(slot.centerx - 42, slot.y + 10, 84, 84)
            if self.card_art:
                img = self.card_art.get_image(2, self.career, pos, False, size=(84, 84))
                if img:
                    ui.blit(img, img.get_rect(center=icon_rect.center))
                else:
                    pygame.draw.rect(ui, career_col, icon_rect, border_radius=8)
            else:
                pygame.draw.rect(ui, career_col, icon_rect, border_radius=8)

            ptxt = self.f_s.render(f"{card_names[pos]}: x{self.counts[pos]}", True,
                                   (255, 235, 140) if is_top else (210, 215, 230))
            ui.blit(ptxt, ptxt.get_rect(center=(slot.centerx, slot.bottom - 22)))

        note = self.f_s.render(
            f"Most Picked: {card_names[self.most_pos]} Card  ->  Ending #{self.ending_num}",
            True,
            (150, 255, 175),
        )
        ui.blit(note, (rx, box.bottom - 38))

        # Continue prompt
        if int(self.t * 2) % 2 == 0:
            prompt = self.f_m.render(
                "BTNC (Space / Click): Reveal Your Ending Career >>", True, (150, 255, 170)
            )
            ui.blit(prompt, prompt.get_rect(center=(UW // 2, UH - 44)))

    def _draw_ending_reveal(self, ui):
        img = self.ending_images.get(self.ending_num)
        if img:
            ui.blit(img, (0, 0))
        else:
            title, desc = ENDINGS[self.ending_num]
            ui.fill((22, 24, 34))
            t_surf = self.f_l.render(f"ENDING {self.ending_num}: {title}", True, (255, 230, 120))
            d_surf = self.f_m.render(desc, True, (220, 225, 240))
            m_surf = self.f_s.render(
                f"Put ending{self.ending_num}.jpg in assets/", True, (180, 185, 200)
            )
            ui.blit(t_surf, t_surf.get_rect(center=(UW // 2, UH // 2 - 40)))
            ui.blit(d_surf, d_surf.get_rect(center=(UW // 2, UH // 2 + 10)))
            ui.blit(m_surf, m_surf.get_rect(center=(UW // 2, UH // 2 + 50)))

        # Minimal unobtrusive bottom-edge pill so none of the ending card text/stars/icon is covered
        if self.step_t >= REVEAL_LOCK_S and not self.confirm_open:
            pill = pygame.Surface((370, 22), pygame.SRCALPHA)
            pill.fill((12, 14, 20, 185))
            px = (UW - pill.get_width()) // 2
            py = UH - 24
            ui.blit(pill, (px, py))
            label = "Space / Click: Finish Options   |   Left: Summary"
            txt = self.f_tiny.render(label, True, (230, 235, 245))
            ui.blit(txt, txt.get_rect(center=(UW // 2, py + 11)))

        if self.confirm_open:
            self._draw_confirm_modal(ui)

    def _draw_confirm_modal(self, ui):
        ov = pygame.Surface((UW, UH), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 165))
        ui.blit(ov, (0, 0))

        box_bg = pygame.Surface((CONFIRM_BOX.w, CONFIRM_BOX.h), pygame.SRCALPHA)
        box_bg.fill((18, 22, 34, 242))
        ui.blit(box_bg, CONFIRM_BOX.topleft)
        pygame.draw.rect(ui, (255, 225, 110), CONFIRM_BOX, 2, border_radius=14)

        t1 = self.f_m.render("RETURN TO THE BEGINNING?", True, (255, 230, 120))
        t2 = self.f_s.render("Leave your ending screen and start a new game?", True, (220, 225, 240))
        ui.blit(t1, t1.get_rect(center=(CONFIRM_BOX.centerx, CONFIRM_BOX.y + 42)))
        ui.blit(t2, t2.get_rect(center=(CONFIRM_BOX.centerx, CONFIRM_BOX.y + 78)))

        buttons = (
            (BTN_KEEP, "Keep Viewing", 0, (48, 86, 130), (140, 220, 255)),
            (BTN_REPLAY, "Play Again", 1, (120, 52, 52), (255, 160, 130)),
        )
        for rect, label, idx, fill_col, hi_col in buttons:
            sel = (self.confirm_choice == idx)
            pygame.draw.rect(ui, fill_col if sel else (34, 38, 52), rect, border_radius=10)
            pygame.draw.rect(ui, (255, 230, 120) if sel else (90, 98, 125), rect, 3 if sel else 1, border_radius=10)
            lbl = self.f_s.render(label, True, hi_col if sel else (210, 215, 230))
            ui.blit(lbl, lbl.get_rect(center=rect.center))

        hint = self.f_tiny.render(
            "BTNL / BTNR: Select   |   BTNC / Space: Confirm   |   Click a button",
            True,
            (175, 185, 210),
        )
        ui.blit(hint, hint.get_rect(center=(CONFIRM_BOX.centerx, CONFIRM_BOX.bottom - 20)))

    def draw_panel(self, screen):
        y0 = SCR_H
        pygame.draw.rect(screen, (24, 26, 32), (0, y0, SCR_W, PANEL_H))
        pygame.draw.line(screen, (70, 74, 90), (0, y0), (SCR_W, y0), 2)
        hearts = max(0, self.handoff.get("hearts", 3))
        text = f"H{hearts} End-{self.ending_num}"
        for i, ch in enumerate(text[:8]):
            draw_digit(screen, ch, 14 + i * 40, y0 + 26, 32, 52)

        title, _ = ENDINGS[self.ending_num]
        status = self.f_s.render(
            f"Ending {self.ending_num}/9: {title}", True, (255, 230, 120)
        )
        screen.blit(status, (360, y0 + 26))
        if self.step == 0:
            hint_str = "BTNC (Space / Click): Reveal Your Ending Career"
        elif self.confirm_open:
            hint_str = "BTNL / BTNR: Choose   |   BTNC (Space / Enter): Confirm   |   Esc: Stay"
        else:
            hint_str = "BTNC (Space / Click): Finish Options   |   Left / Backspace: Summary"
        hint = self.f_tiny.render(hint_str, True, (170, 170, 190))
        screen.blit(hint, (360, y0 + 60))

    def draw(self, ui, screen):
        ui.fill((12, 14, 20))
        if self.step == 0:
            self._draw_graduation(ui)
        else:
            self._draw_ending_reveal(ui)

        if self.fade_t < FADE_S:
            fade = pygame.Surface((UW, UH))
            fade.fill((0, 0, 0))
            fade.set_alpha(int(255 * (1.0 - self.fade_t / FADE_S)))
            ui.blit(fade, (0, 0))

        screen.blit(pygame.transform.smoothscale(ui, (SCR_W, SCR_H)), (0, 0))
        self.draw_panel(screen)


def main():
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_caption("CPE Escape - Ending Cutscene")
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
