import os
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import pygame

# 1. Add project and stage 3 paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STAGE3_PATH = os.path.join(PROJECT_ROOT, "onlystage_3")

for path in [PROJECT_ROOT, STAGE3_PATH]:
    if path not in sys.path:
        sys.path.insert(0, path)

# 2. Import Stage 3 modules
try:
    import onlystage_3.settings as C
except ModuleNotFoundError:
    import settings as C

from game import Game as Stage3Core
from level import Level
from render import draw_frame

KEYS = {"left": 1, "a": 1, "right": 2, "d": 2, "space": 4, "up": 4, "w": 4, "e": 8, "return": 16, "escape": 16}

SEG_MAP = {
    "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg",
    "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg",
    "H": "bcefg", "S": "acdfg", "t": "defg", "G": "acdef", "-": "g", " ": "",
}


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


# ---------------- Pygame wrapper for demo_hub.py ----------------
class Game:
    ACTIONS = [("win", "Trigger Graduation (Stage 3 Clear)")]

    def __init__(self):
        self.standalone = True
        self.g = Stage3Core({n: Level(C.ASSETS / f) for n, f in C.MAPS.items()})
        self.f_tiny = pygame.font.Font(None, 16)
        self.f_s = pygame.font.Font(None, 22)
        self.start()

    def start(self, handoff=None):
        self.handoff = dict(handoff) if handoff else {
            "hearts": 3, "form": 2, "armor": 0, "boost": False, "shards": 0
        }
        self.g.new_game()
        if self.g.mode == "ready":
            self.g.mode = "play"
        if hasattr(self.g, "hearts"):
            self.g.hearts = self.handoff.get("hearts", 3)
        if hasattr(self.g, "form"):
            self.g.form = self.handoff.get("form", 2)
        self.acc = 0.0
        self.jumps = 0
        self.skill = False
        self.exit_requested = False

    def get_handoff(self):
        out = dict(self.handoff)
        if hasattr(self.g, "hearts"):
            out["hearts"] = self.g.hearts
        if hasattr(self.g, "form"):
            out["form"] = self.g.form
        return out

    def do_action(self, key):
        if key == "win":
            self.g.stage = max(self.g.maps)
            self.g.gold = True
            self.g.mode = "win"
            self.g.notify("")

    def poll(self, events):
        confirm = False
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.g.mode == "win":
                    confirm = True
            elif e.type == pygame.KEYDOWN:
                k = e.key
                if k in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                    if self.g.mode == "ready":
                        self.g.mode = "play"
                    elif self.g.mode == "play":
                        self.jumps += 1
                    confirm = True
                elif k == pygame.K_e and self.g.mode == "play":
                    self.skill = True
                elif k == pygame.K_r:
                    self.g.restart("Checkpoint restart  /  Skill restored")
                    self.jumps, self.skill, self.acc = 0, False, 0.0
                elif k in (pygame.K_RETURN, pygame.K_ESCAPE):
                    if self.g.mode == "win":
                        confirm = True
                    elif self.g.mode in ("play", "pause"):
                        self.g.mode = "pause" if self.g.mode == "play" else "play"
                        self.jumps, self.skill, self.acc = 0, False, 0.0

        pressed = pygame.key.get_pressed()
        axis = int(bool(pressed[pygame.K_RIGHT] or pressed[pygame.K_d])) - int(
            bool(pressed[pygame.K_LEFT] or pressed[pygame.K_a])
        )
        return {"axis": axis, "confirm": confirm}

    def update(self, dt, ev):
        self.acc = min(0.25, self.acc + dt)
        while self.acc >= C.TICK and self.g.mode in ("play", "clear"):
            self.g.step(C.TICK, ev["axis"], self.jumps > 0, self.skill)
            self.jumps = 0 if self.g.time == 0 else max(0, self.jumps - 1)
            self.skill = False
            self.acc -= C.TICK
        if self.g.mode not in ("play", "clear"):
            self.acc = 0.0
        if self.g.mode == "win" and ev["confirm"]:
            if self.standalone:
                self.start(self.handoff)
            else:
                self.exit_requested = True

    def draw_panel(self, screen):
        scr_w, scr_h = 1152, 648
        y0 = scr_h
        pygame.draw.rect(screen, (24, 26, 32), (0, y0, scr_w, 112))
        pygame.draw.line(screen, (70, 74, 90), (0, y0), (scr_w, y0), 2)

        hearts = getattr(self.g, "hearts", self.handoff.get("hearts", 3))
        cloak = getattr(self.g, "cloak_digit", 0)
        text = f"H{max(0, hearts)} StG3-{cloak}"
        for i, ch in enumerate(text[:8]):
            draw_digit(screen, ch, 14 + i * 40, y0 + 26, 32, 52)

        hint1 = self.f_s.render(
            "A / D: Move   |   W / Space: Jump (x2 Double Jump)   |   E: Skill",
            True,
            (210, 215, 230),
        )
        hint2 = self.f_tiny.render(
            "R: Retry Checkpoint   |   Enter / Esc: Pause   |   F10: Demo Menu",
            True,
            (150, 155, 175),
        )
        screen.blit(hint1, (360, y0 + 30))
        screen.blit(hint2, (360, y0 + 62))

    def draw(self, ui, screen):
        frame = draw_frame(self.g)
        if frame.mode not in ("RGB", "RGBA"):
            frame = frame.convert("RGB")
        surf = pygame.image.fromstring(frame.tobytes(), frame.size, frame.mode)
        ui.blit(pygame.transform.scale(surf, ui.get_size()), (0, 0))
        screen.blit(pygame.transform.smoothscale(ui, (1152, 648)), (0, 0))
        self.draw_panel(screen)


# ---------------- Standalone Tkinter App ----------------
def key_name(event):
    if os.name == "nt" and event.keycode in (65, 68, 69, 87):
        return chr(event.keycode).lower()
    return event.keysym.lower()


class App:
    def __init__(self, root):
        self.root = root
        self.root.report_callback_exception = self.show_error
        self.game = Stage3Core({n: Level(C.ASSETS / f) for n, f in C.MAPS.items()})
        self.keys, self.releases = set(), {}
        self.board = 0
        self.jumps = 0
        self.skill = False
        self.port = None
        self.sent_digit = None
        self.next_refresh = 0.0
        self.last, self.acc = time.perf_counter(), 0.0
        root.title("Digi of Adventure")
        root.configure(bg="#f4efdf")
        self.canvas = tk.Canvas(root, width=960, height=540, bg="#e7faff", highlightthickness=0, takefocus=1)
        self.canvas.pack(fill="both", expand=True)
        self.item = self.canvas.create_image(0, 0, anchor="center")
        self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set())
        bar = ttk.Frame(root, padding=6)
        bar.pack(fill="x")
        ttk.Button(bar, text="Start / Pause", command=self.menu).pack(side="left")
        ttk.Button(bar, text="Retry stage", command=self.retry).pack(side="left")
        ttk.Button(bar, text="New game", command=self.new).pack(side="left")
        self.ports = ttk.Combobox(bar, width=14, state="readonly", postcommand=self.list_ports)
        self.ports.pack(side="right")
        self.connect_button = ttk.Button(bar, text="Connect board", command=self.connect)
        self.connect_button.pack(side="right", padx=5)
        self.status = ttk.Label(
            root,
            text="A / D: Move     W: Jump (tap twice for double jump)     Skill: E     Start / pause: Enter",
            padding=5,
        )
        self.status.pack()
        root.bind("<KeyPress>", self.keydown)
        root.bind("<KeyRelease>", self.keyup)
        root.bind("<FocusOut>", lambda e: root.after_idle(self.check_focus))
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.minsize(640, 432)
        self.canvas.focus_set()
        self.tick()

    def flush(self):
        self.jumps, self.skill, self.acc = 0, False, 0.0
        self.last = time.perf_counter()

    def menu(self):
        g = self.game
        if g.mode == "clear":
            return
        if g.mode == "win":
            g.new_game()
        else:
            g.mode = "pause" if g.mode == "play" else "play"
        self.flush()
        self.canvas.focus_set()

    def retry(self):
        self.game.restart("Checkpoint restart  /  Skill restored")
        self.flush()
        self.canvas.focus_set()

    def new(self):
        self.game.new_game()
        self.flush()
        self.canvas.focus_set()

    def check_focus(self):
        if self.root.focus_displayof() is None:
            self.keys.clear()
            if self.game.mode == "play":
                self.game.mode = "pause"
            self.flush()

    def mask(self):
        bits = self.board
        for key in self.keys:
            bits |= KEYS[key]
        return bits

    def edge(self, old):
        pressed = self.mask() & ~old
        if pressed & 16:
            self.menu()
        elif self.game.mode == "play":
            if pressed & 4:
                self.jumps += 1
            if pressed & 8:
                self.skill = True

    def keydown(self, event):
        key = key_name(event)
        if key not in KEYS or event.widget is self.ports:
            return
        if key in self.releases:
            timer, release_time = self.releases.pop(key)
            self.root.after_cancel(timer)
            if event.time != release_time:
                self.keys.discard(key)
        old = self.mask()
        first_press = key not in self.keys
        self.keys.add(key)
        if key == "space" and first_press and self.game.mode == "ready":
            self.menu()
        else:
            self.edge(old)
        return "break"

    def keyup(self, event):
        key = key_name(event)
        if key not in KEYS:
            return

        def release():
            self.keys.discard(key)
            self.releases.pop(key, None)

        if key not in self.releases:
            self.releases[key] = (self.root.after_idle(release), event.time)
        return "break"

    def list_ports(self):
        try:
            from serial.tools import list_ports
            devices = [p.device for p in list_ports.comports()]
        except ImportError:
            devices = []
        self.ports["values"] = devices
        if devices and self.ports.get() not in devices:
            self.ports.set(devices[0])

    def disconnect(self):
        if self.port:
            try:
                self.port.close()
            except OSError:
                pass
        self.port, self.board = None, 0
        self.connect_button.configure(text="Connect board")

    def connect(self):
        if self.port:
            self.disconnect()
            self.status.configure(text="Keyboard ready")
            return
        self.list_ports()
        try:
            import serial
            if not self.ports.get():
                raise ValueError("No serial port found. Connect the programmed Nexys board.")
            self.port = serial.Serial(self.ports.get(), 115200, timeout=0, write_timeout=0.05)
            self.sent_digit = None
            self.port.reset_input_buffer()
            self.connect_button.configure(text="Disconnect board")
            self.status.configure(text="Nexys connected   |   BTNL / BTNR: Move    BTNU: Jump    BTNC: Skill    BTND: Start / pause")
            self.canvas.focus_set()
        except (ImportError, OSError, ValueError) as exc:
            messagebox.showerror("Nexys connection", str(exc))

    def display_skill(self, now):
        if not self.port:
            return
        digit = self.game.cloak_digit
        if digit == self.sent_digit and now < self.next_refresh:
            return
        try:
            if self.port.write(bytes([0xD0 | digit])) == 1:
                self.sent_digit = digit
                self.next_refresh = now + 0.25
        except OSError:
            self.disconnect()
            self.status.configure(text="Board disconnected  /  keyboard ready")

    def tick(self):
        now = time.perf_counter()
        self.acc += min(0.25, now - self.last)
        self.last = now
        if self.port:
            try:
                for byte in self.port.read(self.port.in_waiting):
                    if byte & 224 == 160:
                        old = self.mask()
                        self.board = byte & 31
                        self.edge(old)
            except OSError:
                self.disconnect()
                self.status.configure(text="Board disconnected  /  keyboard ready")
        while self.acc >= C.TICK and self.game.mode in ("play", "clear"):
            bits = self.mask()
            axis = int(bool(bits & 2)) - int(bool(bits & 1))
            self.game.step(C.TICK, axis, self.jumps > 0, self.skill)
            self.jumps = 0 if self.game.time == 0 else max(0, self.jumps - 1)
            self.skill = False
            self.acc -= C.TICK
        if self.game.mode not in ("play", "clear"):
            self.acc = 0
        self.display_skill(now)
        frame = draw_frame(self.game)
        w, h = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        scale = min(w / 640, h / 360)
        frame = frame.resize((max(1, round(640 * scale)), max(1, round(360 * scale))), Image.Resampling.NEAREST)
        self.photo = ImageTk.PhotoImage(frame)
        self.canvas.coords(self.item, w / 2, h / 2)
        self.canvas.itemconfigure(self.item, image=self.photo)
        self.root.after(10, self.tick)

    def show_error(self, error_type, error, traceback):
        messagebox.showerror("Digi of Adventure", str(error), parent=self.root)
        self.close()

    def close(self):
        self.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        app = App(root)
        root.mainloop()
    except (OSError, ValueError, KeyError) as err:
        messagebox.showerror("Digi of Adventure", str(err))
        root.destroy()
        raise