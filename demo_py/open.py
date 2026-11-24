"""Opening scene: assets/1.jpg ... 6.jpg, one click -> next picture.
Run alone:  python open.py        (click / Space / Enter / Right = next, Left / Backspace = back, Esc = skip)
From demo_hub:  scene = Opening(); scene.start(); every frame: scene.update(dt, pygame.event.get()); scene.draw(screen)
                when scene.exit_requested is True -> go to the next scene (Stage 1)."""
import os, sys
import pygame

W, H = 960, 540
ENTER_BTN = pygame.Rect(0, 0, 250, 54)          # "ENTER THE ROOM" button on the last picture (centre of the doorway)
ENTER_BTN.center = (506, 405)
FADE_S = 0.45                                   # cross-fade time between pictures
_HERE = os.path.dirname(os.path.abspath(__file__))
ASSET_DIRS = [os.path.join(os.path.dirname(_HERE), "assets"), os.path.join(_HERE, "assets"), _HERE,
              os.path.join(os.getcwd(), "assets"), os.getcwd()]


def find_pages(max_n=99):
    """1.jpg, 2.jpg, ... in order (also .png / .jpeg / .webp); stops at the first missing number."""
    pages, n = [], 1
    while n <= max_n:
        hit = None
        for d in ASSET_DIRS:
            for ext in (".jpg", ".png", ".jpeg", ".webp"):
                p = os.path.join(d, "%d%s" % (n, ext))
                if os.path.isfile(p): hit = p; break
            if hit: break
        if not hit: break
        pages.append(hit); n += 1
    return pages


def fit(img, w=W, h=H):                         # whole picture visible, black bars if the ratio differs
    iw, ih = img.get_size()
    k = min(w / iw, h / ih)
    out = pygame.transform.smoothscale(img, (max(1, round(iw * k)), max(1, round(ih * k))))
    s = pygame.Surface((w, h)); s.fill((0, 0, 0))
    s.blit(out, ((w - out.get_width()) // 2, (h - out.get_height()) // 2))
    return s


class Opening:
    def __init__(self):
        self.standalone = True
        self.pages = []
        for p in find_pages():
            try: self.pages.append(fit(pygame.image.load(p).convert()))
            except pygame.error as e: print("[open] could not read %s: %s" % (p, e))
        if not self.pages: print("[open] no 1.jpg ... found in", ASSET_DIRS[0])
        self.font = pygame.font.Font(None, 26)
        self.f_btn = pygame.font.Font(None, 36)
        self.go_stage1 = False
        self.start()

    def start(self, handoff=None):
        self.i, self.prev, self.fade, self.t = 0, None, 1.0, 0.0
        self.exit_requested = self.go_stage1 = False
        self.hover = False

    def next(self):
        if self.fade < 1.0:                     # click during a fade -> finish it first
            self.fade = 1.0; return
        if self.i + 1 >= len(self.pages):            # last picture: only the ENTER button (or Space / Enter) goes on
            return
        self.prev, self.i, self.fade = self.i, self.i + 1, 0.0

    def enter(self):
        self.go_stage1 = self.exit_requested = True   # demo_hub: when exit_requested -> start Stage 1

    def on_last(self):
        return bool(self.pages) and self.i == len(self.pages) - 1 and self.fade >= 1.0

    def back(self):
        if self.i > 0: self.prev, self.i, self.fade = self.i, self.i - 1, 0.0

    def update(self, dt, events):
        self.t += dt
        if self.fade < 1.0: self.fade = min(1.0, self.fade + dt / FADE_S)
        if not self.pages: self.exit_requested = True
        for e in events:
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
            if e.type == pygame.MOUSEMOTION:
                self.hover = self.on_last() and ENTER_BTN.collidepoint(e.pos)
            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1:
                    if self.on_last():
                        if ENTER_BTN.collidepoint(e.pos): self.enter()
                    else: self.next()
                elif e.button == 3: self.back()
            elif e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_RIGHT, pygame.K_d):
                    if self.on_last(): self.enter()
                    else: self.next()
                elif e.key in (pygame.K_LEFT, pygame.K_a, pygame.K_BACKSPACE): self.back()
                elif e.key == pygame.K_ESCAPE: self.exit_requested = True

    def draw(self, screen):
        screen.fill((0, 0, 0))
        if not self.pages: return
        cur = self.pages[self.i]
        if self.fade < 1.0 and self.prev is not None:
            screen.blit(self.pages[self.prev], (0, 0))
            cur = cur.copy(); cur.set_alpha(int(255 * self.fade))
        screen.blit(cur, (0, 0))
        last = self.i == len(self.pages) - 1
        if last:
            if self.fade >= 1.0:
                self.hover = ENTER_BTN.collidepoint(pygame.mouse.get_pos())
                pulse = 0.5 + 0.5 * abs((self.t * 1.2) % 2 - 1)
                col = (255, 215, 90) if self.hover else (int(235 + 20 * pulse), int(235 + 20 * pulse), 255)
                bg = (30, 60, 130) if self.hover else (18, 28, 60)
                pygame.draw.rect(screen, bg, ENTER_BTN, border_radius=10)
                pygame.draw.rect(screen, col, ENTER_BTN, 3, border_radius=10)
                t = self.f_btn.render("ENTER THE ROOM", True, col)
                screen.blit(t, t.get_rect(center=ENTER_BTN.center))
        elif int(self.t * 1.6) % 2 == 0:        # blinking hint
            s = self.font.render("click to continue", True, (255, 255, 255)); sh = self.font.render("click to continue", True, (0, 0, 0))
            x, y = W - s.get_width() - 18, H - 30
            screen.blit(sh, (x + 2, y + 2)); screen.blit(s, (x, y))
        n = self.font.render("%d / %d" % (self.i + 1, len(self.pages)), True, (230, 230, 230))
        screen.blit(n, (16, H - 30))


def main():
    pygame.init()
    pygame.display.set_caption("CPE Escape - Opening")
    try: screen = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
    except pygame.error: screen = pygame.display.set_mode((W, H))
    scene, clock = Opening(), pygame.time.Clock()
    while not scene.exit_requested:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        scene.update(dt, pygame.event.get())
        scene.draw(screen)
        pygame.display.flip()
    if scene.go_stage1:
        print("[open] ENTER THE ROOM clicked -> Stage 1 (not linked yet)")
    pygame.quit()


if __name__ == "__main__":
    main()