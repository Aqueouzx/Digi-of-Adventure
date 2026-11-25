#!/usr/bin/env python3
# PC DEMO ONLY - not FPGA code. Gameplay prototype of Stage 1 (Final Exam), 16:9.
# Optional images in ../assets/ :
#   finalexam.jpg (the room picture, any 16:9 size)
#   player_form{0-3}_{front|back|left|right}_{stand|stepl|stepr}.png (transparent PNG, see player_sprite.py)
#   closeup_<id>.png (16:9)  ids: whiteboard paper laptop3 laptop4 screen projector pc lightsw door keypad box shelf
# Missing files -> placeholders, the game still runs.
import itertools, math, os, sys, time
import pygame
import player_sprite
import card_assets


SCR_W, SCR_H, PANEL_H = 1152, 648, 112      # window: game area 16:9 + virtual board panel
UW, UH = 960, 540                           # internal UI surface (16:9), scaled up to the window
WINDOW_SIZE = (SCR_W, SCR_H + PANEL_H)
UI_SIZE = (UW, UH)
IMG_W, IMG_H = 2000, 1116                   # WORLD coordinates = pixels of the room picture
VIEW_W = 1000.0                             # how much of the room the camera sees (zoom 2x)
VIEW_H = VIEW_W * UH / UW
ZOOM = UW / VIEW_W
FEET_HW, FEET_H = 18, 22                    # player collision box (feet)
SPR_W, SPR_H = 46, 96
BASE_SPEED = 360.0                          # world px / second
LONG_PRESS_S = 0.8
ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

# ---- design switches ----
HINT_BY_TRUTH = True     # True: smart hint looks at the real right/wrong state (leaks which puzzle is wrong)
                         # False: smart hint only looks at "has the player answered it yet"
SHOW_P3_TARGET = False   # True: laptop 3 also shows the target truth table

# ---------------- puzzle data (same numbers as the RTL design) ----------------
ANS_A = 0x2A - 0b10011 - 0o21                    # 42 - 19 - 17 = 6
P2_TRUTH = 0xF888                                # F = AB + CD
ANS_B = bin(P2_TRUTH).count("1")                 # 7
P4_ANSWER = 0b11110100                           # -12 in 8-bit two's complement (-12 from decimal 12)
ANS_C = bin(P4_ANSWER).count("1")                # 5
PC_PASS = "CPE"                                  # Canva, Pinterest, Explorer -> C, P, E
L1_CODE = [int(c) for c in str(ord(PC_PASS[-1]))]            # 'E' = 69 -> [6, 9]
_S = ANS_A + ANS_B + ANS_C
_PRE = [ANS_A, ANS_B, ANS_C, _S // 10, _S % 10]             # 6 7 5 1 8
CODE2 = [_PRE[i] for i in (3, 1, 4, 0, 2)]                  # order 4-2-5-1-3 -> 1 7 8 6 5
GRAY = [0, 1, 3, 2]
SRC_NAMES = ["A", "B", "C", "D", "G1", "G2", "G3"]
APP_LOGOS = ["Canva", "Pinterest", "Explorer", "AppStore", "X (Twitter)", "Facebook"]
PC_APP_ANS = [0, 1, 2] # C, P, E indices

# ---------------- walkable floor + blockers (WORLD px, measured from room.png) ----------------
FLOOR_TOP, FLOOR_BOT = 360, 1085
def floor_left(y): return 600 - 0.76 * (y - 355)
def floor_right(y): return 1440 + 0.714 * (y - 350)

BLOCKERS = [                                   # floor footprints (x, y, w, h)
    pygame.Rect(620, 300, 200, 70),            # grey cabinet
    pygame.Rect(815, 250, 140, 120),           # shelf
    pygame.Rect(450, 440, 125, 120),           # lockers (left wall)
    pygame.Rect(100, 880, 160, 125),           # low cabinet (bottom-left)
    pygame.Rect(660, 420, 650, 120),           # table row 1 (back)
    pygame.Rect(520, 615, 850, 150),           # table row 2
    pygame.Rect(380, 860, 1080, 170),          # table row 3 (front)
    pygame.Rect(1490, 525, 225, 250),          # teacher desk
]
SPAWN = (1300.0, 405.0)

# ---------------- hints / items / cards ----------------
HINTS = {
    "P1": "10",
    "P2": "Circle the 1s in the biggest groups you can. Two groups are enough.",   # TODO: write your own
    "P3": "De Morgan",
    "P4": "00001100",
    "P5": "It takes greater faith to dance in the dark than to rest in light.",
}
HINT_ORDER = (2, 1, 0, 3)          # smart hint priority after P5: P3 -> P2 -> P1 -> P4

# Round 1 is FIXED: card colour index 0 = green, 1 = yellow, 2 = red (see CAREERS)
#   green = Hint (P3), yellow = Hint (P3), red = Armor
CARD_ITEMS = {1: ["HINT_HARD", "HINT_HARD", "ARMOR"],
              2: ["SHARD", "SLOW", "HINT_SMART"],
              3: ["FREEZE", "UNDO", "SHARD"]}
# Description here is the default text. Hints, Undo and Shard get their text from grant().
ITEM_TEXT = {
    "HINT_HARD": ("Hint", ""),
    "BOOST": ("Speed Boost", "Saved for later stages."),
    "ARMOR": ("Armor", "Blocks the next wrong code penalty."),
    "SHARD": ("Armor Shard", "Collect 2 shards to forge 1 Armor."),
    "SLOW": ("Slow", "You walk slower for 10 seconds."),
    "HINT_SMART": ("Hint", ""),
    "FREEZE": ("Freeze", "Moving obstacles stop for 5 seconds."),
    "UNDO": ("Undo", ""),
}
CAREERS = [("AIR", (60, 170, 80)), ("EARTH", (220, 190, 50)), ("WATER", (200, 60, 60))]
SYMBOLS = [["WING", "PLANE", "FART"], ["SHIP", "GEAR", "MONEY"], ["WORM", "WHITE FLAG", "PLUG"]]
PERMS = list(itertools.permutations([0, 1, 2]))
FORM_COLORS = [(60, 110, 220), (240, 240, 240), (35, 35, 35), (240, 200, 60)]
FORM_NAMES = ["Student uniform", "Lab coat", "Graduation gown", "Super Yasai"]

SEG_MAP = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg", "6": "acdefg",
           "7": "abc", "8": "abcdefg", "9": "abcdfg", "H": "bcefg", "-": "g", " ": "", "E": "adefg",
           "P": "abefg", "C": "adef", "A": "abcefg", "F": "aefg", "L": "def", "O": "abcdef",
           "U": "bcdef", "d": "bcdeg", "S": "acdfg"}


class Obj:
    def __init__(self, oid, kind, name, ax, ay, r, rect, desc="", hidden=None, collect=None):
        self.id, self.kind, self.name = oid, kind, name
        self.ax, self.ay, self.r = ax, ay, r
        self.rect = pygame.Rect(rect)
        self.desc, self.hidden, self.collect = desc, hidden, collect


OBJS = [
    Obj("whiteboard", "whiteboard", "Whiteboard", 300, 580, 180, (165, 180, 235, 510)),
    Obj("paper", "paper", "Paper on the cabinet", 700, 400, 130, (640, 170, 70, 100)),
    Obj("laptop3", "nand", "Laptop 1", 1370, 920, 160, (1215, 870, 115, 115)),
    Obj("laptop4", "twos", "Laptop 2", 570, 690, 150, (665, 600, 115, 95)),
    Obj("projector", "screen", "Projector screen", 1560, 400, 120, (1600, 170, 230, 540)),
    Obj("pc", "pc", "Teacher computer", 1540, 650, 120, (1500, 565, 70, 95)),
    Obj("lightsw", "lightsw", "Light switch", 1150, 310, 100, (1125, 195, 26, 28)),
    Obj("door", "door", "Exit door", 1340, 300, 120, (1210, 110, 180, 240)),
]
PAGED = ("whiteboard", "paper", "nand", "twos", "pc")


def term_str(used, pol):
    return "".join("ABCD"[i] + ("" if pol[i] else "'") for i in range(4) if used[i])


def p2_table(slots):
    t = 0
    for m in range(16):
        v = [(m >> 3) & 1, (m >> 2) & 1, (m >> 1) & 1, m & 1]
        f = 0
        for used, pol in slots:
            if any(used) and all(v[i] == int(pol[i]) for i in range(4) if used[i]):
                f = 1
        t |= f << m
    return t


def p3_table(f):
    t = 0
    for m in range(16):
        v = [(m >> 3) & 1, (m >> 2) & 1, (m >> 1) & 1, m & 1]
        g = []
        for k in range(4):
            src = v + g
            g.append(1 - (src[f[2 * k]] & src[f[2 * k + 1]]))
        if g[f[8]]:
            t |= 1 << m
    return t


def bits16(t):
    return " ".join("".join(str((t >> (g * 4 + i)) & 1) for i in range(4)) for g in range(4))


def load_img(name, size=None):
    path = os.path.join(ASSET_DIR, name)
    if not os.path.isfile(path):
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(img, size) if size else img
    except (pygame.error, ValueError):
        return None


def draw_digit(scr, ch, x, y, w, h):
    t = max(3, w // 6)
    h2 = h // 2
    segs = {"a": (x + t, y, w - 2 * t, t), "b": (x + w - t, y + t, t, h2 - t),
            "c": (x + w - t, y + h2, t, h2 - t), "d": (x + t, y + h - t, w - 2 * t, t),
            "e": (x, y + h2, t, h2 - t), "f": (x, y + t, t, h2 - t),
            "g": (x + t, y + h2 - t // 2, w - 2 * t, t)}
    on = SEG_MAP.get(ch, "g")
    for k, r in segs.items():
        pygame.draw.rect(scr, (255, 60, 40) if k in on else (50, 22, 22), r)


def sw_cx(i):
    return 360 + (15 - i) * 48 + 22


class Game:
    # ---- demo hub interface (only used by demo_hub.py) ----
    CHECKPOINTS = [("start", "Start of stage (card round 1)"),
                   ("r2", "3 puzzles answered (card round 2)"),
                   ("r3", "All 5 puzzles answered (card round 3)"),
                   ("door", "All cards done, at the door"),
                   ("clear", "Stage 1 cleared")]
    ACTIONS = [("door_wrong", "At the door, test an incorrect door code"),
               ("armor", "Give 1 Armor")]

    def __init__(self):
        self.f_tiny = pygame.font.Font(None, 15)
        self.f_s = pygame.font.Font(None, 20)
        self.f_m = pygame.font.Font(None, 26)
        self.f_l = pygame.font.Font(None, 38)
        mono = "dejavusansmono,consolas,menlo,couriernew"
        self.f_mono = pygame.font.SysFont(mono, 17)
        self.f_mono_l = pygame.font.SysFont(mono, 25)
        self.bg = load_img("finalexam.jpg", (int(IMG_W * ZOOM), int(IMG_H * ZOOM)))
        self.sprite = player_sprite.PlayerSprite(ASSET_DIR, int(SPR_H * ZOOM))
        self.cu_cache = {}
        self.app_logo_cache = {}
        self.sw = [False] * 16
        self.sw[15] = True  # SW15 = Help (startup guide is open)
        self.sw_rects = [pygame.Rect(sw_cx(i) - 20, SCR_H + 36, 40, 34) for i in range(16)]
        self.c_down, self.c_long = None, False
        self.lfsr = (int(time.time() * 1000) & 0xFFFF) or 0xACE1
        self.debug = False
        self.show_help = True
        self.standalone = True          # demo hub sets this to False
        self.form = 0
        self.reset_stage(True)
        self.card_art = card_assets.CardAssets(ASSET_DIR, (170, 170))


    def reset_stage(self, full=False):
        if full:
            self.form = 0
        self.px, self.py = SPAWN
        self.sprite.reset()
        self.mode, self.cur, self.page, self.cmsg = "map", None, 0, ""
        self.feedback = None  # None=neutral, True=correct, False=incorrect
        self.notebook_guide_pending = False
        self.notebook_guide_seen = False
        self.state = "play"
        self.exit_requested = False
        self.lights = True
        # Puzzle state. done/right become True only after a correct answer is confirmed.
        self.done = [False] * 5
        self.right = [False] * 5
        self.ans = {"A": None, "B": None, "C": None}      # what the notebook shows
        self.undo_rec = None
        self.p2 = [([False] * 4, [False] * 4) for _ in range(3)]
        self.p2_cur, self.p2_eq = 0, ""
        self.p3, self.p3_cur = [0] * 9, 0
        self.p5, self.p5_cur, self.p5_seen = [0, 0, 0], 0, False
        self.ostate = {o.id: {"revealed": False, "collected": False} for o in OBJS}
        self.notes, self.hints_seen = [], []
        # immediate effects
        self.armor = 0
        self.slow_t = 0.0
        self.freeze_t = 0.0
        # backend inventory (never shown on screen, handed to later stages)
        self.inv = {"boost": False, "shard": 0}
        self.hearts = 3
        self.door_layer, self.door_digits, self.door_cur = 0, [0] * 5, 0
        self.deck = {"active": False, "round": 1, "perm": (0, 1, 2), "cursor": 1, "face": None,
                     "name": "", "desc": ""}
        self.career = None
        self.r_run = {1: False, 2: False, 3: False}
        self.r_done = {1: False, 2: False, 3: False}
        self.toast = ("", 0)
        self.flash, self.over_until = 0.0, 0.0

    def say(self, text, secs=2.5):
        self.toast = (text, time.time() + secs)

    # ---------------- demo hub hooks ----------------
    def start(self, handoff=None):
        self.reset_stage(True)
        self.show_help = False
        self.sw[15] = False

    def get_handoff(self):
        return {
            "hearts": self.hearts, 
            "form": self.form, 
            "armor": self.armor,
            "boost": self.inv["boost"], 
            "shards": self.inv["shard"],
            "career": self.career  # สำคัญมาก ตัวนี้คือตัวส่งต่อสีและหมวดหมู่ครับ
        }


    def get_inventory(self):
        return {"boost": self.inv["boost"], "shards": self.inv["shard"], "armor": self.armor}

    def get_progress(self):
        if self.state == "clear": return 4
        if self.r_done[3]: return 3
        if self.r_run[3]: return 2
        if self.r_run[2]: return 1
        return 0

    def set_hearts(self, n):
        self.hearts = max(1, min(3, n))
        if self.state == "over": self.state = "play"

    def set_form(self, i):
        self.form = max(0, min(3, i))

    def toggle_debug(self):
        self.debug = not self.debug

    def auto_answer(self, i):
        """Demo helper: fill puzzle i exactly as a perfect player would."""
        if i == 0:
            self.ans["A"] = ANS_A
        elif i == 1:
            self.p2 = [([True, True, False, False], [True, True, False, False]),
                       ([False, False, True, True], [False, False, True, True]),
                       ([False] * 4, [False] * 4)]
            self.p2_eq = "AB + CD"
        elif i == 2:
            self.p3 = [0, 1, 2, 3, 4, 5, 0, 0, 2]          # G1=NAND(A,B) G2=NAND(C,D) G3=NAND(G1,G2) F=G3
            self.ans["B"] = ANS_B
        elif i == 3:
            self.ans["C"] = ANS_C
        elif i == 4:
            self.p5 = [2, 15, 4]                           # C P E
        self.done[i] = self.right[i] = True

    def jump_to(self, key):
        form = self.form
        
        # --- [จุดที่แก้] บันทึกค่า career เดิมไว้ ถ้ายังไม่มีให้สุ่ม 0, 1 หรือ 2 แทนที่จะฟิกซ์เป็น 0 ---
        if self.career is None:
            self.career = 1  # หรือใช้การสุ่มเช่น (int(time.time()) % 3)
            
        current_career = self.career
        
        self.reset_stage(True)
        self.form = form
        self.career = current_career  # ล็อคค่าหมวดหมู่เดิมไว้ ไม่ให้ถูกรีเซ็ตทิ้ง
        self.show_help = False
        self.sw[15] = False
        
        if key == "start":
            return
        if key == "clear":
            self.state, self.form = "clear", 1
            return
            
        for i in range(3 if key == "r2" else 5):
            self.auto_answer(i)
            
        # ลบหรือคอมเมนต์บรรทัดนี้ออก: self.career = 0  <--- (ตัวการที่ทำให้เป็น Air ทุกรอบ)
        
        self.add_hint("P3")
        self.r_run[1] = self.r_done[1] = True
        if key in ("r3", "door"):
            self.r_run[2] = self.r_done[2] = True
        if key == "door":
            self.r_run[3] = self.r_done[3] = True

    def do_action(self, key):
        if key == "armor":
            self.armor = min(3, self.armor + 1)
            self.say("Armor +1")
        elif key == "door_wrong":
            self.jump_to("door")
            # Test a wrong door entry without writing an incorrect value to the Notebook.
            self.door_digits = [9, 9, 9, 9, 9]

    # ---------------- input ----------------
    
    def find_near(self):
        # ค้นหาวัตถุที่ตัวละครเดินไปยืนใกล้ๆ (รัศมี r)
        best, bs = None, 9.0
        for o in OBJS:
            # คำนวณระยะห่างระหว่างตัวละครกับวัตถุ
            score = math.hypot(self.px - o.ax, self.py - o.ay) / o.r
            if score <= 1.0 and score < bs:
                best, bs = o, score
        return best
    
    
    def poll(self, events):
        ev = dict(up=0, down=0, left=0, right=0, tap=0, back=0)
        now = time.time()
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.MOUSEBUTTONDOWN:
                for i, r in enumerate(self.sw_rects):
                    if r.collidepoint(e.pos):
                        self.sw[i] = not self.sw[i]
                        if i == 15:
                            self.show_help = self.sw[15]
                        if self.mode == "closeup" and self.cur and self.cur.kind in ("whiteboard", "paper", "twos"):
                            self.clear_feedback()
            if e.type == pygame.KEYDOWN:
                k = e.key
                if k in (pygame.K_UP, pygame.K_w): ev["up"] = 1
                elif k in (pygame.K_DOWN, pygame.K_s): ev["down"] = 1
                elif k in (pygame.K_LEFT, pygame.K_a): ev["left"] = 1
                elif k in (pygame.K_RIGHT, pygame.K_d): ev["right"] = 1
                elif k in (pygame.K_SPACE, pygame.K_RETURN):
                    if self.c_down is None:
                        self.c_down, self.c_long = now, False
                elif k in (pygame.K_ESCAPE, pygame.K_BACKSPACE): ev["back"] = 1
                elif pygame.K_1 <= k <= pygame.K_8:
                    self.sw[k - pygame.K_1] = not self.sw[k - pygame.K_1]
                    if self.mode == "closeup" and self.cur and self.cur.kind in ("whiteboard", "paper", "twos"):
                        self.clear_feedback()
                elif k == pygame.K_n: self.sw[14] = not self.sw[14]  # PC demo alias for SW14
                elif k == pygame.K_h:
                    self.sw[15] = not self.sw[15]  # PC demo alias for SW15
                    self.show_help = self.sw[15]
                elif k in (pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4): self.form = k - pygame.K_F1
                elif k == pygame.K_F5: self.cheat_solve()
                elif k == pygame.K_F6: self.debug = not self.debug
            if e.type == pygame.KEYUP and e.key in (pygame.K_SPACE, pygame.K_RETURN):
                if self.c_down is not None and not self.c_long:
                    ev["tap"] = 1
                self.c_down = None
        if self.c_down is not None and not self.c_long and now - self.c_down >= LONG_PRESS_S:
            self.c_long = True
            ev["back"] = 1
        return ev

    def cheat_solve(self):
        for i in range(5):
            if not self.done[i]:
                self.auto_answer(i)
                self.say("[DEBUG] puzzle %d answered" % (i + 1))
                return

    def lfsr_step(self):
        q = self.lfsr
        fb = ((q >> 15) ^ (q >> 14) ^ (q >> 12) ^ (q >> 3)) & 1
        q = ((q << 1) | fb) & 0xFFFF
        self.lfsr = q if q else 0xACE1

    # ---------------- cards ----------------
    # One source of truth: card position -> perm -> colour index -> item. Name, text and effect all use card_item().
    def card_start(self, r):
        while True:
            self.lfsr_step()
            v = self.lfsr & 7
            if v < 6:
                break
        self.deck = {"active": True, "round": r, "perm": PERMS[v], "cursor": 1,
                     "face": None, "name": "", "desc": ""}
        self.r_run[r] = True

    def card_trigger(self):
        if self.deck["active"]:
            return
        n = sum(self.done)
        if not self.r_run[1]: self.card_start(1)
        elif self.r_done[1] and not self.r_run[2] and n >= 3: self.card_start(2)
        elif self.r_done[2] and not self.r_run[3] and n == 5: self.card_start(3)

    def card_item(self, pos):
        d = self.deck
        return CARD_ITEMS[d["round"]][d["perm"][pos]]

    def cards_input(self, ev):
        d = self.deck
        if d["face"] is None:
            if ev["left"]: d["cursor"] = (d["cursor"] - 1) % 3
            elif ev["right"]: d["cursor"] = (d["cursor"] + 1) % 3
            elif ev["tap"]:
                d["face"] = d["cursor"]
                if d["round"] == 1: self.career = d["perm"][d["cursor"]]
                item = self.card_item(d["cursor"])
                d["name"] = ITEM_TEXT[item][0]
                d["desc"] = self.grant(item)          # effect happens now, returns the text to show
        elif ev["tap"]:
            d["active"] = False
            self.r_done[d["round"]] = True

    # ---------------- item effects ----------------
    def passed(self, i):
        return self.right[i] if HINT_BY_TRUTH else self.done[i]

    def smart_hint(self):
        if not self.done[4]:                       # puzzle 5 not done yet -> always P5
            return "P5"
        for idx in HINT_ORDER:                     # then the hardest unfinished one: P3 -> P2 -> P1 -> P4
            if not self.passed(idx):
                return "P%d" % (idx + 1)
        return None

    def add_hint(self, key):
        if HINTS[key] not in self.hints_seen:
            self.hints_seen.append(HINTS[key])

    def apply_undo(self):
        r = self.undo_rec
        if not r:
            return "Nothing to undo right now."
        i = r["i"]
        self.ans = r["ans"]
        self.done[i], self.right[i] = r["done"], r["right"]
        if i == 1 and not self.done[1]: self.p2_eq = ""
        self.undo_rec = None
        return "Your latest answer (Puzzle %d) was undone." % (i + 1)

    def grant(self, item):
        """Apply the card effect immediately. Returns the description shown on the card."""
        cap = lambda v: min(3, v + 1)
        if item == "HINT_HARD":
            self.add_hint("P3")
            return HINTS["P3"]
        if item == "HINT_SMART":
            key = self.smart_hint()
            if key is None: return "No hint this time. Keep going!"
            self.add_hint(key)
            return HINTS[key]
        if item == "UNDO":
            return self.apply_undo()
        if item == "ARMOR":
            self.armor = cap(self.armor)
        elif item == "SLOW":
            self.slow_t = 10.0
        elif item == "FREEZE":
            self.freeze_t = 5.0
        elif item == "BOOST":
            self.inv["boost"] = True
        elif item == "SHARD":
            self.inv["shard"] += 1
            if self.inv["shard"] >= 2:
                self.inv["shard"] = 0
                self.armor = cap(self.armor)
                return "2 shards forged 1 Armor!"
            return "Armor Shard 1 / 2 (saved for later)."
        return ITEM_TEXT[item][1]

    # ---------------- answer validation / notebook ----------------
    def clear_feedback(self):
        self.feedback = None
        self.cmsg = ""

    def commit(self, i, correct, msg=None, key=None, value=None, note=None,
               *, correct_msg=None, wrong_msg=None):
        """Validate an answer; only correct answers update progress and Notebook.

        `msg` is retained for compatibility with older calls.
        New calls should provide separate `correct_msg` and `wrong_msg`.
        """
        if correct_msg is None:
            correct_msg = msg or "Your answer is correct."
        if wrong_msg is None:
            wrong_msg = msg or "Your answer is not correct. Please try again."

        if not correct:
            # A wrong retry must never erase an answer that was already solved.
            if not self.done[i]:
                self.right[i] = False
            self.feedback = False
            self.cmsg = "INCORRECT! " + wrong_msg
            self.say("Incorrect - try again", 2.5)
            return False

        # Store the previous answer state for the Undo item.
        self.undo_rec = {
            "i": i,
            "ans": dict(self.ans),
            "done": self.done[i],
            "right": self.right[i]
        }

        if key is not None:
            self.ans[key] = value

        self.done[i], self.right[i] = True, True

        # Notebook entries are added only after validation succeeds.
        if note and note not in self.notes:
            self.notes.append(note)

        # The first solved A/B/C puzzle introduces the Notebook and its saved answers.
        if i in (0, 2, 3) and not self.notebook_guide_seen:
            self.notebook_guide_pending = True

        self.feedback = True
        self.cmsg = "CORRECT! " + correct_msg
        self.say("Puzzle %d correct - saved to Notebook" % (i + 1), 2.5)
        return True

    def door_damage(self):
        if self.armor > 0:
            self.armor -= 1
            self.say("ARMOR PROTECTED!")
            return
        self.hearts -= 1
        self.flash = 0.4
        if self.hearts <= 0:
            self.state, self.over_until = "over", time.time() + 3.0
        else:
            self.say("Wrong code! -1 heart")

    def door_confirm(self):
        n = 2 if self.door_layer == 0 else 5
        want = L1_CODE if self.door_layer == 0 else CODE2
        if self.door_digits[:n] == want:
            self.door_digits, self.door_cur = [0] * 5, 0
            if self.door_layer == 0:
                self.door_layer = 1
                self.cmsg = "LOCK 1 OPEN. Now the 5-digit lock."
            else:
                self.state, self.form = "clear", 1
        else:
            self.cmsg = "WRONG CODE"
            self.door_damage()

    def update(self, dt, ev):
        for _ in range(7): self.lfsr_step()
        self.flash = max(0.0, self.flash - dt)
        if self.show_help:
            if ev["tap"] or ev["back"]:
                self.show_help = False
                self.sw[15] = False
            return
        if self.notebook_guide_pending:
            if self.sw[14]:
                self.notebook_guide_pending = False
                self.notebook_guide_seen = True
            else:
                self.sprite.stop()
                return
        if self.state == "clear":
            if ev["tap"]:
                if self.standalone: self.reset_stage(True)
                else: self.exit_requested = True
            return
        if self.state == "over":
            if time.time() > self.over_until: self.reset_stage()
            return
        self.slow_t = max(0.0, self.slow_t - dt)
        self.freeze_t = max(0.0, self.freeze_t - dt)
        self.card_trigger()
        if self.deck["active"]:
            self.sprite.stop(); self.cards_input(ev); return
        if self.sw[14]:
            self.sprite.stop(); return
        if self.mode == "map": self.map_update(dt, ev)
        else:
            self.sprite.stop(); self.closeup_input(ev)

    def speed(self):
        s = BASE_SPEED * (1.2 if self.form >= 1 else 1.0)
        return s * 0.5 if self.slow_t > 0 else s

    def blocked(self, x, y):
        r = pygame.Rect(int(x) - FEET_HW, int(y) - FEET_H, FEET_HW * 2, FEET_H)
        for cx_, cy_ in ((r.left, r.top), (r.right, r.top), (r.left, r.bottom), (r.right, r.bottom)):
            if cy_ < FLOOR_TOP or cy_ > FLOOR_BOT or cx_ < floor_left(cy_) or cx_ > floor_right(cy_):
                return True
        return any(r.colliderect(b) for b in BLOCKERS)

    def find_near(self):
        bonus = 30 if self.form >= 1 else 0
        best, bs = None, 9.0
        for o in OBJS:
            score = math.hypot(self.px - o.ax, self.py - o.ay) / (o.r + bonus)
            if score <= 1.0 and score < bs:
                best, bs = o, score
        return best

    def map_update(self, dt, ev):
        k = pygame.key.get_pressed()
        dx = int(k[pygame.K_RIGHT] or k[pygame.K_d]) - int(k[pygame.K_LEFT] or k[pygame.K_a])
        dy = int(k[pygame.K_DOWN] or k[pygame.K_s]) - int(k[pygame.K_UP] or k[pygame.K_w])
        sp = self.speed() * dt
        ox, oy = self.px, self.py
        if not self.blocked(self.px + dx * sp, self.py): self.px += dx * sp
        if not self.blocked(self.px, self.py + dy * sp): self.py += dy * sp
        self.sprite.update(dt, dx, dy, (self.px, self.py) != (ox, oy))
        if ev["tap"]:
            o = self.find_near()
            if o:
                self.mode, self.cur, self.page, self.cmsg = "closeup", o, 0, ""
                self.feedback = None
                self.sprite.stop()
                if o.kind == "screen" and not self.lights: self.p5_seen = True

    def p1_val(self): return sum(1 << i for i in range(4) if self.sw[i])
    def p4_val(self): return sum(1 << i for i in range(8) if self.sw[i])

    def closeup_input(self, ev):
        o = self.cur
        if ev["back"]:
            if self.page > 0 and o.kind in PAGED:
                self.page -= 1
            else:
                self.mode = "map"
            self.cmsg = ""
            return
        getattr(self, "in_" + o.kind)(ev)

    def in_plain(self, ev):
        o, st = self.cur, self.ostate[self.cur.id]
        if not ev["tap"]: return
        if o.hidden and not st["revealed"]:
            st["revealed"] = True
        elif o.collect and st["revealed"] and not st["collected"]:
            st["collected"] = True
            self.notes.append(o.collect)
            self.say("Clue added to notebook (N).")

    # ---- puzzle 1 ----
    def in_whiteboard(self, ev):
        if self.page == 0:
            if ev["tap"]: self.page = 1
        elif ev["tap"]:
            val = self.p1_val()
            self.commit(
                0,
                val == ANS_A,
                key="A",
                value=val,
                correct_msg="The base-conversion answer is correct. Puzzle 1 is complete.",
                wrong_msg="The base-conversion answer is incorrect. Check your calculation and try again.",
                note="P1 correct answer: A = %d" % val
            )

    # ---- puzzle 2 ----
    def in_paper(self, ev):
        if self.page == 0:
            if ev["tap"]:
                self.page = 1
            return

        if ev["up"]:
            self.clear_feedback()
            self.p2_cur = (self.p2_cur - 1) % 3

        elif ev["down"]:
            self.clear_feedback()
            self.p2_cur = (self.p2_cur + 1) % 3

        elif ev["tap"]:
            self.clear_feedback()

            u = [self.sw[7 - i] for i in range(4)]
            p = [self.sw[3 - i] for i in range(4)]

            self.p2[self.p2_cur] = (u, p)

            self.cmsg = (
                "Stored in Term%d. "
                "Continue setting the other terms, then press BTNR to check."
                % (self.p2_cur + 1)
            )

        elif ev["right"]:
            terms = [(u, p) for u, p in self.p2 if any(u)]

            if not terms:
                self.feedback = False
                self.cmsg = (
                    "INCORRECT! No terms have been stored yet. "
                    "Please create your K-map expression first."
                )

            else:
                lits = sum(sum(u) for u, _ in terms)
                ok = p2_table(self.p2) == P2_TRUTH and lits <= 4

                self.p2_eq = " + ".join(
                    term_str(u, p) for u, p in terms
                )

                self.commit(
                    1,
                    ok,
                    correct_msg=(
                        "Your K-map expression is correct. "
                        "You can use this to solve the next puzzle."
                    ),
                    wrong_msg=(
                        "Your K-map expression is not correct. "
                        "Check your variables and terms, then try again."
                    ),
                    note="P2 correct answer: F = " + self.p2_eq
                )

    # ---- puzzle 3 ----
    def in_nand(self, ev):
        if self.page == 0:
            if ev["tap"]: self.page = 1
            return
        c = self.p3_cur
        if ev["left"]:
            self.clear_feedback()
            self.p3_cur = (c - 1) % 9
        elif ev["right"]:
            self.clear_feedback()
            self.p3_cur = (c + 1) % 9
        elif ev["up"] or ev["down"]:
            self.clear_feedback()
            n = 4 if c == 8 else 4 + c // 2
            self.p3[c] = (self.p3[c] + (1 if ev["up"] else -1)) % n
        elif ev["tap"]:
            t = p3_table(self.p3)
            self.commit(
                2,
                t == P2_TRUTH,
                key="B",
                value=bin(t).count("1"),
                correct_msg="The NAND circuit produces the correct truth table. Puzzle 3 is complete.",
                wrong_msg="The NAND circuit output does not match the required truth table. Check the connections and try again.",
                note="P3 correct circuit: NAND-only output matches the K-map."
            )

    # ---- puzzle 4 ----
    def in_twos(self, ev):
        if self.page == 0:
            if ev["tap"]: self.page = 1
        elif ev["tap"]:
            val = self.p4_val()
            self.commit(
                3,
                val == P4_ANSWER,
                key="C",
                value=bin(val).count("1"),
                correct_msg="The two's-complement value is correct. Puzzle 4 is complete.",
                wrong_msg="The binary value is incorrect. Check the two's-complement conversion and try again.",
                note="P4 correct answer: 11110100 (unsigned 244 / signed -12)."
            )

    def in_lightsw(self, ev):
        if ev["tap"]:
            self.lights = not self.lights
            self.say("Lights ON" if self.lights else "Lights OFF")

    def in_screen(self, ev): pass

    # ---- puzzle 5 (a real login: wrong password is simply refused) ----
    def in_pc(self, ev):
        if self.done[4]:
            if ev["down"] or ev["tap"]: self.page = min(2, self.page + 1)
            elif ev["up"]: self.page = max(0, self.page - 1)
            return
        c = self.p5_cur
        if ev["left"]:
            self.clear_feedback()
            self.p5_cur = (c - 1) % 3
        elif ev["right"]:
            self.clear_feedback()
            self.p5_cur = (c + 1) % 3
        elif ev["up"]:
            self.clear_feedback()
            self.p5[c] = (self.p5[c] - 1) % 26
        elif ev["down"]:
            self.clear_feedback()
            self.p5[c] = (self.p5[c] + 1) % 26
        elif ev["tap"]:
            entered_str = "".join(chr(65 + val) for val in self.p5)
            ok = entered_str == PC_PASS
            if self.commit(
                4,
                ok,
                correct_msg="ACCESS GRANTED. The login passcode is correct. Puzzle 5 is complete.",
                wrong_msg="ACCESS DENIED. The passcode is incorrect. Check the letters and try again."
                ,
                note="P5 correct login passcode: " + entered_str
            ):
                self.page = 0

    def in_door(self, ev):
        n = 2 if self.door_layer == 0 else 5
        c = self.door_cur
        if ev["left"]: self.door_cur = (c - 1) % n
        elif ev["right"]: self.door_cur = (c + 1) % n
        elif ev["up"]: self.door_digits[c] = (self.door_digits[c] + 1) % 10
        elif ev["down"]: self.door_digits[c] = (self.door_digits[c] - 1) % 10
        elif ev["tap"]: self.door_confirm()

    # ---------------- drawing helpers ----------------
    def txt(self, s, text, x, y, font=None, color=(255, 255, 255)):
        s.blit((font or self.f_m).render(text, True, color), (x, y))

    def ctxt(self, s, text, cx, y, font=None, color=(255, 255, 255)):
        img = (font or self.f_m).render(text, True, color)
        s.blit(img, (cx - img.get_width() // 2, y))

    def wrap(self, text, font, width):
        lines = []
        for para in text.split("\n"):
            cur = ""
            for word in para.split(" "):
                t = (cur + " " + word).strip()
                if font.size(t)[0] <= width or not cur: cur = t
                else: lines.append(cur); cur = word
            lines.append(cur)
        return lines

    def blit_wrap(self, s, text, x, y, width, font, color, lh=None):
        lh = lh or font.get_linesize()
        for l in self.wrap(text, font, width):
            self.txt(s, l, x, y, font, color); y += lh
        return y

    # ---------------- drawing: world ----------------
    def camera(self):
        cx = max(0.0, min(IMG_W - VIEW_W, self.px - VIEW_W / 2))
        cy = max(0.0, min(IMG_H - VIEW_H, self.py - 60 - VIEW_H / 2))
        return cx, cy

    def draw_interaction_hint(self, ui):
        """Show a subtle [SEARCH] prompt above the player near an interactable object."""
        nearby = self.find_near()
        if nearby is None:
            return

        search_names = {
            "whiteboard": "WHITEBOARD",
            "paper": "PAPER",
            "laptop3": "LAPTOP 1",
            "laptop4": "LAPTOP 2",
            "projector": "PROJECTOR SCREEN",
            "pc": "TEACHER COMPUTER",
            "lightsw": "LIGHT SWITCH",
            "door": "EXIT DOOR",
        }
        search_name = search_names.get(nearby.id, nearby.name.upper())

        cx, cy = self.camera()
        player_x = int((self.px - cx) * ZOOM)
        player_y = int((self.py - cy) * ZOOM)

        player_img = self.sprite.image(self.form)
        if player_img:
            label_y = player_y - player_img.get_height() - 8
        else:
            label_y = player_y - int(SPR_H * ZOOM) - 8

        label = self.f_tiny.render("[SEARCH : %s]" % search_name, True, (225, 230, 240))
        label_rect = label.get_rect(center=(player_x, label_y))

        # A faint background keeps the small prompt readable against the room.
        background = pygame.Surface(
            (label_rect.width + 8, label_rect.height + 4),
            pygame.SRCALPHA
        )
        background.fill((15, 18, 25, 155))
        ui.blit(background, (label_rect.x - 4, label_rect.y - 2))
        ui.blit(label, label_rect)

    def draw_world(self, ui):
        cx, cy = self.camera()
        w2s = lambda x, y: (int((x - cx) * ZOOM), int((y - cy) * ZOOM))
        if self.bg:
            ui.blit(self.bg, (-int(cx * ZOOM), -int(cy * ZOOM)))
        else:
            ui.fill((40, 40, 50))
            pts = [w2s(floor_left(FLOOR_TOP), FLOOR_TOP), w2s(floor_right(FLOOR_TOP), FLOOR_TOP),
                   w2s(floor_right(FLOOR_BOT), FLOOR_BOT), w2s(floor_left(FLOOR_BOT), FLOOR_BOT)]
            pygame.draw.polygon(ui, (150, 140, 160), pts)
            for b in BLOCKERS:
                x, y = w2s(b.x, b.y)
                pygame.draw.rect(ui, (110, 80, 60), (x, y, int(b.w * ZOOM), int(b.h * ZOOM)))
            for o in OBJS:
                x, y = w2s(o.rect.x, o.rect.y)
                pygame.draw.rect(ui, (90, 120, 160), (x, y, int(o.rect.w * ZOOM), int(o.rect.h * ZOOM)), 2)
                ui.blit(self.f_tiny.render(o.name, True, (255, 255, 255)), (x + 2, y + 2))
        img = self.sprite.image(self.form)
        if img:
            fx, fy = w2s(self.px, self.py + 4)               # feet position, sprite anchored bottom-centre
            ui.blit(img, (fx - img.get_width() // 2, fy - img.get_height()))
        else:
            sx, sy = w2s(self.px - SPR_W / 2, self.py - SPR_H + 4)
            sw_, sh_ = int(SPR_W * ZOOM), int(SPR_H * ZOOM)
            pygame.draw.rect(ui, FORM_COLORS[self.form], (sx, sy + sh_ // 3, sw_, sh_ - sh_ // 3), border_radius=6)
            pygame.draw.circle(ui, (240, 200, 160), (sx + sw_ // 2, sy + sh_ // 6), max(6, sw_ // 3))
        if not self.lights:
            dk = pygame.Surface((UW, UH)); dk.fill((0, 0, 25)); dk.set_alpha(150); ui.blit(dk, (0, 0))

        # Show the interaction prompt only while an object is within reach.
        self.draw_interaction_hint(ui)

        if self.debug:
            pts = [w2s(floor_left(FLOOR_TOP), FLOOR_TOP), w2s(floor_right(FLOOR_TOP), FLOOR_TOP),
                   w2s(floor_right(FLOOR_BOT), FLOOR_BOT), w2s(floor_left(FLOOR_BOT), FLOOR_BOT)]
            pygame.draw.polygon(ui, (0, 255, 255), pts, 2)
            for b in BLOCKERS:
                x, y = w2s(b.x, b.y)
                pygame.draw.rect(ui, (255, 0, 0), (x, y, int(b.w * ZOOM), int(b.h * ZOOM)), 2)
            for o in OBJS:
                x, y = w2s(o.ax, o.ay)
                pygame.draw.circle(ui, (255, 255, 0), (x, y), 4)
                pygame.draw.circle(ui, (255, 255, 0), (x, y), int(o.r * ZOOM), 1)
                ui.blit(self.f_tiny.render(o.id, True, (255, 255, 0)), (x + 5, y - 5))
            fx, fy = w2s(self.px - FEET_HW, self.py - FEET_H)
            pygame.draw.rect(ui, (0, 255, 0), (fx, fy, int(FEET_HW * 2 * ZOOM), int(FEET_H * ZOOM)), 1)

    # ---------------- drawing: close-up ----------------
    def cu_img(self, oid):
        if oid not in self.cu_cache: self.cu_cache[oid] = load_img("closeup_%s.png" % oid, (UW, UH))
        return self.cu_cache[oid]

    def draw_closeup(self, ui, s):
        o = self.cur
        img = self.cu_img(o.id)
        if img: ui.blit(img, (0, 0))
        pygame.draw.rect(s, (70, 74, 90), (0, 0, 640, 44))
        self.txt(s, o.name.upper(), 16, 10, self.f_l)
        foot = (getattr(self, "cu_" + o.kind, None) or self.cu_plain)(s)
        if self.cmsg:
            msg_color = (110, 255, 145) if self.feedback is True else (255, 105, 105) if self.feedback is False else (255, 225, 120)
            for i, l in enumerate(self.wrap(self.cmsg, self.f_m, 610)[:2]):
                self.txt(s, l, 16, 440 + i * 24, self.f_m, msg_color)
        pygame.draw.rect(s, (40, 44, 60), (0, 494, 640, 46))
        self.txt(s, foot or "", 16, 499, self.f_s, (170, 200, 255))
        self.txt(s, "Back: hold BTNC for 0.8 s", 16, 520, self.f_tiny, (140, 150, 180))

    def cu_plain(self, s):
        o, st = self.cur, self.ostate[self.cur.id]
        pygame.draw.rect(s, (90, 96, 120), (200, 290, 240, 120), border_radius=10)
        self.blit_wrap(s, o.desc, 40, 70, 560, self.f_m, (230, 230, 230))
        if st["revealed"]:
            pygame.draw.rect(s, (60, 60, 85), (40, 150, 560, 110), border_radius=8)
            self.blit_wrap(s, o.hidden, 56, 164, 528, self.f_m, (255, 230, 120))
            if o.collect:
                self.txt(s, "Picked up (see notebook)" if st["collected"] else "BTNC: pick it up", 56, 232, self.f_s, (150, 255, 150))
            return "" if (not o.collect or st["collected"]) else "BTNC: pick up"
        return "BTNC: look closer" if o.hidden else ""

    def cu_whiteboard(self, s):
        pygame.draw.rect(s, (240, 240, 235), (40, 56, 560, 376), border_radius=6)
        ink = (30, 40, 130)
        if self.page == 0:
            lines = ["ROOM 402 - FINAL EXAM", "attendance sheet", "", "registered ........ 0x2A",
                     "absent ............ 0b10011", "sick leave ........ 0o21", "",
                     "sitting the exam = ?"]
            for i, l in enumerate(lines): self.txt(s, l, 70, 78 + i * 38, self.f_mono_l, ink)
            return "BTNC: next page"
        for i, l in enumerate(["margin notes:", "weights   128 64 32 16 8 4 2 1",
                               "hex  A=10 B=11 C=12 D=13 E=14 F=15", "octal: digits are 8s and 1s"]):
            self.txt(s, l, 70, 70 + i * 26, self.f_mono, ink)
        pygame.draw.rect(s, (60, 60, 70), (70, 190, 500, 224), border_radius=8)
        self.txt(s, "HEAD-COUNT DIAL  (switches SW3..SW0)", 90, 202, self.f_s)
        for k in range(4):
            i = 3 - k
            cx = 150 + k * 90
            pygame.draw.circle(s, (255, 220, 60) if self.sw[i] else (90, 90, 90), (cx, 280), 26)
            self.ctxt(s, str(8 >> k), cx, 316, self.f_m)
        self.txt(s, "= %d" % self.p1_val(), 470, 262, self.f_l)
        if self.done[0]: self.txt(s, "LOGGED: A = %s" % self.ans["A"], 90, 366, self.f_m, (255, 230, 120))
        return "ANSWER: set SW3-SW0, then BTNC"

    def draw_kmap(self, s, x, y, cell, ink):
        self.txt(s, "AB\\CD", x, y + 4, self.f_s, ink)
        for c in range(4):
            self.txt(s, "%d%d" % (GRAY[c] >> 1, GRAY[c] & 1), x + cell * (c + 1) + cell // 3, y + 4, self.f_s, ink)
        for r in range(4):
            self.txt(s, "%d%d" % (GRAY[r] >> 1, GRAY[r] & 1), x + 6, y + cell * (r + 1) + cell // 3, self.f_s, ink)
            for c in range(4):
                m = (GRAY[r] << 2) | GRAY[c]
                rc = pygame.Rect(x + cell * (c + 1), y + cell * (r + 1), cell, cell)
                pygame.draw.rect(s, ink, rc, 1)
                self.ctxt(s, str((P2_TRUTH >> m) & 1), rc.centerx, rc.y + cell // 3, self.f_m, ink)

    def cu_paper(self, s):
        pygame.draw.rect(s, (245, 240, 220), (40, 56, 560, 366), border_radius=4)
        ink = (40, 40, 40)
        if self.page == 0:
            self.txt(s, "SENSOR FAIL LOG   (1 = failed)", 70, 68, self.f_m, ink)
            self.txt(s, "rows: A B    columns: C D    Do it in terms of SOP", 70, 94, self.f_s, ink)
            self.draw_kmap(s, 70, 122, 52, ink)
            self.txt(s, "F =", 400, 230, self.f_l, ink)
            st = pygame.Surface((150, 110), pygame.SRCALPHA)
            pygame.draw.ellipse(st, (110, 70, 30, 170), (0, 0, 150, 110))
            s.blit(st, (450, 190))
            return "BTNC: next page"
        self.draw_kmap(s, 56, 70, 44, ink)
        for i in range(3):
            u, p = self.p2[i]
            y = 90 + i * 46
            if i == self.p2_cur: pygame.draw.rect(s, (255, 230, 120), (310, y - 6, 270, 38), border_radius=6)
            self.txt(s, "Term%d:  %s" % (i + 1, term_str(u, p) or "(empty)"), 324, y, self.f_m, ink)
        u, p = [self.sw[7 - i] for i in range(4)], [self.sw[3 - i] for i in range(4)]
        self.txt(s, "switches say:  %s" % (term_str(u, p) or "(nothing)"), 310, 250, self.f_m, (30, 80, 160))
        self.txt(s, "SW7-4: which letters (A B C D)", 310, 290, self.f_s, ink)
        self.txt(s, "SW3-0: 1 = plain, 0 = inverted", 310, 312, self.f_s, ink)
        if self.done[1]: self.txt(s, "LOGGED: F = %s" % self.p2_eq, 70, 380, self.f_m, (30, 80, 160))
        return "BTNU/BTND slot | BTNC store | BTNR confirm answer"

    def cu_nand(self, s):
        pygame.draw.rect(s, (10, 20, 10), (40, 60, 560, 360), border_radius=6)
        g = (110, 255, 130)
        if self.page == 0:
            lines = ["SYSTEM TERMINAL - LAB 01", "",
                     "Status: Spec match required",
                     "Task: Build F from puzzle on cabinet as a",
                     "      minimal combinational circuit",
                     "Constraint: 74HC00 quad NAND gates only. G(n) = Gate(n)"]
            for i, l in enumerate(lines): self.txt(s, l, 56, 76 + i * 34, self.f_mono, g)
            return "BTNC: open circuit editor"
        for k in range(4):
            y = 74 + k * 44
            for j in range(2):
                f = 2 * k + j
                hl = (f == self.p3_cur)
                self.txt(s, ("> " if hl else "  ") + "G%d in%d: %s" % (k + 1, j + 1, SRC_NAMES[self.p3[f]]), 64 + j * 260, y, self.f_mono, (255, 255, 120) if hl else g)
        hl = (self.p3_cur == 8)
        self.txt(s, ("> " if hl else "  ") + "F = output of: G%d" % (self.p3[8] + 1), 64, 256, self.f_mono, (255, 255, 120) if hl else g)
        if SHOW_P3_TARGET: self.txt(s, "target F: " + bits16(P2_TRUTH), 64, 296, self.f_tiny, g)
        self.txt(s, "your F:   " + bits16(p3_table(self.p3)), 64, 320, self.f_tiny, g)
        return "BTNL/BTNR field | BTNU/BTND source | BTNC save circuit"

    def cu_twos(self, s):
        pygame.draw.rect(s, (10, 10, 25), (40, 60, 560, 360), border_radius=6)
        g = (130, 200, 255)
        if self.page == 0:
            lines = ["SYSTEM KERNEL CONSOLE", "",
                     "Target register: penalty_reg",
                     "Current decimal value: 12",
                     "Operation: Invert sign using two's complement", "",
                     "READY FOR PATCH INPUT..."]
            for i, l in enumerate(lines): self.txt(s, l, 56, 76 + i * 34, self.f_mono, g)
            return "BTNC: open patch console"
        self.txt(s, "penalty_reg patch value:", 70, 90, self.f_m, g)
        bits = "".join("1" if self.sw[i] else "0" for i in range(7, -1, -1))
        self.txt(s, bits, 70, 130, self.f_mono_l, (255, 255, 120))
        v = self.p4_val()
        self.txt(s, "unsigned %d    signed %d" % (v, v - 256 if v >= 128 else v), 70, 180, self.f_m, g)
        return "ANSWER: set SW7-SW0, then BTNC"

    def app_logo(self, app_name):
        """Load an optional app logo; return None when its image is unavailable."""
        filenames = {
            "Canva": "app_logo_canva.png",
            "Pinterest": "app_logo_pinterest.png",
            "Explorer": "app_logo_explorer.png",
            "AppStore": "app_logo_appstore.png",
            "X": "app_logo_x.png",
            "Facebook": "app_logo_facebook.png",
        }
        if app_name not in self.app_logo_cache:
            filename = filenames.get(app_name)
            self.app_logo_cache[app_name] = load_img(filename, (22, 22)) if filename else None
        return self.app_logo_cache[app_name]

    def cu_screen(self, s):
        if self.lights:
            pygame.draw.rect(s, (235, 235, 230), (40, 60, 560, 360))
            self.ctxt(s, "No Signal", 320, 230, self.f_s, (150, 150, 145))
            return ""
        pygame.draw.rect(s, (15, 20, 30), (40, 60, 560, 360), border_radius=6)
        self.ctxt(s, "PROJECTOR SLIDE: APP LOGO MASTERMIND", 320, 60, self.f_s, (130, 200, 255))

        pygame.draw.rect(s, (40, 50, 70), (50, 88, 480, 30))
        self.txt(s, "App Sequence (3 Logos)", 60, 94, self.f_tiny, (255, 230, 120))
        self.txt(s, "Correct Apps", 325, 94, self.f_tiny, (255, 230, 120))
        self.txt(s, "Correct Positions", 445, 94, self.f_tiny, (255, 230, 120))

        clue_rows = [
            (("Facebook", "Explorer", "Canva"), "2", "0"),
            (("Facebook", "Canva", "X"), "1", "0"),
            (("Canva", "AppStore", "Pinterest"), "2", "1"),
            (("Pinterest", "AppStore", "Facebook"), "1", "0"),
            (("AppStore", "Explorer", "Facebook"), "1", "0"),
        ]
        for idx, (apps, ca, cp) in enumerate(clue_rows):
            y = 122 + idx * 35
            pygame.draw.rect(s, (25, 32, 45) if idx % 2 == 0 else (20, 26, 38), (50, y, 480, 33))
            for app_idx, app_name in enumerate(apps):
                logo = self.app_logo(app_name)
                x = 60 + app_idx * 82
                if logo:
                    s.blit(logo, (x, y + 5))
                else:
                    self.txt(s, app_name, x, y + 8, self.f_tiny, (240, 240, 240))
            self.ctxt(s, ca, 365, y + 8, self.f_s, (150, 255, 150))
            self.ctxt(s, cp, 485, y + 8, self.f_s, (255, 220, 100))

        self.ctxt(s, "Deduce the secret 3-app code from clues.", 320, 316, self.f_tiny, (180, 220, 180))
        self.ctxt(s, "The nearby workstation may hold another piece of this trail.", 320, 350,
                  self.f_tiny, (125, 145, 170))
        return "Turn off room lights to view clearly"

    def cu_lightsw(self, s):
        pygame.draw.rect(s, (200, 200, 200), (260, 110, 120, 200), border_radius=10)
        pygame.draw.rect(s, (90, 200, 90) if self.lights else (200, 80, 80), (290, 130 if self.lights else 220, 60, 70), border_radius=6)
        self.ctxt(s, "LIGHTS ON" if self.lights else "LIGHTS OFF", 320, 340, self.f_m)
        return "BTNC: flip the switch"

    def cu_door(self, s):
        pygame.draw.rect(s, (120, 85, 55), (240, 56, 160, 230), border_radius=6)
        n = 2 if self.door_layer == 0 else 5
        self.ctxt(s, "LOCK %d of 2  (%d digits)" % (self.door_layer + 1, n), 320, 298, self.f_m)
        x0 = 320 - n * 70 // 2
        for i in range(n):
            r = pygame.Rect(x0 + i * 70 + 5, 332, 60, 64)
            pygame.draw.rect(s, (255, 230, 120) if i == self.door_cur else (200, 200, 200), r, border_radius=6)
            self.ctxt(s, str(self.door_digits[i]), r.centerx, r.y + 14, self.f_l, (20, 20, 20))
        return "BTNU/BTND digit | BTNL/BTNR box | BTNC confirm"

    def cu_pc(self, s):
        pygame.draw.rect(s, (15, 25, 50), (40, 60, 560, 360), border_radius=6)
        c = (160, 200, 255)
        if not self.done[4]:
            self.txt(s, "PROFESSOR TERMINAL LOGIN", 70, 75, self.f_mono, c)
            self.txt(s, "Enter 3-letter passcode (A-Z):", 70, 115, self.f_s, c)
            for i in range(3):
                r = pygame.Rect(180 + i * 90, 150, 70, 70)
                pygame.draw.rect(s, (255, 230, 120) if i == self.p5_cur else (60, 75, 110), r, border_radius=8)
                self.ctxt(s, chr(65 + self.p5[i]), r.centerx, r.y + 18, self.f_l, (255, 255, 255))
            self.txt(s, "Match projector table clues to unlock terminal", 70, 250, self.f_tiny, (180, 220, 180))
            return "BTNU/BTND letter (A-Z) | BTNL/BTNR box | BTNC enter"
        if self.page == 0:
            self.txt(s, "Welcome, prof.", 70, 90, self.f_mono_l, c)
            self.txt(s, "[ door_manual.txt ]", 70, 150, self.f_mono_l, (255, 230, 120))
            return "BTNU/BTND or BTNC: open file"
        if self.page == 1:
            lines = ["DOOR - LAYER 1  (2 digits)", "1. Take the LAST letter of your login password.",
                     "2. Find it in the table (values are HEX).", "3. Key in its DECIMAL value.", "",
                     "A 41  B 42  C 43  D 44  E 45  F 46  G 47", "H 48  I 49  J 4A  K 4B  L 4C  M 4D  N 4E",
                     "O 4F  P 50  Q 51  R 52  S 53  T 54  U 55", "V 56  W 57  X 58  Y 59  Z 5A"]
        else:
            lines = ["DOOR - LAYER 2  (5 digits)", "A = whiteboard dial result",
                     "B = report code from cabinet + laptop 1", "C = receipt code from laptop 2",
                     "Step 1: S = A + B + C.  Row: A B C S", "        (S has two digits -> 5 digits)",
                     "Step 2: new digit 1 = old position 4,", "        then old 2, 5, 1, 3.",
                     "Example: row 2 4 6 8 9 -> 8 4 9 2 6"]
        for i, l in enumerate(lines): self.txt(s, l, 56, 74 + i * 33, self.f_mono, c)
        return "BTNU/BTND: page"

    # ---------------- drawing: overlays ----------------
    def draw_cards(self, ui, s):
        d = self.deck
        ov = pygame.Surface((UW, UH), pygame.SRCALPHA); ov.fill((0, 0, 0, 205)); ui.blit(ov, (0, 0))
        self.ctxt(s, "PICK A CARD", 320, 30, self.f_l)

        if self.career is not None:
            career_name, career_col = CAREERS[self.career]
        else:
            career_name, career_col = "", (80, 85, 100)

        for pos in range(3):
            r = pygame.Rect(65 + pos * 180, 95, 170, 170)
            idx = d["perm"][pos]
            
            # --- ดึงชื่อไอเทมจริงๆ ของการ์ดใบนี้ (เช่น "SHARD", "SLOW", ฯลฯ) ---
            item_key = CARD_ITEMS[d["round"]][idx] 
            
            revealed = (d["face"] == pos)
            fb_col = CAREERS[idx][1] if (d["round"] == 1 and revealed) else (career_col if d["round"] > 1 else (80, 85, 100))

            # --- ส่ง item_name=item_key เข้าไปให้ CardAssets ---
            drew_img = self.card_art.draw_card(
                s, r, d["round"], self.career, pos, revealed, slot_idx=idx, fallback_color=fb_col, item_name=item_key
            )

            # ถ้าไม่มีรูปให้ขึ้นข้อความเดิมแทน และถ้ารอบ 2+ เปิดแล้วให้แสดงชื่อไอเทมบนแถบดำโปร่งใส
            if not drew_img:
                if revealed:
                    self.ctxt(s, d["name"], r.centerx, r.y + 90, self.f_m, (255, 255, 255))
                elif d["round"] == 1:
                    self.ctxt(s, "?", r.centerx, r.y + 90, self.f_l, (200, 200, 200))
                else:
                    sym = SYMBOLS[self.career][pos] if self.career is not None else career_name
                    self.ctxt(s, sym, r.centerx, r.y + 90, self.f_m, (255, 255, 255))
            

            if d["face"] is None and pos == d["cursor"]:
                pygame.draw.rect(s, (255, 255, 255), r.inflate(10, 10), 4, border_radius=12)

        if d["face"] is not None:
            # Keep the original card-result layout: the description sits in its
            # own dark panel, while the continue prompt stays below it.
            pygame.draw.rect(s, (30, 35, 45), (80, 300, 480, 110), border_radius=8)
            self.ctxt(s, "Obtained: " + d["name"], 320, 306, self.f_l, (255, 230, 120))
            for i, line in enumerate(self.wrap(d["desc"], self.f_s, 440)[:3]):
                self.ctxt(s, line, 320, 350 + i * 20, self.f_s, (240, 240, 240))
            self.ctxt(s, "BTNC: continue", 320, 424, self.f_m, (170, 200, 255))
        else:
            self.ctxt(s, "BTNL/BTNR choose   BTNC pick", 320, 360, self.f_m, (170, 200, 255))

    def draw_box(self, s, rect):
        pygame.draw.rect(s, (20, 22, 30), rect, border_radius=10)
        pygame.draw.rect(s, (120, 130, 170), rect, 2, border_radius=10)

    def draw_notebook(self, s):
        self.draw_box(s, pygame.Rect(60, 50, 520, 420))
        self.ctxt(s, "NOTEBOOK  (SW14 to close)", 320, 62, self.f_m)
        v = lambda k: "?" if self.ans[k] is None else self.ans[k]
        self.txt(s, "Answers Logged: A = %s   B = %s   C = %s" % (v("A"), v("B"), v("C")), 80, 100, self.f_s, (255, 230, 120))
        y = 140
        self.txt(s, "Logged Actions & Clues:", 80, y, self.f_s, (170, 200, 255)); y += 22
        for n in self.notes[-8:]: y = self.blit_wrap(s, "- " + n, 80, y, 480, self.f_s, (230, 230, 230))
        y += 8
        self.txt(s, "Hints Used:", 80, y, self.f_s, (170, 200, 255)); y += 22
        for h in self.hints_seen[-3:]:
            y = self.blit_wrap(s, "- " + h, 80, y, 480, self.f_s, (230, 230, 230))

    def draw_notebook_guide(self, ui, s):
        ov = pygame.Surface((UW, UH), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 205))
        ui.blit(ov, (0, 0))
        self.draw_box(s, pygame.Rect(48, 165, 544, 190))
        self.ctxt(s, "ANSWER SAVED TO NOTEBOOK", 320, 190, self.f_l, (150, 255, 170))
        self.ctxt(s, "Your correct answer has been recorded.", 320, 240, self.f_m)
        self.ctxt(s, "Flip SW14 to open the Notebook and view it.", 320, 278, self.f_m, (255, 230, 120))
        self.ctxt(s, "Gameplay will continue after you open it.", 320, 318, self.f_s, (170, 200, 255))

    def draw_help(self, ui, s):
        ov = pygame.Surface((UW, UH), pygame.SRCALPHA); ov.fill((0, 0, 0, 215)); ui.blit(ov, (0, 0))
        self.draw_box(s, pygame.Rect(30, 60, 580, 420))
        self.ctxt(s, "HOW TO PLAY", 320, 74, self.f_l)
        rows = [("Move", "BTNU / BTND / BTNL / BTNR"),
                ("Interact / confirm", "BTNC (tap)"),
                ("Back", "BTNC (hold for 0.8 s)"),
                ("Puzzle inputs", "SW0-SW7"),
                ("Notebook", "SW14 (toggle)"),
                ("Help", "SW15 (toggle)")]
        for i, (a, b) in enumerate(rows):
            self.txt(s, a, 54, 128 + i * 30, self.f_s, (255, 230, 120))
            self.txt(s, b, 220, 128 + i * 30, self.f_s)
        self.blit_wrap(s, "Approach an object and press BTNC. If nothing happens, it is scenery.", 54, 330, 530, self.f_m, (170, 200, 255))
        self.ctxt(s, "BTNC: start", 320, 442, self.f_m, (150, 255, 170))

    def draw_hud(self, ui):
        for i in range(3):
            col = (230, 50, 60) if i < self.hearts else (80, 50, 50)
            pygame.draw.circle(ui, col, (24 + i * 26, 22), 10)
        if self.armor > 0:
            pygame.draw.rect(ui, (80, 180, 255), (96, 12, 18, 22), border_radius=4)
            self.txt(ui, "x%d" % self.armor, 118, 14, self.f_s, (120, 200, 255))
        if self.slow_t > 0:
            self.txt(ui, "SLOW %.0fs" % self.slow_t, 180, 14, self.f_m, (255, 150, 80))
        if self.freeze_t > 0:
            self.txt(ui, "FREEZE %.0fs" % self.freeze_t, 290, 14, self.f_m, (140, 220, 255))

    def draw_toast(self, ui):
        if time.time() < self.toast[1]:
            img = self.f_m.render(self.toast[0], True, (255, 255, 255))
            r = pygame.Rect(UW // 2 - img.get_width() // 2 - 12, 14, img.get_width() + 24, 34)
            pygame.draw.rect(ui, (0, 0, 0), r, border_radius=8)
            ui.blit(img, (r.x + 12, r.y + 7))

    def seg_right(self):
        if self.state == "clear": return "PA55"
        if self.state == "over": return "dEAd"
        if self.mode == "closeup" and self.cur and not self.deck["active"]:
            k = self.cur.kind
            if k == "whiteboard" and self.page == 1: return str(self.p1_val())
            if k == "twos" and self.page == 1: return str(self.p4_val())
            if k == "door": return "".join(str(d) for d in self.door_digits[:2 if self.door_layer == 0 else 5])
            if k == "pc" and not self.done[4]: return "".join(str(v) for v in self.p5)
        return ""

    def draw_panel(self, scr):
        y0 = SCR_H
        pygame.draw.rect(scr, (24, 26, 32), (0, y0, SCR_W, PANEL_H))
        pygame.draw.line(scr, (70, 74, 90), (0, y0), (SCR_W, y0), 2)
        leds = [False] * 16
        for i in range(3): leds[i] = self.hearts > i
        leds[3] = self.armor > 0
        for i in range(5): leds[4 + i] = self.done[i]
        leds[9] = self.lights
        leds[10] = self.freeze_t > 0
        leds[11] = self.slow_t > 0
        for i in range(16):
            pygame.draw.circle(scr, (255, 70, 60) if leds[i] else (70, 40, 40), (sw_cx(i), y0 + 18), 7)
        for i in range(16):
            r = self.sw_rects[i]
            pygame.draw.rect(scr, (230, 230, 230) if self.sw[i] else (80, 80, 90), r, border_radius=5)
            self.ctxt(scr, "SW%d" % i, r.centerx, r.y + 11, self.f_tiny, (20, 20, 20) if self.sw[i] else (200, 200, 200))
        text = ("H%d" % max(0, self.hearts)) + self.seg_right().rjust(6)[-6:]
        for i, ch in enumerate(text):
            draw_digit(scr, ch, 14 + i * 40, y0 + 26, 32, 52)
        self.txt(scr, "7-SEG: H3 = 3 hearts | right = live value", 14, y0 + 84, self.f_tiny, (170, 170, 190))
        self.txt(scr, "LED: 0-2 hearts  3 armor  4-8 puzzles answered  9 lights  10 freeze  11 slow", 360, y0 + 78, self.f_tiny, (140, 140, 160))
        self.txt(scr, "BTNU/BTND/BTNL/BTNR: Move | BTNC: Interact (hold: Back) | SW14: Notebook | SW15: Help",
                 360, y0 + 94, self.f_tiny, (170, 170, 190))
        self.txt(scr, "Form: %s" % FORM_NAMES[self.form], 14, y0 + 98, self.f_tiny, (140, 140, 160))

    def draw(self, ui, screen):
        ui.fill((18, 20, 26))
        s = ui.subsurface(pygame.Rect(160, 0, 640, UH))
        if self.mode == "closeup" and self.cur: self.draw_closeup(ui, s)
        else: self.draw_world(ui)
        self.draw_hud(ui)
        if self.sw[14]: self.draw_notebook(s)
        if self.deck["active"]: self.draw_cards(ui, s)
        if self.notebook_guide_pending and not self.sw[14]:
            self.draw_notebook_guide(ui, s)
        if self.flash > 0:
            fl = pygame.Surface((UW, UH)); fl.fill((255, 0, 0)); fl.set_alpha(int(180 * self.flash / 0.4)); ui.blit(fl, (0, 0))
        if self.state == "over":
            ov = pygame.Surface((UW, UH)); ov.set_alpha(220); ui.blit(ov, (0, 0))
            self.ctxt(ui, "OUT OF HEARTS", UW // 2, 220, self.f_l, (255, 90, 90))
            self.ctxt(ui, "Restarting Stage 1...", UW // 2, 270, self.f_m)
        if self.state == "clear":
            ui.fill((15, 40, 25))
            self.ctxt(ui, "STAGE 1 CLEAR - YOU PASSED THE EXAM!", UW // 2, 160, self.f_l, (150, 255, 170))
            self.ctxt(ui, "Hearts left: %d" % self.hearts, UW // 2, 220, self.f_m)
            self.ctxt(ui, "CHARACTER EVOLVED -> %s" % FORM_NAMES[1], UW // 2, 270, self.f_m, (255, 230, 120))
            self.ctxt(ui, "BTNC: play again" if self.standalone else "BTNC: continue to the next stage",
                      UW // 2, 370, self.f_s, (170, 200, 255))
        self.draw_toast(ui)
        if self.show_help: self.draw_help(ui, s)
        screen.blit(pygame.transform.smoothscale(ui, (SCR_W, SCR_H)), (0, 0))
        self.draw_panel(screen)


def main():
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_caption("CPE Escape - Stage 1 (PC demo)")
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