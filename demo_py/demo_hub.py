#!/usr/bin/env python3
"""demo_hub.py - DEMO ONLY. Runs every stage in one window and adds a teleport menu (top-right, or F10).
The final submission does not import this file, so the menu never appears in the real game.

Every stage file must provide a class (default name: Game) with:
    __init__()                  create fonts/images (display already initialised)
    poll(events) -> ev          read input
    update(dt, ev)
    draw(ui, screen)            ui = Surface(UI_SIZE), screen = window
    start(handoff=None)         fresh start. handoff = dict from the previous stage
    get_handoff() -> dict       {"hearts","form","armor","boost","shards"} for the next stage
    exit_requested (bool)       set True when the player finishes the stage and presses continue
    standalone (bool)           hub sets it False (the stage must not restart itself when cleared)
  optional (menu hides what is missing):
    CHECKPOINTS = [(key, label), ...]   ordered progress ticks, e.g. ("r2", "3 puzzles done")
    ACTIONS     = [(key, label), ...]   one-off shortcuts
    jump_to(key), do_action(key), get_progress() -> index of the furthest checkpoint reached
    set_hearts(n), set_form(i), toggle_debug(), debug (bool)
"""
import importlib, sys, time
import pygame

DEMO_MENU = True                     # False = hub works but no menu is drawn
REGISTRY = [                         # (tab label, python module, class name) - edit to match your files
    ("Open", "open", "Game"),
    ("Stage 1", "stage1_demo", "Game"),
    ("Cutscene 1-2", "cutscene_1_2", "Game"),
    ("Stage 2", "stage2_demo", "Game"),
    ("Cutscene 2-3", "cutscene_2_3", "Game"),
    ("Stage 3", "stage3_demo", "Game"),
]
WINDOW = (1152, 760)
UI_SIZE = (960, 540)
GAME_H = 648                         # height of the game area above the board panel

BG, EDGE, TXT, DIM, GOLD, GREEN = (18, 20, 28), (120, 130, 170), (235, 235, 245), (130, 135, 160), (255, 230, 120), (120, 230, 150)


class Hub:
    def __init__(self):
        self.games = [None] * len(REGISTRY)
        self.errors = [""] * len(REGISTRY)
        self.cur = 0
        self.open = False
        self.note = ("", 0.0)
        self.panel = pygame.Rect(0, 0, 0, 0)

    # ---------- stage management ----------
    def load(self, i):
        if self.games[i] or self.errors[i]:
            return self.games[i]
        _, mod, cls = REGISTRY[i]
        try:
            g = getattr(importlib.import_module(mod), cls)()
            g.standalone = False
            self.games[i] = g
        except Exception as e:           # missing file or a bug in a stage: show it, do not crash the demo
            self.errors[i] = "%s: %s" % (type(e).__name__, e)
        return self.games[i]

    def say(self, text):
        self.note = (text, time.time() + 3.0)

    def switch(self, i, handoff=None):
        g = self.load(i)
        if not g:
            self.say("%s is not available: %s" % (REGISTRY[i][0], self.errors[i][:60]))
            return
        g.start(handoff)
        self.cur = i
        self.open = False

    def select(self, i):
        self.switch(i, {"hearts": 3, "form": i, "armor": 0, "boost": False, "shards": 0})

    def next_stage(self):
        g = self.games[self.cur]
        g.exit_requested = False
        nxt = self.cur + 1
        if nxt >= len(REGISTRY) or not self.load(nxt):
            self.say("No next stage loaded.")
            return
        self.switch(nxt, g.get_handoff() if hasattr(g, "get_handoff") else None)

    # ---------- menu ----------

    def menu_items(self):
        x0, w = WINDOW[0] - 402, 390
        items, y = [], 54

        def row(entries, h=28):
            nonlocal y
            n, gap = len(entries), 6
            wd = (w - 20 - gap * (n - 1)) // n
            for k, (kind, text, fn, on, en) in enumerate(entries):
                items.append((kind, pygame.Rect(x0 + 10 + k * (wd + gap), y, wd, h), text, fn, on, en))
            y += h + 4

        g = self.games[self.cur]
        row([("head", "DEMO TOOLS", None, False, True)], 26)
        tabs = [
            ("tab", REGISTRY[i][0], (lambda i=i: self.select(i)), i == self.cur, not self.errors[i])
            for i in range(len(REGISTRY))
        ]
        for start in range(0, len(tabs), 3):
            row(tabs[start:start + 3], 30)
        if g:
            cps = getattr(g, "CHECKPOINTS", [])
            if cps:
                row([("sub", "Progress (tick = done, click to jump there)", None, False, True)], 20)
                prog = g.get_progress() if hasattr(g, "get_progress") else -1
                for k, (key, label) in enumerate(cps):
                    row([("check", label, (lambda key=key: self.jump(key)), k <= prog, True)])
            acts = getattr(g, "ACTIONS", [])
            if acts:
                row([("sub", "Shortcuts", None, False, True)], 20)
                for key, label in acts:
                    row([("button", label, (lambda key=key: self.act(key)), False, True)])
            row([("sub", "Tools", None, False, True)], 20)
            if hasattr(g, "set_hearts"):
                row([("button", "Hearts %d" % n, (lambda n=n: g.set_hearts(n)), False, True) for n in (1, 2, 3)])
            if hasattr(g, "set_form"):
                row([("button", "Form %d" % (n + 1), (lambda n=n: g.set_form(n)), False, True) for n in range(4)])
            row([("button", "Collision debug", g.toggle_debug if hasattr(g, "toggle_debug") else None,
                  bool(getattr(g, "debug", False)), hasattr(g, "toggle_debug")),
                 ("button", "Restart stage", (lambda: (g.start(), self.close())), False, True)])
            row([("button", "Skip to next stage >>", self.next_stage, False, True)])
        row([("sub", "F10 or the menu button", None, False, True)], 20)
        self.panel = pygame.Rect(x0, 46, w, y - 46 + 6)
        return items


    def close(self):
        self.open = False

    def jump(self, key):
        self.games[self.cur].jump_to(key)
        self.close()

    def act(self, key):
        self.games[self.cur].do_action(key)
        self.close()

    def click(self, pos):
        for kind, r, text, fn, on, en in self.menu_items():
            if kind in ("tab", "check", "button") and en and fn and r.collidepoint(pos):
                fn()
                return

    # ---------- events ----------
    def filter(self, events):
        out = []
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if DEMO_MENU:
                if e.type == pygame.KEYDOWN and e.key == pygame.K_F10:
                    self.open = not self.open
                    continue
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if self.open:
                        self.click(e.pos)
                        continue
                if self.open:
                    if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                        self.open = False
                    continue                      # swallow everything else while the menu is open
            out.append(e)
        return out

    # ---------- drawing ----------
    def draw_overlay(self, screen, fonts):
        f, fb = fonts
        if time.time() < self.note[1]:
            img = f.render(self.note[0], True, TXT)
            r = pygame.Rect(WINDOW[0] // 2 - img.get_width() // 2 - 10, GAME_H - 40, img.get_width() + 20, 28)
            pygame.draw.rect(screen, (0, 0, 0), r, border_radius=6)
            screen.blit(img, (r.x + 10, r.y + 6))
        if not self.open:
            return
        items = self.menu_items()
        pygame.draw.rect(screen, BG, self.panel, border_radius=10)
        pygame.draw.rect(screen, EDGE, self.panel, 2, border_radius=10)
        mouse = pygame.mouse.get_pos()
        for kind, r, text, fn, on, en in items:
            hover = r.collidepoint(mouse) and en and kind in ("tab", "check", "button")
            if kind == "head":
                screen.blit(fb.render(text, True, GOLD), (r.x, r.y + 3))
            elif kind == "sub":
                screen.blit(f.render(text, True, DIM), (r.x, r.y + 3))
            elif kind in ("tab", "button"):
                col = (70, 90, 150) if on else ((60, 64, 86) if hover else (40, 44, 60))
                pygame.draw.rect(screen, col, r, border_radius=6)
                img = f.render(text, True, TXT if en else (90, 90, 100))
                screen.blit(img, (r.centerx - img.get_width() // 2, r.centery - img.get_height() // 2))
            elif kind == "check":
                if hover:
                    pygame.draw.rect(screen, (40, 44, 60), r, border_radius=6)
                box = pygame.Rect(r.x + 6, r.y + 5, 18, 18)
                pygame.draw.rect(screen, GREEN if on else DIM, box, 2, border_radius=3)
                if on:
                    pygame.draw.lines(screen, GREEN, False,
                                      [(box.x + 3, box.y + 9), (box.x + 7, box.y + 13), (box.x + 15, box.y + 4)], 3)
                screen.blit(f.render(text, True, TXT if on else (190, 190, 205)), (r.x + 32, r.y + 6))
            elif kind in ("tab", "button"):
                col = (70, 90, 150) if on else ((60, 64, 86) if hover else (40, 44, 60))
                pygame.draw.rect(screen, col, r, border_radius=6)
                img = f.render(text, True, TXT if en else (90, 90, 100))
                if img.get_width() > r.w - 8:
                    img = pygame.transform.smoothscale(img, (r.w - 8, img.get_height()))
                screen.blit(img, (r.centerx - img.get_width() // 2, r.centery - img.get_height() // 2))

    def draw_missing(self, screen, fonts):
        screen.fill(BG)
        msg = self.errors[self.cur] or "Stage not loaded"
        screen.blit(fonts[1].render("%s could not start" % REGISTRY[self.cur][0], True, (255, 120, 120)), (40, 40))
        screen.blit(fonts[0].render(msg[:110], True, TXT), (40, 80))
        screen.blit(fonts[0].render("Open the menu (F10) and pick another stage.", True, DIM), (40, 110))

    # ---------- main loop ----------
    def run(self):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption("CPE Escape - DEMO")
        try:
            screen = pygame.display.set_mode(WINDOW, pygame.SCALED | pygame.RESIZABLE)
        except pygame.error:
            screen = pygame.display.set_mode(WINDOW)
        ui = pygame.Surface(UI_SIZE)
        fonts = (pygame.font.Font(None, 22), pygame.font.Font(None, 30))
        clock = pygame.time.Clock()
        self.load(0)
        while True:
            dt = min(clock.tick(60) / 1000.0, 0.05)
            events = self.filter(pygame.event.get())
            g = self.games[self.cur]
            if g:
                if not self.open:
                    ev = g.poll(events)
                    g.update(dt, ev)
                    if getattr(g, "exit_requested", False):
                        self.next_stage()
                g.draw(ui, screen)
            else:
                self.draw_missing(screen, fonts)
            if DEMO_MENU:
                self.draw_overlay(screen, fonts)
            pygame.display.flip()


if __name__ == "__main__":
    Hub().run()