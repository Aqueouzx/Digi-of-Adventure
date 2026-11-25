#!/usr/bin/env python3
# PC DEMO ONLY - not FPGA code. Gameplay prototype of Stage 2 (Internship), same structure as the Stage 1 demo.
# Flow: hunt the 18 lab parts hidden in the office (notes and screens hold hints) -> bring them to the decoder bench
#       -> wire the 7-segment decoder on a breadboard (74HC04 / 74HC08 / 74HC32 x2 + DIP switch + resistors)
#       -> pass 3 QA tests -> the exit door unlocks.  No in-game computers.
# Files used (folder layout):   <project>/assets/bg.jpg   <project>/assets/player_form{N}_{back|front|right}_{stand|stepl|stepr}.png
#                               (left uses _left_ files if present, else mirrors right)   + this file.  player_sprite.py is no longer needed.
import copy, itertools, math, os, sys, time
from collections import deque
import pygame

try:
    import card_assets                               # card pictures (demo_py/card_assets.py + assets/); optional
except ImportError:
    card_assets = None
    print("[assets] card_assets.py not found next to this file -> plain cards")

SCR_W, SCR_H, PANEL_H = 1152, 648, 112      # window: game area 16:9 + virtual board panel
UW, UH = 960, 540                           # internal UI surface (16:9), scaled up to the window
CU_X, CU_W = 160, 640                       # close-up panel inside the UI surface
FEET_HW, FEET_H = 10, 10                    # player collision box (feet): 20 x 10 px
SPR_W, SPR_H = 30, 62                       # placeholder size / drawn sprite height
BASE_SPEED = 260.0                          # px / second
LONG_PRESS_S = 0.8
TEST_MODE = True                            # test shortcuts (auto-wire button, F7/F8, skip intro). Set False for the real game

_HERE = os.path.dirname(os.path.abspath(__file__))
# images are searched in these folders, in this order
ASSET_DIRS = [os.path.join(os.path.dirname(_HERE), "assets"), os.path.join(_HERE, "assets"), _HERE,
              os.path.join(os.getcwd(), "assets"), os.getcwd()]


def find_asset(name):                # "bg.jpg" also matches bg.png / .jpeg / .webp
    stem, ext0 = os.path.splitext(name)
    for d in ASSET_DIRS:
        for ext in (ext0, ".jpg", ".jpeg", ".png", ".webp"):
            path = os.path.join(d, stem + ext)
            if os.path.isfile(path):
                return path
    return None


def load_img(name, size=None):
    path = find_asset(name)
    if path is None:
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(img, size) if size else img
    except (pygame.error, ValueError) as e:
        print("[assets] could not read %s: %s" % (path, e))
        return None


class BossSprite:
    """Boss skin from assets/: every image whose name starts with "Boss" (any case, png/jpg/webp).
    Name = Boss[_dir][_pose], e.g. Boss_front_stand.png, Boss_right_stepl.png, Boss_sit.png, or just Boss.png.
      dir  : back | front | left | right      (a missing left is the right image mirrored; no dir = used for every direction)
      pose : stand | stepl | stepr | sit      (no pose = stand)"""
    DIRS = ("back", "front", "left", "right")
    POSE = {"stand": "stand", "idle": "stand", "stepl": "stepl", "walk1": "stepl", "stepr": "stepr", "walk2": "stepr",
            "sit": "sit", "sitting": "sit", "seat": "sit"}
    STEP_S = 0.14

    def __init__(self, stand_h, sit_h):
        self.stand_h, self.sit_h, self.files, self.cache = stand_h, sit_h, {}, {}
        seen = set()
        for d in ASSET_DIRS:
            if not os.path.isdir(d): continue
            for fn in sorted(os.listdir(d)):
                stem, ext = os.path.splitext(fn)
                if not stem.lower().startswith("boss") or ext.lower() not in (".png", ".jpg", ".jpeg", ".webp") or fn.lower() in seen: continue
                seen.add(fn.lower())
                toks = [t for t in "".join(c if c.isalnum() else " " for c in stem.lower()[4:]).split() if t]
                dr = next((t for t in toks if t in self.DIRS), "any")
                pose = next((self.POSE[t] for t in toks if t in self.POSE), "stand")
                self.files.setdefault((dr, pose), os.path.join(d, fn))
        if self.files: print("[assets] Boss skin: %d image(s): %s" % (len(self.files), ", ".join(sorted(os.path.basename(v) for v in self.files.values()))))

    def __bool__(self):
        return bool(self.files)

    def _get(self, dr, pose, mirror=False):
        path = self.files.get((dr, pose))
        if not path: return None
        key = (path, mirror, pose == "sit")
        if key not in self.cache:
            try:
                img = pygame.image.load(path).convert_alpha()
                h = self.sit_h if pose == "sit" else self.stand_h
                img = pygame.transform.smoothscale(img, (max(1, round(img.get_width() * h / img.get_height())), h))
                self.cache[key] = pygame.transform.flip(img, True, False) if mirror else img
            except (pygame.error, ValueError) as e:
                print("[assets] could not read %s: %s" % (path, e)); self.cache[key] = None
        return self.cache[key]

    def image(self, sit, dr, walking, t):
        if sit:
            for d in (dr, "any", "back", "front", "right", "left"):
                img = self._get(d, "sit")
                if img: return img
        pose = "stand"
        if walking and not sit: pose = ("stand", "stepl", "stand", "stepr")[int(t / self.STEP_S) % 4]
        for p in ((pose, "stand") if pose != "stand" else ("stand",)):
            img = self._get(dr, p)
            if img: return img
            if dr == "left":
                img = self._get("right", p, mirror=True)
                if img: return img
            img = self._get("any", p, mirror=(dr == "left"))   # single picture: flip it when walking left
            if img: return img
            if dr == "left":
                img = self._get("right", p, mirror=True)
                if img: return img
        for d in ("front", "any", "right", "back", "left"):
            img = self._get(d, "stand")
            if img: return img
        return None


ASSET_DIR = next((d for d in ASSET_DIRS if os.path.isfile(os.path.join(d, "bg.jpg"))), ASSET_DIRS[0])

class PlayerSprite:
    """Player skin: assets/player_form{N}_{back|front|right}_{stand|stepl|stepr}.png  (left uses player_form{N}_left_* if present, else the right image mirrored).
    Walk cycle: stand, stepl, stand, stepr.  A missing form falls back to form 1; a missing file -> placeholder box."""
    POSES = ("stand", "stepl", "stepr")
    STEP_S = 0.14                                    # seconds per walk frame

    def __init__(self, folder, height):
        self.h, self.cache = height, {}
        self.dir, self.t = "front", 0.0
        self.moving = False

    def reset(self):
        self.dir, self.t, self.moving = "front", 0.0, False

    def update(self, dt, dx, dy, moving):
        if dx: self.dir = "right" if dx > 0 else "left"
        elif dy: self.dir = "front" if dy > 0 else "back"
        self.moving = moving
        self.t = self.t + dt if moving else 0.0

    def stop(self):
        self.moving, self.t = False, 0.0

    def _load(self, form, d, pose):
        key = (form, d, pose)
        if key not in self.cache:
            img = None
            for f in (form, 1):                          # a form without this direction (e.g. gown) falls back to form 1
                img = load_img("player_form%d_%s_%s.png" % (f, d, pose))
                flip = False
                if img is None and d == "left":          # no left picture: mirror the right one
                    img, flip = load_img("player_form%d_right_%s.png" % (f, pose)), True
                if img:
                    img = pygame.transform.smoothscale(img, (max(1, round(img.get_width() * self.h / img.get_height())), self.h))
                    if flip: img = pygame.transform.flip(img, True, False)
                    break
            self.cache[key] = img
        return self.cache[key]

    def image(self, form):
        pose = "stand"
        if self.moving:
            pose = ("stand", "stepl", "stand", "stepr")[int(self.t / self.STEP_S) % 4]
        return self._load(form, self.dir, pose) or self._load(form, self.dir, "stand")


# ---------------- decoder data (same numbers as the RTL design) ----------------
SEGS = "abcdefg"
CHAR_NAME = {1: "C", 2: "P", 3: "E", 4: "-", 5: "3", 6: "9"}          # input code CBA -> character
GOLD = {1: "adef", 2: "abefg", 3: "adefg", 4: "g", 5: "abcdg", 6: "abcdfg"}
ROUNDS = 3                                       # QA tests, 2 random input codes each


def bits(k): return (k >> 2) & 1, (k >> 1) & 1, k & 1


# ---------------- the lab equipment list (18 pieces hidden around the office) ----------------
PARTS = [("not", "74HC04 hex inverter (NOT)", 1), ("and", "74HC08 quad AND", 1), ("or", "74HC32 quad OR", 2),
         ("seg", "7-segment display", 1), ("dip", "DIP switch", 1), ("r10k", "10k ohm resistor", 3),
         ("r220", "220 ohm resistor", 7), ("bb", "Breadboard + jumper wires", 1), ("psu", "Bench DC supply", 1)]
PART_QTY = {k: q for k, _, q in PARTS}
PART_LABEL = {k: n for k, n, _ in PARTS}
PART_SHORT = {"not": "74HC04", "and": "74HC08", "or": "74HC32", "seg": "7-seg", "dip": "DIP sw", "r10k": "10k",
              "r220": "220 ohm", "bb": "Breadboard", "psu": "DC supply"}
TOTAL_PARTS = sum(PART_QTY.values())             # 18
CARD_BACKS = False                               # False: no *_back pictures, every round shows the card faces right away. True: face-down backs, flip on pick
CARD_BOX, CARD_CY = (170, 190), 180                  # card pictures are fitted into this box (never stretched), centre y
CARD2_AT, CARD3_AT = 8, 18                       # card rounds: none at the start, 2 when 8 parts are found, 3 when all 18 are found


R_ITEM, R_OBJ = 50, 70                        # how close (px) you must stand to the spot's walkable point


class Spot:                                      # a hidden part (the red circles in the picture)
    def __init__(self, sid, part, ix, iy, name, clue, foot=None):
        self.id, self.part, self.ix, self.iy, self.name, self.clue = sid, part, ix, iy, name, clue
        self.foot, self.r, self.ax, self.ay = foot or (ix, iy), R_ITEM, 0, 0     # ax, ay: nearest floor spot (set at start-up)


# ix, iy = where the thing is in the picture | foot = where its base touches the floor (the player stands nearby)
ITEM_SPOTS = [
    Spot("bin_g", "not", 48, 490, "Green recycling bin", "Chips get thrown away like trash. Look at the recycling bins in the bottom-left corner."),
    Spot("bin_y", "and", 81, 444, "Yellow recycling bin", "Two recycling bins stand in the bottom-left corner. The yellow one is not empty."),
    Spot("bottle", "r10k", 75, 393, "Water bottle", "Big resistors hide in things you drink from, write with or listen with. Start at the coffee corner.", (120, 400)),
    Spot("plant_l", "or", 169, 321, "Potted plant", "OR chips like plants. One plant stands next to the water cooler on the left."),
    Spot("pen", "r10k", 301, 308, "Pen cup", "Somebody keeps pens in a cup on the first desk of the middle row.", (270, 308)),
    Spot("bind_bl", "r220", 222, 441, "Binder, bottom-left desk", "Small resistors hide inside office binders. The bottom-left desk has one."),
    Spot("bind_tl", "r220", 344, 210, "Binder, top-left desk", "Small resistors hide inside office binders. The top-left desk has one.", (344, 198)),
    Spot("bind_tr", "r220", 484, 205, "Binder, top-right desk", "Small resistors hide inside office binders. The top-right desk has one.", (484, 198)),
    Spot("headset", "r10k", 514, 213, "Headset", "Something you wear on your ears sits on a desk in the top row.", (514, 198)),
    Spot("bind_m1", "r220", 450, 300, "Binder, middle row (left)", "Small resistors hide inside office binders. Check the middle row, left desk."),
    Spot("bind_m2", "r220", 499, 302, "Binder, middle row (right)", "Small resistors hide inside office binders. Check the middle row, right desk."),
    Spot("box", "seg", 776, 414, "Cardboard box", "A display needs a safe box. Try the cardboard box on the floor beside the black desk."),
    Spot("bluebox", "dip", 226, 128, "Blue box on the gray cabinet", "Small blue box, high up: it sits on top of the low gray cabinet on the left.", (240, 272)),
    Spot("rack", "bb", 717, 214, "Box on the shelf rack", "Breadboards live in boxes on shelves. Check the rack under the projector.", (720, 262)),
    Spot("cab", "psu", 343, 141, "Wall cabinet", "Power supplies are heavy: open the tall two-door metal cabinet on the back wall.", (343, 186)),
    Spot("plant_t", "or", 289, 129, "Plant behind the beanbag", "Another OR chip hides in the plant behind the pink beanbag, near the cabinets.", (296, 190)),
    Spot("shelf1", "r220", 863, 319, "Bookshelf, upper shelf", "Small resistors hide inside office binders. The bookshelf on the right has two.", (845, 465)),
    Spot("shelf2", "r220", 870, 382, "Bookshelf, lower shelf", "Small resistors hide inside office binders. The bookshelf on the right has two.", (845, 465)),
]


class Hint:                                      # a note, screen or board that holds a hint (hidden like a part)
    def __init__(self, hid, x, y, title, text, foot=None):
        self.id, self.ix, self.iy, self.title, self.text = hid, x, y, title, text
        self.foot, self.r, self.ax, self.ay = foot or (x, y), R_ITEM, 0, 0


HINT_SPOTS = [
    Hint("h_sticky", 90, 197, "Sticky note",
         "SHOPPING LIST: 1 NOT chip, 1 AND chip, 2 OR chips, 1 display, 1 DIP switch, 3 big resistors (10k), "
         "7 small resistors (220), 1 breadboard with jumper wires, 1 power supply. That is 18 pieces.", (150, 290)),
    Hint("h_locker", 263, 121, "Tag on the locker",
         "Heavy stuff stays in the tall metal cabinet with two doors on the back wall: the bench power supply is in there.", (255, 275)),
    Hint("h_paper", 319, 102, "Paper on the cabinet",
         "Logic chips are like trash to this office: look in the recycling bins in the bottom-left corner (green and yellow).", (326, 186)),
    Hint("h_monitor", 507, 78, "Wall monitor",
         "Resistors with BIG values (10k) hide in things people drink from, write with or listen with: a bottle, a pen cup, a headset.", (507, 186)),
    Hint("h_desk", 538, 229, "Papers on a desk",
         "Seven small 220 ohm resistors sit in office binders: two on the top-row desks, two in the middle row, "
         "one at the bottom-left desk and two on the bookshelf on the right.", (538, 198)),
    Hint("h_cork", 831, 180, "Cork board",
         "OR chips like plants: one by the water cooler on the left wall and one behind the pink beanbag. "
         "Breadboards and wires: a box on the shelf rack under the projector.", (700, 250)),
    Hint("h_npc", 817, 300, "Boss at the black desk",
         "Boss: 'The display? We keep spare parts in the cardboard box on the floor next to my desk. "
         "And that little blue box on top of the gray cabinet is a DIP switch.'", (800, 400)),
    Hint("h_note1", 551, 429, "Sticky note (bottom desk)",
         "Hidden things have no marker: walk close to anything suspicious and press Space to search it. Notes, screens and boards "
         "around the office hold hints. Hints you read are saved in the notebook (N).", (551, 430)),
    Hint("h_note2", 666, 436, "Calendar note (bottom desk)",
         "When the Parts counter reaches 18/18, come to the bottom-right desk. The decoder bench is right here.", (666, 430)),
]

# ---------------- the breadboard: ICs, switch, display ----------------
IC_X = {"U1": 190, "U2": 400, "U3": 190, "U4": 400}
IC_Y = {"U1": 150, "U2": 150, "U3": 330, "U4": 330}
IC_TYPE = {"U1": "74HC04", "U2": "74HC08", "U3": "74HC32", "U4": "74HC32"}
PITCH, BODY_H = 24, 64


def pin_xy(u, p):                                # DIP-14, notch on the left: pins 1-7 bottom, 14-8 top
    x0, yb = IC_X[u], IC_Y[u]
    if p <= 7: return (x0 + 12 + (p - 1) * PITCH, yb + BODY_H + 14)
    return (x0 + 12 + (14 - p) * PITCH, yb - 14)


GATES = {}                                       # gate id -> (kind, unit, input pins, output pin)
for _i, (_a, _b, _y) in enumerate([(1, 2, 3), (4, 5, 6), (9, 10, 8), (12, 13, 11)]):
    GATES["A%d" % (_i + 1)] = ("and", "U2", [_a, _b], _y)
    GATES["O%d" % (_i + 1)] = ("or", "U3", [_a, _b], _y)
    GATES["O%d" % (_i + 5)] = ("or", "U4", [_a, _b], _y)
for _i, (_a, _y) in enumerate([(1, 2), (3, 4), (5, 6)]):
    GATES["N%d" % (_i + 1)] = ("not", "U1", [_a], _y)

UNITS = ["U1", "U2", "U3", "U4"]
SINKS, SINK_POS, SRC_POS, GATE_IN = [], {}, {}, {}
for _u in UNITS:                                 # every chip needs +5V on pin 14 and GND on pin 7
    SINKS += [_u + ".vcc", _u + ".gnd"]
    SINK_POS[_u + ".vcc"], SINK_POS[_u + ".gnd"] = pin_xy(_u, 14), pin_xy(_u, 7)
SINKS += ["dip.vcc", "pd.C", "pd.B", "pd.A", "seg.com"]      # DIP common pin, the three 10k pull-downs, display cathode
SINK_POS.update({"dip.vcc": (160, 216), "pd.C": (46, 392), "pd.B": (82, 392), "pd.A": (118, 392), "seg.com": (936, 300)})
for _g in ["N1", "N2", "N3"] + ["A%d" % i for i in range(1, 5)] + ["O%d" % i for i in range(1, 9)]:
    _kind, _u, _ins, _y = GATES[_g]
    GATE_IN[_g] = []
    for _k, _p in enumerate(_ins):
        _s = "%s.%s" % (_g, "ab"[_k])
        SINKS.append(_s)
        SINK_POS[_s] = pin_xy(_u, _p)
        GATE_IN[_g].append(_s)
    SRC_POS[_g] = [pin_xy(_u, _y)]
for _i, _s in enumerate(SEGS):                   # 220 ohm resistor: input end (sink "s?") and output end (source "R?")
    SINKS.append("s" + _s)
    SINK_POS["s" + _s] = (610, 150 + _i * 48)
    SRC_POS["R" + _s] = [(722, 150 + _i * 48)]
for _i, _s in enumerate(SEGS):                   # the seven segment pins of the display
    SINKS.append("d" + _s)
    SINK_POS["d" + _s] = (766, 142 + _i * 32)
RAIL_X = [214, 294, 374, 454, 534]
RAIL_LINES = [("1", 122), ("0", 246), ("1", 298), ("0", 478)]     # +5V / GND rails (click anywhere on the line)
SRC_POS["C"], SRC_POS["B"], SRC_POS["A"] = [(160, 238)], [(160, 270)], [(160, 302)]
SRC_POS["1"] = [(x, y) for k, y in RAIL_LINES if k == "1" for x in RAIL_X]
SRC_POS["0"] = [(x, y) for k, y in RAIL_LINES if k == "0" for x in RAIL_X]
SRC_LIST = (["1", "0", "C", "B", "A"] + ["N1", "N2", "N3"] + ["A%d" % i for i in range(1, 5)] +
            ["O%d" % i for i in range(1, 9)] + ["R" + s for s in SEGS])
CUR_CLEAR = len(SINKS)
N_CUR = len(SINKS) + 1
BTN_CLEAR = pygame.Rect(790, 58, 154, 34)
BTN_AUTO = pygame.Rect(636, 58, 146, 34)         # TEST_MODE only

# one correct build (used by the smart hint item): sink -> source
REF = ([(u + ".vcc", "1") if k == 0 else (u + ".gnd", "0") for u in UNITS for k in (0, 1)] +
       [("dip.vcc", "1"), ("pd.C", "0"), ("pd.B", "0"), ("pd.A", "0"), ("seg.com", "0")] +
       [("N1.a", "C"), ("N2.a", "A"),
        ("A1.a", "B"), ("A1.b", "N2"), ("A2.a", "C"), ("A2.b", "A"), ("A3.a", "C"), ("A3.b", "O4"), ("A4.a", "C"), ("A4.b", "B"),
        ("O1.a", "N1"), ("O1.b", "B"), ("O2.a", "O1"), ("O2.b", "A"), ("O3.a", "A1"), ("O3.b", "A2"), ("O4.a", "A"), ("O4.b", "B"),
        ("O5.a", "A"), ("O5.b", "A4"), ("O6.a", "N1"), ("O6.b", "B"), ("O7.a", "C"), ("O7.b", "B"), ("O8.a", "O7"), ("O8.b", "N2"),
        ("sa", "O2"), ("sb", "O3"), ("sc", "A3"), ("sd", "O5"), ("se", "N1"), ("sf", "O6"), ("sg", "O8")] +
       [("d" + s, "R" + s) for s in SEGS])


def powered(w, u):                               # a chip works only with +5V on VCC and GND on its ground pin
    return w.get(u + ".vcc") == "1" and w.get(u + ".gnd") == "0"


def levels(w, c, b, a):                          # what the DIP switch really puts on its three outputs
    vcc = w.get("dip.vcc") == "1"

    def lv(on, pd):                              # ON needs +5V on the common pin; OFF needs the 10k pull-down to GND
        return 1 if (on and vcc) else (0 if pd else 1)     # without a pull-down an OFF input floats high
    return lv(c, w.get("pd.C") == "0"), lv(b, w.get("pd.B") == "0"), lv(a, w.get("pd.A") == "0")


def val(w, node, c, b, a, seen=()):              # logic value of a net; c, b, a = levels on the switch outputs
    if node == "1": return 1
    if node == "0": return 0
    if node == "C": return c
    if node == "B": return b
    if node == "A": return a
    if node in seen: return 0
    if len(node) == 2 and node[0] == "R":        # a 220 ohm resistor passes the level of its input end
        src = w.get("s" + node[1])
        return val(w, src, c, b, a, seen + (node,)) if src else 0
    kind, unit = GATES[node][0], GATES[node][1]
    if not powered(w, unit): return 0            # an unpowered chip outputs nothing
    xs = []
    for s in GATE_IN[node]:
        src = w.get(s)
        if src is None: return 0
        xs.append(val(w, src, c, b, a, seen + (node,)))
    return (1 - xs[0]) if kind == "not" else ((xs[0] & xs[1]) if kind == "and" else (xs[0] | xs[1]))


def seg_val(w, s, c, b, a):                      # is segment s lit? (c, b, a = switch positions)
    if w.get("seg.com") != "0": return 0         # the display needs its common cathode on GND
    src = w.get("d" + s)
    if not src: return 0
    ce, be, ae = levels(w, c, b, a)
    return val(w, src, ce, be, ae)


SINK_TEXT = {"dip.vcc": "DIP switch common pin (+5V)", "pd.C": "10k pull-down of switch C (to GND)",
             "pd.B": "10k pull-down of switch B (to GND)", "pd.A": "10k pull-down of switch A (to GND)",
             "seg.com": "display common cathode (GND)"}


def sink_name(s):
    if s in SINK_TEXT: return SINK_TEXT[s]
    if s.endswith(".vcc"): return "chip %s power pin (VCC)" % s[:2]
    if s.endswith(".gnd"): return "chip %s ground pin (GND)" % s[:2]
    if s[0] == "s" and len(s) == 2: return "220 ohm resistor %s (input end)" % s[1]
    if s[0] == "d" and len(s) == 2: return "display segment %s pin" % s[1]
    g, p = s.split(".")
    return "%s gate %s input %s" % ({"N": "NOT", "A": "AND", "O": "OR"}[g[0]], g, p.upper())


def src_name(s):
    if s is None: return "(no wire)"
    if len(s) == 2 and s[0] == "R": return "220 ohm resistor %s (output end)" % s[1]
    return {"C": "switch C", "B": "switch B", "A": "switch A", "1": "+5V rail", "0": "GND rail"}.get(s, "output of gate " + s)


def src_color(s):
    if s in ("C", "B", "A"): return (250, 196, 64)
    if s == "1": return (235, 80, 80)
    if s == "0": return (96, 128, 255)
    if s[0] == "R" and len(s) == 2: return (240, 150, 70)
    return {"N": (190, 130, 255), "A": (90, 205, 255), "O": (120, 230, 120)}[s[0]]


# ---------------- room layout (px in the 960x540 game area, matches bg.jpg) ----------------
# Everything inside FLOOR is walkable except the SOLIDS: desks, chairs, partitions and furniture of the picture.
FLOOR = pygame.Rect(100, 176, 830, 350)
SOLIDS = [
    [(100, 176), (180, 176), (180, 286), (100, 286)],                       # left wall / whiteboard base
    [(186, 176), (258, 176), (258, 272), (186, 272)],                       # gray cabinet + plant
    [(262, 182), (288, 182), (288, 220), (262, 220)],                       # pink beanbag
    [(100, 286), (178, 286), (178, 376), (100, 376)],                       # plant + water cooler
    [(100, 376), (150, 376), (150, 462), (100, 462)],                       # coffee counter
    [(208, 288), (246, 288), (246, 380), (208, 380)],                       # black chair (left corridor)
    [(322, 198), (636, 198), (636, 270), (322, 270)],                       # top row: desks, chairs, partitions
    [(284, 288), (656, 288), (656, 394), (272, 394), (272, 330)],           # middle row (open lanes above and below it)
    [(272, 412), (690, 412), (690, 494), (218, 494), (218, 440), (272, 440)],   # bottom row: back panels + desks
    [(232, 494), (292, 494), (292, 510), (232, 510)],                       # bottom row chairs (you can walk in front of them)
    [(466, 494), (522, 494), (522, 510), (466, 510)],
    [(546, 494), (606, 494), (606, 510), (546, 510)],
    [(206, 385), (224, 385), (204, 470), (190, 527), (163, 527), (178, 470)],   # bottom-left partition
    [(684, 381), (698, 381), (704, 494), (690, 494)],                       # bottom-right partition
    [(701, 176), (780, 176), (780, 262), (701, 262)],                       # shelf rack under the projector
    [(748, 258), (776, 258), (776, 284), (748, 284)],                       # plant pot on the rack
    [(667, 176), (700, 176), (700, 204), (667, 204)],                       # teal beanbag
    [(700, 268), (820, 268), (820, 360), (776, 412), (736, 384), (706, 330)],   # black desk
    [(805, 292), (831, 292), (831, 380), (805, 380)],                       # chair at the black desk
    [(780, 176), (930, 176), (930, 274), (843, 274), (780, 262)],           # right wall (cork board)
    [(745, 383), (803, 383), (803, 429), (745, 429)],                       # cardboard box + rolled posters
    [(843, 274), (930, 274), (930, 470), (843, 470)],                       # bookshelf
    [(873, 374), (930, 374), (930, 526), (873, 526)],                       # big plant
    [(719, 499), (771, 499), (771, 526), (719, 526)],                       # box at the bottom edge
]
SPAWN = (682.0, 300.0)


def make_walk_mask():
    m = pygame.Surface((UW, UH))
    m.fill((0, 0, 0))
    pygame.draw.rect(m, (255, 255, 255), FLOOR)
    for poly in SOLIDS:
        pygame.draw.polygon(m, (0, 0, 0), poly)
    return m

CARD_ITEMS = {1: ["HINT_HARD", "BOOST", "ARMOR"], 2: ["SHARD", "SLOW", "HINT_SMART"], 3: ["FREEZE", "UNDO", "SHARD"]}
ITEM_TEXT = {
    "HINT_HARD": ("Hint", "Use it from the inventory (I)."),
    "BOOST": ("Speed Boost", "Saved for the Obby stage. No effect here."),
    "ARMOR": ("Armor", "Blocks the next failed QA penalty."),
    "SHARD": ("Armor Shard", "Collect 2 shards to forge 1 Armor."),
    "SLOW": ("Slow", "You walk slower for 10 seconds."),
    "HINT_SMART": ("Hint", "Use it from the inventory (I)."),
    "FREEZE": ("Freeze", "Stops moving obstacles for 5 s. Saved for Stage 3."),
    "UNDO": ("Undo", "Reverts your latest wiring change."),
}
CAREERS = [("AIR", (60, 170, 80)), ("EARTH", (220, 190, 50)), ("WATER", (200, 60, 60))]
SYMBOLS = [["WING", "PLANE", "FART"], ["SHIP", "GEAR", "MONEY"], ["WORM", "WHITE FLAG", "PLUG"]]
PERMS = list(itertools.permutations([0, 1, 2]))
USABLE = ["HINT_HARD", "HINT_SMART", "UNDO", "FREEZE"]
FORM_COLORS = [(60, 110, 220), (90, 90, 100), (35, 35, 35), (240, 200, 60)]
FORM_NAMES = ["Student uniform", "Workshop suit", "Graduation gown", "Super Yasai"]

SEG_MAP = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg", "6": "acdefg",
           "7": "abc", "8": "abcdefg", "9": "abcdfg", "H": "bcefg", "-": "g", " ": "", "E": "adefg",
           "P": "abefg", "C": "adef", "A": "abcefg", "F": "aefg", "L": "def", "O": "abcdef",
           "U": "bcdef", "d": "bcdeg", "S": "acdfg"}


class Obj:
    def __init__(self, oid, kind, name, fx, fy, rect):
        self.id, self.kind, self.name, self.foot = oid, kind, name, (fx, fy)
        self.r, self.ax, self.ay = R_OBJ, 0, 0
        self.rect = pygame.Rect(rect)


OBJS = [
    Obj("whiteboard", "whiteboard", "Work-order board", 150, 300, (78, 86, 108, 240)),
    Obj("door", "door", "Exit door", 622, 176, (581, 53, 86, 116)),
    Obj("bench", "bench", "Decoder bench", 600, 432, (447, 420, 246, 79)),
]
NPC_NAME = "Boss"
NPC_OBJ = Obj("npc", "npc", "Talk to the Boss", 815, 395, (795, 285, 50, 60))
NPC_SEAT = (818.0, 336.0)                        # the black chair at the desk on the right
NPC_SPEED = 150.0
INTRO_LINES = [
    "Welcome to the lab, intern! I am your Boss.",
    "Today's job: build a 7-segment decoder on the bench. It must show the characters C, P, E, -, 3 and 9.",
    "First, collect the 18 parts hidden around the office. Walk close to anything suspicious and press Space to search it. "
    "Notes, screens and boards hold hints.",
    "You are wearing the workshop shirt you earned in the last stage. It has a skill: for 10 seconds you can SEE the hidden parts. "
    "Watch, I will show you once!",
    "See them glowing? Work for 2 minutes and you can use the skill one more time, whenever you like. "
    "A SKILL button lights up at the top right (key E, or flip SW13).",
    "When you have everything, go to the decoder bench at the bottom-right desk and wire the breadboard: give every chip +5V and GND, "
    "power the DIP switch, add the pull-down and display resistors. The switches SW2-SW0 let you test your circuit.",
    "Finished? Bring it to me. I will test it and tell you if it is right or wrong. A wrong answer costs a heart!",
    "I will be at my desk on the right. Good luck!",
]
PAGED = ("whiteboard", "bench")
SKILL_LINE = 3                                   # intro line shown while the Boss demonstrates the skill
SKILL_SECS, SKILL_WAIT = 10.0, 120.0             # reveal time / play time before the skill can be used again
SKILL_BTN = pygame.Rect(UW - 160, 50, 146, 28)   # on-screen skill button (map view)
# partition rows you can walk BEHIND: (x0, x1, walk-lane bottom, y of the partition's top edge in the picture).
# While your feet are in that lane, everything below the partition's top edge is covered by the room picture.
ROW_LANES = [(322, 636, 198, 186), (284, 656, 288, 270), (272, 690, 412, 413)]
LANE_H = 24
ZOOM_SECS, ZOOM_MAX = 2.2, 2.6                   # camera zoom when a part is found


def draw_set(scr, on, x, y, w, h, off=(50, 22, 22)):
    t = max(3, w // 6)
    h2 = h // 2
    segs = {"a": (x + t, y, w - 2 * t, t), "b": (x + w - t, y + t, t, h2 - t),
            "c": (x + w - t, y + h2, t, h2 - t), "d": (x + t, y + h - t, w - 2 * t, t),
            "e": (x, y + h2, t, h2 - t), "f": (x, y + t, t, h2 - t),
            "g": (x + t, y + h2 - t // 2, w - 2 * t, t)}
    for k, r in segs.items():
        pygame.draw.rect(scr, (255, 60, 40) if k in on else off, r)


def sw_cx(i):
    return 360 + (15 - i) * 48 + 22


def near(pos, pt, r):
    return (pos[0] - pt[0]) ** 2 + (pos[1] - pt[1]) ** 2 <= r * r


def bez(p0, p1, p2, p3, n=22):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        pts.append((u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                    u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]))
    return pts


def wire_pts(a, b):
    (x1, y1), (x2, y2) = a, b
    if abs(y2 - y1) < 40:
        if y2 != y1: off = 26 if y2 > y1 else -26          # short vertical hop (e.g. rail -> chip pin): stay close
        else: off = -45 if y1 < 300 else 45                # same height: arc over / under
        return bez(a, (x1, y1 + off), (x2, y2 + off), b)
    m = (y1 + y2) / 2
    return bez(a, (x1, m), (x2, m), b)


class Game:
        # ---- demo hub interface (for stage 2) ----
    CHECKPOINTS = [
        ("start", "Start of stage"),
        ("parts", "All 4 parts collected"),
        ("bench", "Decoder bench powered on"),
        ("qa1", "Passed QA round 1"),
        ("qa3", "All 3 QA rounds cleared (Door open)"),
        ("clear", "Stage 2 cleared")
    ]
    ACTIONS = [
        ("give_parts", "Collect all 4 parts"),
        ("give_armor", "Give 1 Armor"),
        ("wrong_qa", "Trigger QA failure penalty")
    ]

    def start(self, handoff=None):
        self.reset_stage(True)
        self.show_help = False

    def get_handoff(self):
        return {
            "hearts": getattr(self, "hearts", 3),
            "form": getattr(self, "form", 0),
            "armor": getattr(self, "armor", 0),
            "boost": getattr(self, "boost", False),
            "shards": getattr(self, "shard", 0)
        }

    def get_progress(self):
        if getattr(self, "state", "") == "clear":
            return 5
        # เช็กความคืบหน้าตามกลไกของ Stage 2
        parts_collected = len(getattr(self, "parts", {})) >= 4
        qa_rnd = getattr(self, "rnd", 0)
        if qa_rnd >= 3:
            return 4
        if qa_rnd >= 1:
            return 3
        if parts_collected:
            # สมมติถ้าเปิดบอร์ด/เดคโคเดอร์แล้ว ให้ดันขึ้นไปขั้น 2
            return 2 if getattr(self, "page", 0) > 0 else 1
        return 0

    def set_hearts(self, n):
        self.hearts = max(1, min(3, n))
        if getattr(self, "state", "") == "over":
            self.state = "play"

    def set_form(self, i):
        self.form = max(0, min(3, i))

    def toggle_debug(self):
        self.debug = not getattr(self, "debug", False)

    def jump_to(self, key):
        career = self.career
        self.career = career if career is not None else 1
        self.reset_stage(True)
        self.show_help = False
        if key == "start":
            return
        if key == "clear":
            self.state = "clear"
            return
        # จำลองการกระโดดข้ามขั้นตอนตาม Checkpoint
        if key in ("parts", "bench", "qa1", "qa3"):
            # บังคับให้เก็บชิ้นส่วนครบ 4 ชิ้น
            if hasattr(self, "parts"):
                self.parts = {"and1": True, "and2": True, "or": True, "not": True}
        if key in ("bench", "qa1", "qa3"):
            self.page = 1  # เปิดหน้าจอเดคโคเดอร์
        if key in ("qa1", "qa3"):
            self.rnd = 1   # ผ่านรอบที่ 1
        if key == "qa3":
            self.rnd = 3   # ผ่านครบ 3 รอบ ปลดล็อกประตู

    def do_action(self, key):
        if key == "give_parts":
            if hasattr(self, "parts"):
                self.parts = {"and1": True, "and2": True, "or": True, "not": True}
                self.say("[DEBUG] Collected all 4 parts")
        elif key == "give_armor":
            if hasattr(self, "armor"):
                self.armor = min(3, self.armor + 1)
                self.say("Armor +1")
        elif key == "wrong_qa":
            # จำลองการตอบคำถามผิดเพื่อทดสอบระบบหักหัวใจ/เกราะ
            if hasattr(self, "hearts"):
                self.hearts = max(0, self.hearts - 1)
                self.say("[DEBUG] Triggered QA penalty (-1 heart)")
    def __init__(self):
        self.f_tiny = pygame.font.Font(None, 15)
        self.f_s = pygame.font.Font(None, 20)
        self.f_m = pygame.font.Font(None, 26)
        self.f_l = pygame.font.Font(None, 38)
        mono = "dejavusansmono,consolas,menlo,couriernew"
        self.f_mono = pygame.font.SysFont(mono, 17)
        self.f_mono_l = pygame.font.SysFont(mono, 25)
        self.bg = load_img("bg.jpg", (UW, UH)) or load_img("internship.jpg", (UW, UH))
        print("[assets] background:", find_asset("bg.jpg") or find_asset("internship.jpg") or
              "NOT FOUND (looked in: %s)" % ", ".join(ASSET_DIRS))
        self.spr = PlayerSprite(ASSET_DIR, SPR_H)
        self.npc_img, self.npc_img_sit = self.scaled("npc_stand.png", SPR_H), self.scaled("npc_sit.png", 48)
        self.boss = BossSprite(SPR_H, 48)                                           # assets/Boss*.png (see BossSprite)
        self.cu_cache = {}
        self.bb_surf = self.make_breadboard()
        self.sw = [False] * 16
        self.sw_rects = [pygame.Rect(sw_cx(i) - 20, SCR_H + 36, 40, 34) for i in range(16)]
        self.c_down, self.c_long = None, False
        self.lfsr = (int(time.time() * 1000) & 0xFFFF) or 0xACE1
        self.debug = False
        self.show_help = True
        self.form = 1
        self._sw13 = False
        self._walking = False
        self.walk = make_walk_mask()
        self.reach = self.flood(SPAWN)
        for o in OBJS + [NPC_OBJ] + ITEM_SPOTS + HINT_SPOTS:
            self.set_anchor(o)
        self.reset_stage(True)
        self.card_art = card_assets.CardAssets(ASSET_DIR) if card_assets else None
        self.standalone = True          # demo_hub sets this to False when it runs the game

    def make_breadboard(self):
        s = pygame.Surface((928, 384))
        s.fill((226, 222, 208))
        for x in range(10, 928, 12):
            for y in range(8, 384, 12):
                s.fill((186, 182, 168), (x, y, 3, 3))
        return s

    def reset_stage(self, full=False):
        if full:
            self.form = 1
        self.px, self.py = SPAWN
        self.mode, self.cur, self.page, self.cmsg = "map", None, 0, ""
        self.state = "play"
        self.exit_requested = False
        self.found = {k: 0 for k in PART_QTY}                       # parts collected so far
        self.done_spots, self.read_hints = set(), set()
        self.rnd, self.codes, self.qa_pairs = 0, None, None         # QA tests cleared / current test inputs / the 3 pairs
        self.w = {}                                                 # wiring: sink -> source
        self.wcur, self.wsrc, self.wprev, self.msel = 0, None, None, None
        self.undo_rec = None
        self.notes, self.hints_seen = [], []
        self.hh = self.hs = self.undo = self.freeze = self.armor = self.shard = 0
        self.boost, self.slow_t = False, 0.0
        self.hearts = 3
        self.deck = {"active": False, "round": 1, "perm": (0, 1, 2), "cursor": 1, "face": None}
        self.career = self.lfsr_pick(3)                             # no card draw at the start: the career is picked silently (used by the round 2 / 3 card pictures)
        self.r_run = {1: True, 2: False, 3: False}                  # round 1 (the start card) is skipped
        self.r_done = {1: True, 2: False, 3: False}
        self.hint_popup, self.hint_title, self.toast, self.inv_cur = None, "HINT", ("", 0), 0
        self.flash, self.over_until = 0.0, 0.0
        self.play_t, self.skill_t, self.skill_used, self.zoom = 0.0, 0.0, False, None
        self.npc = {"x": 622.0, "y": 186.0, "state": "off", "path": [], "walk": False}   # the Boss
        self.talk, self.intro_started, self.cutscene = None, False, False
        if self.spr: self.spr.reset()

    def say(self, text, secs=2.5):
        self.toast = (text, time.time() + secs)

    def parts_total(self): return sum(self.found.values())

    # ---------------- demo hub hooks ----------------
    def start(self, handoff=None):
        self.reset_stage(True)
        self.show_help = False
        if handoff:
            if handoff.get("career") in (0, 1, 2): self.career = handoff["career"]      # career chosen in the previous stage (optional)
            self.hearts = max(1, min(3, handoff.get("hearts", 3)))
            self.form = max(0, min(3, handoff.get("form", 1)))
            self.armor = max(0, min(3, handoff.get("armor", 0)))
            self.boost = bool(handoff.get("boost", False))
            self.shard = int(handoff.get("shards", 0))

            # --- [จุดที่เพิ่ม] รับค่า career มาจากฮับหรือสเตจก่อนหน้า ---

            if "career" in handoff:

                self.career = handoff["career"]

    def get_handoff(self):
        return {
            "hearts": self.hearts,
            "form": self.form,
            "armor": self.armor,
            "boost": self.boost,
            "shards": self.shard,
            "career": self.career,
        }

    def get_progress(self):
        if self.state == "clear": return 5
        if self.rnd >= ROUNDS: return 4
        if self.r_run[3] or self.rnd >= 2: return 3
        if self.parts_total() >= TOTAL_PARTS: return 2
        if self.r_run[2] or self.parts_total() >= CARD2_AT: return 1
        return 0

    def set_hearts(self, n):
        self.hearts = max(1, min(3, n))
        if self.state == "over":
            self.state = "play"

    def set_form(self, i):
        self.form = max(0, min(3, i))

    def toggle_debug(self):
        self.debug = not self.debug

    def jump_to(self, key):
        form = self.form
        self.reset_stage(True)
        self.form = form
        self.show_help = False
        if key == "start":
            return
        if key == "clear":
            self.state, self.form = "clear", 2
            return

        # ข้ามการ์ดรอบ 1 และข้ามคัตซีน Boss เดินเข้าห้อง (ให้ Boss นั่งรอที่โต๊ะเลย)
        self.career = 0
        self.r_run[1] = self.r_done[1] = True
        self.intro_started, self.cutscene, self.talk = True, False, None
        self.npc = {"x": NPC_SEAT[0], "y": NPC_SEAT[1], "state": "sit", "path": [], "walk": False}

        if key == "r2":
            for sp in ITEM_SPOTS[:CARD2_AT]:
                self.done_spots.add(sp.id)
                self.found[sp.part] += 1
            return

        # ตั้งแต่ parts / r3 / door ขึ้นไป: เก็บครบ 18 ชิ้น + ข้ามการ์ดรอบ 2
        self.cheat_parts()
        self.r_run[2] = self.r_done[2] = True
        self.new_round()

        if key == "parts":
            return

        # ต่อวงจรให้เสร็จพร้อมเทสต์
        self.w = dict(REF)
        if key == "r3":
            self.rnd = 2
            self.new_round()
            return

        if key == "door":
            self.rnd = ROUNDS
            self.r_run[3] = self.r_done[3] = True
            self.say("All 3 QA passed! Go to the exit door.")

    def do_action(self, key):
        if key == "auto_wire":
            self.auto_wire()
            self.say("Circuit auto-wired! Talk to the Boss.")
        elif key == "skill_ready":
            self.play_t = SKILL_WAIT
            self.skill_used = False
            self.skill_t = 0.0
            self.say("Workshop-shirt skill ready! (Press E)")
        elif key == "armor":
            self.armor = min(3, self.armor + 1)
            self.say("Armor +1")

    # ---------------- input ----------------
    def poll(self, events):
        ev = dict(up=0, down=0, left=0, right=0, tap=0, back=0, skill=0, click=None, rclick=None)
        now = time.time()
        for e in events:
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.MOUSEBUTTONDOWN:
                for i, r in enumerate(self.sw_rects):
                    if r.collidepoint(e.pos):
                        self.sw[i] = not self.sw[i]
                if e.pos[1] < SCR_H:                 # click inside the game area -> UI-surface coordinates
                    p = (e.pos[0] * UW / SCR_W, e.pos[1] * UH / SCR_H)
                    if e.button == 1: ev["click"] = p
                    elif e.button == 3: ev["rclick"] = p
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
                elif pygame.K_1 <= k <= pygame.K_8: self.sw[k - pygame.K_1] = not self.sw[k - pygame.K_1]
                elif k == pygame.K_i: self.sw[15] = not self.sw[15]
                elif k == pygame.K_n: self.sw[14] = not self.sw[14]
                elif k == pygame.K_h: self.show_help = not self.show_help
                elif k == pygame.K_e: ev["skill"] = 1
                elif k in (pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4): self.form = k - pygame.K_F1
                elif k == pygame.K_F5: self.cheat_solve()
                elif k == pygame.K_F6: self.debug = not self.debug
                elif k == pygame.K_F7 and TEST_MODE: self.cheat_parts()
                elif k == pygame.K_F8 and TEST_MODE: self.auto_wire()
                elif k == pygame.K_F9 and TEST_MODE: self.play_t = SKILL_WAIT
            if e.type == pygame.KEYUP and e.key in (pygame.K_SPACE, pygame.K_RETURN):
                if self.c_down is not None and not self.c_long:
                    ev["tap"] = 1
                self.c_down = None
        if self.c_down is not None and not self.c_long and now - self.c_down >= LONG_PRESS_S:
            self.c_long = True
            ev["back"] = 1
        return ev

    def cheat_parts(self):               # TEST_MODE (F7): get all 18 parts at once
        for sp in ITEM_SPOTS:
            if sp.id not in self.done_spots:
                self.done_spots.add(sp.id)
                self.found[sp.part] += 1
        self.notes.append("[TEST] all parts collected")
        self.say("[TEST] all 18 parts collected")

    def auto_wire(self):                 # TEST_MODE (F8 / board button): the whole circuit is wired for you
        if self.parts_total() < TOTAL_PARTS: self.cheat_parts()
        if self.codes is None and self.rnd < ROUNDS: self.new_round()
        self.rec_undo()
        self.w = dict(REF)
        self.wsrc = self.msel = None
        self.cmsg = "[TEST] Circuit wired. Now show it to the Boss (Esc, then walk to his desk)."
        self.notes.append("[TEST] circuit auto-wired")

    def cheat_solve(self):
        for sp in ITEM_SPOTS:
            if sp.id not in self.done_spots:
                self.pickup(sp)
                return self.say("[DEBUG] found %s" % sp.name)
        if self.rnd < ROUNDS:
            self.rnd += 1
            self.say("[DEBUG] QA test %d marked clear" % self.rnd)
            if self.rnd < ROUNDS: self.new_round()

    # ---------------- random (LFSR) ----------------
    def lfsr_step(self):
        q = self.lfsr
        fb = ((q >> 15) ^ (q >> 14) ^ (q >> 12) ^ (q >> 3)) & 1
        q = ((q << 1) | fb) & 0xFFFF
        self.lfsr = q if q else 0xACE1

    def lfsr_pick(self, n):              # LFSR value 0..n-1 (n <= 8): take 3 bits, retry if out of range
        while True:
            self.lfsr_step()
            v = self.lfsr & 7
            if v < n:
                return v

    def card_start(self, r):
        # ถ้ารอบ 2 (รอบแรกของ Stage 2) ให้สอดรับกับ career ที่เคยเลือกไว้จาก Stage 1
        # แต่ถ้าไม่มี ให้สุ่มใหม่ตามปกติ
        self.deck = {"active": True, "round": r, "perm": PERMS[self.lfsr_pick(6)], "cursor": 1, "face": None}
        self.r_run[r] = True

    def card_trigger(self):              # round 1: skipped | round 2: 8 parts found | round 3: all 18 parts found
        if self.deck["active"]:
            return
        if self.zoom: return                                        # wait until the found-part zoom has finished
        elif self.r_done[1] and not self.r_run[2] and self.parts_total() >= CARD2_AT: self.card_start(2)
        elif self.r_done[2] and not self.r_run[3] and self.parts_total() >= CARD3_AT: self.card_start(3)

    def cards_input(self, ev):
        d = self.deck
        if d["face"] is None:
            if ev["left"]: d["cursor"] = (d["cursor"] - 1) % 3
            elif ev["right"]: d["cursor"] = (d["cursor"] + 1) % 3
            elif ev["tap"]:
                d["face"] = d["cursor"]
                idx = d["perm"][d["cursor"]]
                if d["round"] == 1: self.career = idx
                self.grant(CARD_ITEMS[d["round"]][idx])
        elif ev["tap"]:
            d["active"] = False
            self.r_done[d["round"]] = True

    def grant(self, item):
        cap = lambda v: min(3, v + 1)
        if item == "HINT_HARD": self.hh = cap(self.hh)
        elif item == "HINT_SMART": self.hs = cap(self.hs)
        elif item == "UNDO": self.undo = cap(self.undo)
        elif item == "FREEZE": self.freeze = cap(self.freeze)
        elif item == "ARMOR": self.armor = cap(self.armor)
        elif item == "BOOST": self.boost = True
        elif item == "SLOW": self.slow_t = 10.0
        elif item == "SHARD":
            self.shard += 1
            if self.shard >= 2:
                self.shard = 0
                self.armor = cap(self.armor)

    # ---------------- part hunt ----------------
    def pickup(self, sp):
        self.done_spots.add(sp.id)
        self.found[sp.part] += 1
        self.zoom = {"t": 0.0, "x": sp.ix, "y": sp.iy, "part": sp.part}      # camera zooms to the spot
        left = TOTAL_PARTS - self.parts_total()
        self.notes.append("Found %s (%s)" % (PART_SHORT[sp.part], sp.name))
        self.say("Found: %s  (%d/%d)" % (PART_LABEL[sp.part], self.found[sp.part], PART_QTY[sp.part]))
        if left == 0:
            self.say("All 18 parts found! Go to the decoder bench.", 4.0)

    def open_hint(self, h):
        self.read_hints.add(h.id)
        self.show_hint(h.text, h.title)
        if "Hint: " + h.title not in self.notes:
            self.notes.append("Hint: " + h.title)

    # ---------------- decoder wiring ----------------
    def make_pairs(self):                # the 6 characters are shuffled (LFSR) into 3 pairs: QA test 1, 2 and 3
        order = [1, 2, 3, 4, 5, 6]
        for i in range(5, 0, -1):
            j = self.lfsr_pick(i + 1)
            order[i], order[j] = order[j], order[i]
        self.qa_pairs = [(order[0], order[1]), (order[2], order[3]), (order[4], order[5])]

    def new_round(self):                 # the next QA test checks the next 2 characters; the circuit stays
        if self.qa_pairs is None: self.make_pairs()
        self.codes = list(self.qa_pairs[min(self.rnd, ROUNDS - 1)])
        self.undo_rec = None

    def on_of(self, k):                  # segments your circuit lights for input code k
        c, b, a = bits(k)
        return "".join(s for s in SEGS if seg_val(self.w, s, c, b, a))

    def seg_ok(self, s):                 # segment s matches the target on both test inputs
        return all(seg_val(self.w, s, *bits(k)) == int(s in GOLD[k]) for k in self.codes)

    def code3(self): return sum(1 << i for i in range(3) if self.sw[i])

    def wiring_live(self):
        return (self.mode == "closeup" and self.cur is not None and self.cur.kind == "bench"
                and self.page == 1 and self.codes is not None)

    def rec_undo(self):
        self.undo_rec = copy.deepcopy(self.w)

    def set_wire(self, sink, src):
        if src is None: self.w.pop(sink, None)
        else: self.w[sink] = src

    # ---------------- NPC: the Boss explains, then sits down and judges the circuit ----------------
    def scaled(self, name, h):
        img = load_img(name)
        return pygame.transform.smoothscale(img, (max(1, round(img.get_width() * h / img.get_height())), h)) if img else None

    def find_path(self, start, goal):    # shortest walk on the real floor (same grid as the player)
        near_cell = lambda q: min(self.reach, key=lambda p: (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2)
        s, g = near_cell(start), near_cell(goal)
        prev, todo = {s: None}, deque([s])
        while todo:
            c = todo.popleft()
            if c == g: break
            for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                n = (c[0] + dx, c[1] + dy)
                if n in self.reach and n not in prev:
                    prev[n] = c
                    todo.append(n)
        path, c = [], g
        while c is not None:
            path.append(c)
            c = prev[c]
        return path[::-1]

    def start_intro(self):               # after the first card: the Boss comes in through the door
        self.intro_started, self.cutscene = True, True
        n = self.npc
        n.update(x=622.0, y=186.0, state="to_player", walk=True)
        path = self.find_path((n["x"], n["y"]), (self.px, self.py))
        n["path"] = path[:max(1, len(path) - 14)]

    def npc_update(self, dt):
        n = self.npc
        n["walk"] = bool(n["path"]) and n["state"] in ("to_player", "to_seat")
        if n["walk"]:
            budget = NPC_SPEED * dt
            while budget > 0 and n["path"]:
                tx, ty = n["path"][0]
                d = math.hypot(tx - n["x"], ty - n["y"])
                if d > 0.5:                                                  # facing for the Boss skin
                    ddx, ddy = tx - n["x"], ty - n["y"]
                    n["dir"] = ("right" if ddx > 0 else "left") if abs(ddx) >= abs(ddy) else ("front" if ddy > 0 else "back")
                if d <= budget:
                    n["x"], n["y"] = float(tx), float(ty)
                    n["path"].pop(0)
                    budget -= d
                else:
                    n["x"] += (tx - n["x"]) / d * budget
                    n["y"] += (ty - n["y"]) / d * budget
                    budget = 0
        if n["state"] == "to_player" and not n["path"]:
            n["state"] = "talk"
            self.open_talk(INTRO_LINES, "intro")
        elif n["state"] == "to_seat" and not n["path"]:
            n["state"], self.cutscene = "sit", False

    def open_talk(self, lines, tag, ask=False, result=None):
        self.talk = {"lines": lines, "i": 0, "tag": tag, "ask": ask, "result": result}

    def talk_input(self, ev):
        t = self.talk
        last = t["i"] >= len(t["lines"]) - 1
        if ev["tap"]:
            if not last:
                t["i"] += 1
                if t["tag"] == "intro" and t["i"] == SKILL_LINE: self.start_skill()
            else: self.talk_done(True)
        elif ev["back"] and t["ask"] and last:
            self.talk_done(False)
        elif ev["back"] and TEST_MODE and t["tag"] == "intro":      # test: skip the introduction
            self.talk_done(True)

    def talk_done(self, yes):
        t, self.talk = self.talk, None
        if t["tag"] == "intro":                      # the Boss walks to the desk and sits down
            n = self.npc
            n["state"] = "to_seat"
            n["path"] = self.find_path((n["x"], n["y"]), (NPC_OBJ.ax, NPC_OBJ.ay)) + [NPC_SEAT]
            self.notes.append("Boss: bring the finished circuit to me (desk on the right).")
        elif t["tag"] == "ask" and yes:
            self.judge()
        elif t["tag"] == "verdict":
            if t["result"] == "fail":
                self.damage()
            else:
                self.rnd += 1
                if self.rnd >= ROUNDS: self.say("The exit door is unlocked!")
                else: self.new_round()

    def npc_interact(self):
        if self.codes is None:
            self.open_talk(["Come back when the decoder is built.",
                            "Find all 18 parts, install them on the decoder bench, then wire the breadboard."], "info")
        elif self.rnd >= ROUNDS:
            self.open_talk(["Everything is verified. Leave through the exit door!"], "info")
        else:
            self.open_talk(["Is your circuit finished?",
                            "QA test %d of %d: I will check the two inputs of the work order.   Space = test it     Esc = not yet"
                            % (self.rnd + 1, ROUNDS)], "ask", ask=True)

    def judge(self):                     # the Boss tests the circuit and tells right or wrong
        res = [(k, set(self.on_of(k)) == set(GOLD[k])) for k in self.codes]
        good = sum(ok for _, ok in res)
        lines = ["Let me test your circuit..."]
        for k, ok in res:
            lines.append("Input %d%d%d (must show %s): %s" % (bits(k) + (CHAR_NAME[k], "correct!" if ok else "WRONG.")))
        self.notes.append("QA test %d: Boss says %d/2 correct" % (self.rnd + 1, good))
        if good == 2:
            if self.rnd + 1 >= ROUNDS:
                lines.append("All %d tests passed! The decoder is verified. You may leave through the exit door." % ROUNDS)
            else:
                lines.append("Test %d of %d passed! That covered %s and %s. I still have to check the other characters: "
                             "%d more test%s. If your circuit is right you do not need to change anything, just come back and ask me again."
                             % (self.rnd + 1, ROUNDS, CHAR_NAME[self.codes[0]], CHAR_NAME[self.codes[1]],
                                ROUNDS - self.rnd - 1, "" if ROUNDS - self.rnd - 1 == 1 else "s"))
            self.open_talk(lines, "verdict", result="pass")
        else:
            lines.append("Not right. Go back to the bench and fix it. " +
                         ("Your armor takes the hit this time." if self.armor > 0 else "That costs you a heart."))
            self.open_talk(lines, "verdict", result="fail")

    def damage(self):
        if self.armor > 0:
            self.armor -= 1
            return self.say("ARMOR PROTECTED!")
        self.hearts -= 1
        self.flash = 0.4
        if self.hearts <= 0:
            self.state, self.over_until = "over", time.time() + 3.0
        else:
            self.say("QA failed! -1 heart")

    # ---------------- items ----------------
    def wiring_hint(self, exact):
        for s in SEGS:
            if self.seg_ok(s):
                continue
            t = [int(s in GOLD[k]) for k in self.codes]
            ins = ["%d%d%d" % bits(k) for k in self.codes]
            if not exact:
                return "Segment %s must be %s for input %s and %s for input %s." % (
                    s, "ON" if t[0] else "OFF", ins[0], "ON" if t[1] else "OFF", ins[1])
            for sink, src in REF:
                if self.w.get(sink) != src:
                    return "Try this next: wire the %s to the %s." % (sink_name(sink), src_name(src))
        return "Every segment already matches. Show it to the Boss."

    def smart_hint(self):
        missing = [sp for sp in ITEM_SPOTS if sp.id not in self.done_spots]
        if missing: return "Clue: " + missing[self.lfsr_pick(8) % len(missing)].clue
        if self.rnd >= ROUNDS: return None
        if self.codes is None: return "All parts found. Go to the decoder bench and power it on."
        return self.wiring_hint(True)

    def show_hint(self, text, title="HINT"):
        self.hint_popup, self.hint_title = text, title
        if text not in self.hints_seen:
            self.hints_seen.append(text)

    def use_item(self, name):
        if name == "HINT_HARD":
            if self.hh == 0: return self.say("You do not have this item.")
            if self.rnd >= ROUNDS: return self.say("Not useful now: the decoder is already verified.")
            if self.codes is None: return self.say("Not useful yet: power on the decoder bench first.")
            self.hh -= 1; self.show_hint(self.wiring_hint(False))
        elif name == "HINT_SMART":
            if self.hs == 0: return self.say("You do not have this item.")
            h = self.smart_hint()
            if h is None: return self.say("Not useful now: nothing left to hint.")
            self.hs -= 1; self.show_hint(h)
        elif name == "UNDO":
            if self.undo == 0: return self.say("You do not have this item.")
            if self.undo_rec is None or self.rnd >= ROUNDS: return self.say("Nothing to undo right now.")
            self.undo -= 1
            self.w, self.undo_rec, self.wsrc, self.msel = self.undo_rec, None, None, None
            self.say("Your last wiring change was undone.")
        elif name == "FREEZE":
            if self.freeze == 0: return self.say("You do not have this item.")
            self.say("No moving obstacles here. Keep it for Stage 3.")

    def inventory_input(self, ev):
        if ev["left"]: self.inv_cur = (self.inv_cur - 1) % 4
        elif ev["right"]: self.inv_cur = (self.inv_cur + 1) % 4
        elif ev["tap"]: self.use_item(USABLE[self.inv_cur])

    # ---------------- update ----------------
    def update(self, dt, ev):
        self._walking = False
        self._update(dt, ev)
        if self.spr and not self._walking: self.spr.stop()

    def _update(self, dt, ev):
        for _ in range(7): self.lfsr_step()
        self.flash = max(0.0, self.flash - dt)
        if self.show_help:
            if ev["tap"] or ev["back"]: self.show_help = False
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
        self.skill_t = max(0.0, self.skill_t - dt)                  # the skill keeps counting, even during a dialogue
        if self.zoom:
            self.zoom["t"] += dt
            if self.zoom["t"] >= ZOOM_SECS: self.zoom = None
        press = ev["skill"] or (self.sw[13] and not self._sw13) or (ev["click"] and SKILL_BTN.collidepoint(ev["click"]) and self.mode == "map")
        self._sw13 = self.sw[13]
        self.card_trigger()
        if self.deck["active"]: self.cards_input(ev); return
        if self.r_done[1] and not self.intro_started: self.start_intro()
        self.npc_update(dt)
        if self.talk: self.talk_input(ev); return
        if self.cutscene: return
        self.play_t += dt                                           # play time since the Boss sat down
        if self.zoom:                                               # camera zoom on the part you just found (Space skips it)
            if ev["tap"] and self.zoom["t"] > 0.8: self.zoom = None
            return
        if press: self.try_skill()
        if self.hint_popup:
            if ev["tap"] or ev["back"]: self.hint_popup = None
            return
        if self.sw[15]: self.inventory_input(ev); return
        if self.sw[14]: return
        if self.mode == "map": self.map_update(dt, ev)
        else: self.closeup_input(ev)

    # ---------------- workshop-shirt skill: see the hidden parts for 10 s ----------------
    def look(self):                      # skin drawn: the workshop shirt (form 1) all the time; gown (form 2) after clearing
        return self.form

    def skill_ready(self):
        return self.play_t >= SKILL_WAIT and not self.skill_used and self.skill_t <= 0

    def start_skill(self):
        self.skill_t = SKILL_SECS

    def try_skill(self):
        if self.skill_t > 0: return self.say("The skill is already on!")
        if self.skill_used: return self.say("You already used the skill again.")
        if self.play_t < SKILL_WAIT: return self.say("Skill recharging: %d s left" % math.ceil(SKILL_WAIT - self.play_t))
        if self.mode != "map": return self.say("Use the skill while walking around the office.")
        self.skill_used = True
        self.start_skill()
        self.say("WORKSHOP SHIRT: hidden parts revealed for %d s!" % SKILL_SECS)

    def speed(self):
        s = BASE_SPEED * 1.2
        return s * 0.5 if self.slow_t > 0 else s

    def blocked(self, x, y):             # true if any sample point of the feet box is on a solid or off the floor
        x, y = int(x), int(y)
        l, r, t, b = x - FEET_HW, x + FEET_HW, y - FEET_H, y
        for px, py in ((l, t), (r, t), (l, b), (r, b), (x, t), (x, b), (l, (t + b) // 2), (r, (t + b) // 2)):
            if px < 0 or py < 0 or px >= UW or py >= UH or self.walk.get_at((px, py))[0] < 128:
                return True
        return False

    def flood(self, start):             # every floor point the player can really walk to
        s = (int(start[0]), int(start[1]))
        seen, todo = {s}, [s]
        while todo:
            x, y = todo.pop()
            for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                n = (x + dx, y + dy)
                if n not in seen and not self.blocked(*n):
                    seen.add(n)
                    todo.append(n)
        return seen

    def set_anchor(self, o):            # the walkable point nearest to the thing's base = where you stand to use it
        fx, fy = o.foot
        o.ax, o.ay = min(self.reach, key=lambda p: (p[0] - fx) ** 2 + (p[1] - fy) ** 2)

    def find_near(self):                 # nearest thing the player can use: ("obj"|"item"|"hint", thing)
        best, bs = None, 1.0001
        cands = [("obj", o) for o in OBJS] + ([("npc", NPC_OBJ)] if self.npc["state"] == "sit" else []) + \
                [("item", sp) for sp in ITEM_SPOTS if sp.id not in self.done_spots] + \
                [("hint", h) for h in HINT_SPOTS if h.id not in self.read_hints]
        for kind, o in cands:
            score = math.hypot(self.px - o.ax, self.py - o.ay) / o.r
            if score < bs:
                best, bs = (kind, o), score
        return best

    def map_update(self, dt, ev):
        k = pygame.key.get_pressed()
        dx = int(k[pygame.K_RIGHT] or k[pygame.K_d]) - int(k[pygame.K_LEFT] or k[pygame.K_a])
        dy = int(k[pygame.K_DOWN] or k[pygame.K_s]) - int(k[pygame.K_UP] or k[pygame.K_w])
        sp = self.speed() * dt
        ox, oy = self.px, self.py
        if dx:
            if not self.blocked(self.px + dx * sp, self.py): self.px += dx * sp
            else:                                    # slide along a slanted wall instead of getting stuck
                for n in (sp * 0.7, -sp * 0.7):
                    if not self.blocked(self.px + dx * sp, self.py + n):
                        self.px += dx * sp; self.py += n
                        break
        if dy:
            if not self.blocked(self.px, self.py + dy * sp): self.py += dy * sp
            else:
                for n in (sp * 0.7, -sp * 0.7):
                    if not self.blocked(self.px + n, self.py + dy * sp):
                        self.px += n; self.py += dy * sp
                        break
        if self.spr:
            self.spr.update(dt, dx, dy, (self.px, self.py) != (ox, oy))
            self._walking = True
        if ev["tap"]:
            f = self.find_near()
            if not f: return
            kind, o = f
            if kind == "obj":
                self.mode, self.cur, self.page, self.cmsg = "closeup", o, 0, ""
            elif kind == "npc":
                self.npc_interact()
            elif kind == "item":
                self.pickup(o)
            else:
                self.open_hint(o)

    def closeup_input(self, ev):
        o = self.cur
        if ev["back"]:
            if self.wsrc is not None:                # cancel the source picker, put the old wire back
                self.set_wire(SINKS[self.wcur], self.wprev)
                self.wsrc = None
            elif self.msel is not None:
                self.msel = None
            elif self.page > 0 and o.kind in PAGED:
                self.page -= 1
            else:
                self.mode = "map"
            self.cmsg = ""
            return
        getattr(self, "in_" + o.kind)(ev)

    def in_whiteboard(self, ev):
        if ev["tap"]: self.page = (self.page + 1) % 3

    def in_door(self, ev):
        if not ev["tap"]: return
        if self.rnd >= ROUNDS: self.state, self.form = "clear", 2
        else: self.cmsg = "Locked. It opens when the decoder passes QA (%d / %d)." % (self.rnd, ROUNDS)

    def in_bench(self, ev):
        if self.page == 0:
            if ev["tap"]:
                missing = ["%s x%d" % (PART_SHORT[k], PART_QTY[k] - self.found[k]) for k in PART_QTY if self.found[k] < PART_QTY[k]]
                if missing:
                    self.cmsg = "Cannot power on. Missing: " + ", ".join(missing)
                else:
                    self.page = 1
                    if self.codes is None and self.rnd < ROUNDS:
                        self.new_round()
                        self.notes.append("All parts installed. Bench powered on.")
            return
        if self.rnd >= ROUNDS: return
        if ev["click"]: return self.bench_click(ev["click"])
        if ev["rclick"]:
            for sink in SINKS:
                if near(ev["rclick"], SINK_POS[sink], 11) and sink in self.w:
                    self.rec_undo()
                    del self.w[sink]
            return
        if self.wsrc is not None:                    # source picker: U/D changes the wire live
            sink = SINKS[self.wcur]
            opts = [None] + SRC_LIST
            if ev["up"] or ev["down"]:
                self.wsrc = (self.wsrc + (-1 if ev["up"] else 1)) % len(opts)
                self.set_wire(sink, opts[self.wsrc])
            elif ev["tap"]:
                self.wsrc = None
            return
        if ev["left"] or ev["right"] or ev["up"] or ev["down"]:   # the cursor moves to the nearest pin in the pressed direction
            self.wcur = self.cursor_step(self.wcur, (ev["right"] - ev["left"], ev["down"] - ev["up"]))
        elif ev["tap"]:
            self.msel = None
            if self.wcur == CUR_CLEAR:
                self.rec_undo()
                self.w = {}
            else:
                sink = SINKS[self.wcur]
                self.rec_undo()
                self.wprev = self.w.get(sink)
                self.wsrc = ([None] + SRC_LIST).index(self.wprev)
                self.cmsg = ""

    def cur_pos(self, i):                # screen position of cursor slot i (a pin, or the CLEAR ALL button)
        return BTN_CLEAR.center if i == CUR_CLEAR else SINK_POS[SINKS[i]]

    def cursor_step(self, cur, d):       # d = (dx, dy) of the pressed arrow; pick the closest pin lying that way (same row/column preferred)
        x0, y0 = self.cur_pos(cur)
        best, bs = cur, None
        for i in range(N_CUR):
            if i == cur: continue
            x, y = self.cur_pos(i)
            ax, ay = (x - x0) * d[0] + (y - y0) * d[1], abs((x - x0) * d[1]) + abs((y - y0) * d[0])   # along / across the pressed direction
            if ax < 4: continue
            sc = ax + 3 * ay
            if bs is None or sc < bs: best, bs = i, sc
        return best

    def bench_click(self, pos):          # mouse (PC demo only): click a source, then click a pin
        if self.wsrc is not None:
            self.wsrc = None
        if TEST_MODE and BTN_AUTO.collidepoint(pos):
            return self.auto_wire()
        if BTN_CLEAR.collidepoint(pos):
            self.rec_undo()
            self.w = {}
            self.wcur, self.msel = CUR_CLEAR, None
            return
        for src, pts in SRC_POS.items():
            if any(near(pos, p, 12) for p in pts):
                self.msel = None if self.msel == src else src
                self.cmsg = ""
                return
        for i, sink in enumerate(SINKS):
            if near(pos, SINK_POS[sink], 12):
                self.wcur = i
                if self.msel is None:
                    if sink in self.w:
                        self.rec_undo()
                        del self.w[sink]
                else:
                    self.rec_undo()
                    self.w[sink] = self.msel
                    self.msel, self.cmsg = None, ""
                return
        for kind, y in RAIL_LINES:                   # +5V / GND: click anywhere along the rail
            if 184 <= pos[0] <= 560 and abs(pos[1] - y) <= 8:
                self.msel = None if self.msel == kind else kind
                self.cmsg = ""
                return

    # ---------------- drawing helpers ----------------
    def txt(self, s, text, x, y, font=None, color=(255, 255, 255)):
        s.blit((font or self.f_m).render(text, True, color), (x, y))

    def ctxt(self, s, text, cx, y, font=None, color=(255, 255, 255)):
        img = (font or self.f_m).render(text, True, color)
        s.blit(img, (cx - img.get_width() // 2, y))

    def rtxt(self, s, text, rx, y, font=None, color=(255, 255, 255)):
        img = (font or self.f_m).render(text, True, color)
        s.blit(img, (rx - img.get_width(), y))

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

    def draw_box(self, s, rect):
        pygame.draw.rect(s, (20, 22, 30), rect, border_radius=10)
        pygame.draw.rect(s, (120, 130, 170), rect, 2, border_radius=10)

    # ---------------- drawing: world ----------------
    def draw_world(self, ui):
        if self.bg:
            ui.blit(self.bg, (0, 0))
        else:
            ui.fill((70, 78, 96))
            pygame.draw.rect(ui, (150, 140, 160), FLOOR)
            for poly in SOLIDS: pygame.draw.polygon(ui, (110, 80, 60), poly)
            for o in OBJS:
                pygame.draw.rect(ui, (90, 120, 160), o.rect, 2)
                ui.blit(self.f_tiny.render(o.name, True, (255, 255, 255)), (o.rect.x + 2, o.rect.y + 2))
            self.txt(ui, "Background image not found. Put bg.jpg in:  " + ASSET_DIRS[0], 12, UH - 24, self.f_s, (255, 200, 120))
        if self.skill_t > 0:                                         # skill: the hidden parts glow
            pulse = math.sin(time.time() * 7)
            for sp in ITEM_SPOTS:
                if sp.id in self.done_spots: continue
                r = int(16 + 3 * pulse)
                glow = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 220, 60, 90), (r + 2, r + 2), r)
                ui.blit(glow, (sp.ix - r - 2, sp.iy - r - 2))
                pygame.draw.circle(ui, (255, 230, 90), (sp.ix, sp.iy), r, 3)
        npc_on = self.npc["state"] != "off"
        if npc_on and self.npc["y"] <= self.py: self.draw_npc(ui)
        self.draw_player(ui)
        self.hide_legs(ui)
        if npc_on and self.npc["y"] > self.py: self.draw_npc(ui)
        f = None if (self.talk or self.cutscene) else self.find_near()
        if f:
            kind, o = f
            if kind in ("obj", "npc"):                       # hidden parts and hints show no prompt
                self.ctxt(ui, "[Space] " + o.name, int(self.px), int(self.py - SPR_H - 16), self.f_s, (255, 230, 120))
        if self.debug:
            pygame.draw.rect(ui, (0, 255, 255), FLOOR, 2)
            for poly in SOLIDS: pygame.draw.polygon(ui, (255, 0, 0), poly, 2)
            for sp in ITEM_SPOTS:
                col = (120, 120, 120) if sp.id in self.done_spots else (255, 50, 50)
                pygame.draw.circle(ui, col, (sp.ix, sp.iy), 12, 2)
                pygame.draw.line(ui, col, (sp.ix, sp.iy), (sp.ax, sp.ay), 1)
                pygame.draw.circle(ui, col, (sp.ax, sp.ay), 3)
                self.txt(ui, PART_SHORT[sp.part], sp.ix + 8, sp.iy - 18, self.f_tiny, (255, 150, 150))
            for h in HINT_SPOTS:
                col = (120, 120, 60) if h.id in self.read_hints else (255, 220, 60)
                pygame.draw.circle(ui, col, (h.ix, h.iy), 10, 2)
                pygame.draw.line(ui, col, (h.ix, h.iy), (h.ax, h.ay), 1)
                pygame.draw.circle(ui, col, (h.ax, h.ay), 3)
            for o in OBJS + [NPC_OBJ]:
                pygame.draw.rect(ui, (255, 255, 0), o.rect, 1)
                pygame.draw.circle(ui, (255, 255, 0), (o.ax, o.ay), 4)

    def hide_legs(self, ui):             # behind a partition: the room picture covers the body below the partition's top edge
        if not self.bg: return
        for x0, x1, ye, cut in ROW_LANES:
            if x0 - 12 <= self.px <= x1 + 12 and ye - LANE_H <= self.py <= ye + 1:
                r = pygame.Rect(int(self.px) - 24, cut, 48, int(self.py) + 8 - cut)
                r = r.clip(pygame.Rect(x0, 0, x1 - x0, UH))
                if r.w > 0 and r.h > 0: ui.blit(self.bg, r.topleft, r)
                return

    def draw_player(self, ui):
        form = self.look()
        img = self.spr.image(form) if self.spr else None
        if img:
            ui.blit(img, (int(self.px - img.get_width() / 2), int(self.py - img.get_height() + 4)))
        else:
            sx, sy = int(self.px - SPR_W / 2), int(self.py - SPR_H + 4)
            pygame.draw.rect(ui, FORM_COLORS[form], (sx, sy + SPR_H // 3, SPR_W, SPR_H - SPR_H // 3), border_radius=6)
            pygame.draw.circle(ui, (240, 200, 160), (sx + SPR_W // 2, sy + SPR_H // 6), max(6, SPR_W // 3))

    def draw_npc(self, ui):              # skin: assets/Boss*.png (BossSprite), else npc_stand.png / npc_sit.png, else a drawn figure
        n = self.npc
        x, y = int(n["x"]), int(n["y"])
        sit = n["state"] == "sit"
        img = self.boss.image(sit, n.get("dir", "front"), n["walk"], time.time()) if self.boss else None
        if img is None: img = self.npc_img_sit if sit else self.npc_img
        if img:
            ui.blit(img, (x - img.get_width() // 2, y - img.get_height() + 4))
            return
        bob = int(2 * math.sin(time.time() * 12)) if n["walk"] else 0
        if sit:
            pygame.draw.rect(ui, (40, 70, 150), (x - 11, y - 30, 22, 24), border_radius=4)
            pygame.draw.circle(ui, (240, 200, 160), (x, y - 38), 8)
            pygame.draw.rect(ui, (60, 40, 30), (x - 8, y - 46, 16, 6), border_radius=3)
        else:
            pygame.draw.rect(ui, (40, 40, 55), (x - 8, y - 18 + bob, 16, 18))
            pygame.draw.rect(ui, (40, 70, 150), (x - 11, y - 42 + bob, 22, 26), border_radius=4)
            pygame.draw.rect(ui, (200, 50, 50), (x - 2, y - 38 + bob, 4, 14))
            pygame.draw.circle(ui, (240, 200, 160), (x, y - 50 + bob), 8)
            pygame.draw.rect(ui, (60, 40, 30), (x - 8, y - 58 + bob, 16, 6), border_radius=3)

    def draw_talk(self, ui):             # dialogue box at the bottom of the game area
        t = self.talk
        last = t["i"] >= len(t["lines"]) - 1
        pygame.draw.rect(ui, (14, 18, 28), (40, 400, 880, 120), border_radius=10)
        pygame.draw.rect(ui, (255, 230, 120), (40, 400, 880, 120), 2, border_radius=10)
        self.txt(ui, NPC_NAME, 62, 410, self.f_m, (255, 230, 120))
        self.blit_wrap(ui, t["lines"][t["i"]], 62, 440, 836, self.f_m, (255, 255, 255), 24)
        hint = "Space: yes     Esc: not yet" if (last and t["ask"]) else "Space: next"
        self.rtxt(ui, hint, 904, 498, self.f_s, (170, 200, 255))

    # ---------------- drawing: close-up ----------------
    def cu_img(self, oid):
        if oid not in self.cu_cache: self.cu_cache[oid] = load_img("closeup_%s.png" % oid, (UW, UH))
        return self.cu_cache[oid]

    def draw_closeup(self, ui, s):
        o = self.cur
        if o.kind == "bench" and self.page == 1:
            return self.draw_board(ui)
        img = self.cu_img(o.id)
        if img: ui.blit(img, (0, 0))
        pygame.draw.rect(s, (70, 74, 90), (0, 0, 640, 44))
        self.txt(s, o.name.upper(), 16, 10, self.f_l)
        foot = getattr(self, "cu_" + o.kind)(s)
        if self.cmsg:
            for i, l in enumerate(self.wrap(self.cmsg, self.f_m, 610)[:2]):
                self.txt(s, l, 16, 440 + i * 24, self.f_m, (255, 225, 120))
        pygame.draw.rect(s, (40, 44, 60), (0, 494, 640, 46))
        self.txt(s, foot or "", 16, 499, self.f_s, (170, 200, 255))
        self.txt(s, "Back: hold Space (BTNC) or press Esc", 16, 520, self.f_tiny, (140, 150, 180))

    def draw_target(self, s, k, x, y):               # one line of the work order: the input and the character it must show
        pygame.draw.rect(s, (27, 41, 64), (x, y, 254, 66), border_radius=6)
        pygame.draw.rect(s, (45, 64, 94), (x, y, 254, 66), 2, border_radius=6)
        draw_set(s, GOLD[k], x + 12, y + 9, 28, 48, (38, 54, 76))
        self.txt(s, "CBA = %d%d%d" % bits(k), x + 52, y + 12, self.f_s, (143, 161, 184))
        self.txt(s, "must show  %s" % CHAR_NAME[k], x + 52, y + 34, self.f_m)
        self.txt(s, "tested by", x + 178, y + 14, self.f_tiny, (143, 161, 184))
        self.txt(s, "Boss", x + 178, y + 28, self.f_tiny, (143, 161, 184))

    def cu_whiteboard(self, s):
        pygame.draw.rect(s, (240, 240, 235), (40, 56, 560, 376), border_radius=6)
        ink = (30, 40, 130)
        if self.page == 0:
            lines = ["WORK ORDER #402", "Build the 7-segment decoder.",
                     "1. Hunt for all 18 lab parts in the office.", "   (notes and screens hold hints)",
                     "2. Bring them to the decoder bench.", "3. Wire it, then show it to the Boss.", "",
                     "input CBA -> character", "001 = C   010 = P   011 = E", "100 = -   101 = 3   110 = 9",
                     "(000 and 111 never occur)"]
            for i, l in enumerate(lines): self.txt(s, l, 62, 68 + i * 33, self.f_mono, ink)
            return "BTNC: next page"
        if self.page == 1:
            self.txt(s, "EQUIPMENT LIST", 62, 68, self.f_mono_l, ink)
            for i, (k, name, q) in enumerate(PARTS):
                done = self.found[k] >= q
                self.txt(s, "[%s] %-26s x%d   (%d found)" % ("x" if done else " ", name, q, self.found[k]),
                         62, 112 + i * 30, self.f_mono, (20, 120, 40) if done else ink)
            self.txt(s, "Total: %d / %d" % (self.parts_total(), TOTAL_PARTS), 62, 396, self.f_mono, ink)
            return "BTNC: next page"
        self.txt(s, "QA TEST %d of %d" % (min(self.rnd + 1, ROUNDS), ROUNDS), 70, 76, self.f_mono_l, ink)
        if self.rnd >= ROUNDS:
            self.txt(s, "All QA tests passed. Go to the exit door.", 70, 140, self.f_m, (20, 120, 40))
        elif self.codes is None:
            self.blit_wrap(s, "The QA inputs appear here once the decoder bench is powered on.", 70, 140, 500, self.f_m, ink)
        else:
            for i, k in enumerate(self.codes):
                self.txt(s, "input CBA = %d%d%d  ->  show %s" % (bits(k) + (CHAR_NAME[k],)), 70, 140 + i * 130, self.f_mono, ink)
                draw_set(s, GOLD[k], 470, 126 + i * 130, 54, 92, (215, 215, 210))
        if self.qa_pairs:                                # progress: which characters the Boss has already checked
            for i, pair in enumerate(self.qa_pairs):
                if i < self.rnd: txt, col = "Test %d: %s and %s - passed" % (i + 1, CHAR_NAME[pair[0]], CHAR_NAME[pair[1]]), (20, 120, 40)
                else: txt, col = "Test %d: not done yet" % (i + 1), (90, 90, 100)
                self.txt(s, txt, 70, 366 + i * 20, self.f_mono, col)
        return "BTNC: first page"

    def cu_door(self, s):
        pygame.draw.rect(s, (120, 85, 55), (240, 56, 160, 250), border_radius=6)
        done = self.rnd >= ROUNDS
        pygame.draw.circle(s, (34, 197, 94) if done else (220, 60, 60), (376, 185), 9)
        self.ctxt(s, "UNLOCKED" if done else "LOCKED", 320, 320, self.f_l, (34, 197, 94) if done else (255, 120, 120))
        self.ctxt(s, "Decoder QA: %d / %d" % (self.rnd, ROUNDS), 320, 362, self.f_m)
        if not done:
            self.ctxt(s, "The lock is wired to the decoder bench.", 320, 394, self.f_s, (200, 200, 210))
        return "BTNC: leave the lab" if done else "BTNC: try the handle"

    def cu_bench(self, s):                           # page 0: parts tray checklist
        pygame.draw.rect(s, (10, 20, 10), (40, 56, 560, 366), border_radius=6)
        g = (110, 255, 130)
        self.txt(s, "DECODER BENCH - PARTS TRAY", 56, 64, self.f_mono, g)
        for i, (k, name, q) in enumerate(PARTS):
            have = self.found[k]
            y = 92 + i * 32
            ok = have >= q
            pygame.draw.rect(s, (30, 70, 40) if ok else (40, 30, 30), (56, y, 528, 28), border_radius=5)
            self.txt(s, "[OK]" if ok else "[  ]", 64, y + 5, self.f_mono, g if ok else (255, 120, 120))
            self.txt(s, "%-27s %d / %d" % (name, have, q), 120, y + 5, self.f_mono, g if ok else (255, 170, 150))
        done = self.parts_total() >= TOTAL_PARTS
        if self.rnd >= ROUNDS: self.txt(s, "DECODER VERIFIED.", 56, 392, self.f_mono, (255, 255, 120))
        elif done: self.txt(s, "All parts on the bench. Ready to power on.", 56, 392, self.f_mono, (255, 255, 120))
        else: self.txt(s, "Parts %d / %d. Search the office, read the hints." % (self.parts_total(), TOTAL_PARTS), 56, 392, self.f_mono, g)
        return "BTNC: power on / open the breadboard"

    # ---------------- drawing: the breadboard ----------------
    def draw_resistor(self, ui, x, y, bands):        # horizontal resistor, centre at (x, y)
        pygame.draw.line(ui, (170, 170, 175), (x - 36, y), (x + 36, y), 3)
        pygame.draw.rect(ui, (214, 180, 120), (x - 20, y - 7, 40, 14), border_radius=6)
        for i, col in enumerate(bands):
            pygame.draw.rect(ui, col, (x - 13 + i * 9, y - 7, 4, 14))

    def draw_ic(self, ui, u):
        x0, yb = IC_X[u], IC_Y[u]
        body = pygame.Rect(x0, yb, 12 + 6 * PITCH + 12, BODY_H)
        for p in range(1, 15):
            x, y = pin_xy(u, p)
            y0 = yb + BODY_H if p <= 7 else yb - 10
            col = (215, 60, 60) if p == 14 else ((80, 110, 230) if p == 7 else (190, 190, 198))
            pygame.draw.rect(ui, col, (x - 4, y0, 8, 10))
        pygame.draw.rect(ui, (32, 33, 40), body, border_radius=4)
        pygame.draw.rect(ui, (70, 72, 86), body, 1, border_radius=4)
        pygame.draw.circle(ui, (14, 14, 18), (body.x, body.centery), 7)
        self.txt(ui, "%s  %s" % (u, IC_TYPE[u]), body.x + 14, body.y + 26, self.f_tiny, (200, 205, 220))
        for g, (kind, un, ins, outp) in GATES.items():
            if un != u: continue
            xs = [pin_xy(u, p)[0] for p in ins + [outp]]
            top = ins[0] > 7 or outp > 7
            self.ctxt(ui, g, sum(xs) // len(xs), body.y + (14 if top else 38), self.f_tiny, (255, 220, 120))
            for k, p in enumerate(ins + [outp]):
                letter = "Y" if p == outp else "AB"[k]
                x, _ = pin_xy(u, p)
                self.txt(ui, letter, x - 3, body.y + (2 if p > 7 else BODY_H - 14), self.f_tiny, (150, 155, 175))
        x14 = pin_xy(u, 14)[0]
        self.txt(ui, "+5", x14 - 7, body.y + 2, self.f_tiny, (255, 120, 120))
        self.txt(ui, "GND", pin_xy(u, 7)[0] - 9, body.bottom - 13, self.f_tiny, (140, 160, 255))

    def draw_board(self, ui):
        muted = (143, 161, 184)
        w = self.w
        c, b, a = bits(self.code3())
        done = self.rnd >= ROUNDS
        pygame.draw.rect(ui, (34, 40, 54), (0, 0, UW, 44))
        self.txt(ui, "DECODER BENCH", 120, 8, self.f_l)
        self.rtxt(ui, "Wires %d / %d   |   Parts %d/%d" % (len(w), len(REF), self.parts_total(), TOTAL_PARTS), UW - 16, 14, self.f_s, muted)
        # QA header
        for i, k in enumerate(self.codes):
            self.draw_target(ui, k, 16 + i * 262, 48)
        pygame.draw.rect(ui, (17, 26, 43), (548, 48, 84, 66), border_radius=6)
        self.ctxt(ui, "QA TEST", 590, 56, self.f_tiny, muted)
        self.ctxt(ui, "%d / %d" % (min(self.rnd + 1, ROUNDS), ROUNDS), 590, 76, self.f_m)
        for r, label, idx in ((BTN_CLEAR, "CLEAR ALL", CUR_CLEAR),):
            hot = self.wcur == idx and not done
            pygame.draw.rect(ui, (255, 230, 120) if hot else (27, 41, 64), r, border_radius=5)
            self.ctxt(ui, label, r.centerx, r.y + 9, self.f_s, (20, 20, 20) if hot else (255, 255, 255))
        if TEST_MODE:
            pygame.draw.rect(ui, (214, 120, 40), BTN_AUTO, border_radius=5)
            self.ctxt(ui, "AUTO-WIRE (test)", BTN_AUTO.centerx, BTN_AUTO.y + 9, self.f_s, (20, 20, 20))
        # breadboard + rails
        ui.blit(self.bb_surf, (16, 116))
        pygame.draw.rect(ui, (120, 110, 90), (16, 116, 928, 384), 3)
        for kind, y in RAIL_LINES:
            red = kind == "1"
            pygame.draw.line(ui, (210, 60, 60) if red else (60, 90, 220), (184, y), (560, y), 4)
            self.txt(ui, "+5V" if red else "GND", 187, y + 4, self.f_tiny, (190, 40, 40) if red else (50, 70, 190))
        for u in IC_X: self.draw_ic(ui, u)
        # bench supply
        pygame.draw.rect(ui, (70, 74, 84), (24, 124, 140, 74), border_radius=6)
        self.txt(ui, "BENCH DC SUPPLY", 32, 128, self.f_tiny, (225, 228, 235))
        pygame.draw.rect(ui, (10, 30, 14), (34, 144, 80, 26), border_radius=3)
        self.txt(ui, "5.00 V", 44, 148, self.f_m, (90, 255, 110))
        pygame.draw.circle(ui, (210, 50, 50), (130, 160), 6)
        pygame.draw.circle(ui, (30, 30, 36), (150, 160), 6)
        self.txt(ui, "click the +5V / GND rails", 32, 180, self.f_tiny, (205, 208, 220))
        # DIP switch (= board switches SW2..SW0) with pull-down resistors
        pygame.draw.rect(ui, (36, 84, 190), (28, 212, 120, 112), border_radius=4)
        self.txt(ui, "DIP SWITCH", 36, 214, self.f_tiny, (225, 235, 255))
        for i, (n, swi) in enumerate((("C", 2), ("B", 1), ("A", 0))):
            y = 238 + i * 32
            pygame.draw.rect(ui, (16, 40, 100), (54, y - 8, 66, 16), border_radius=3)
            on = self.sw[swi]
            pygame.draw.rect(ui, (245, 245, 250) if on else (150, 160, 190), (92 if on else 56, y - 6, 26, 12), border_radius=3)
            self.txt(ui, n, 36, y - 7, self.f_s, (255, 255, 255))
            self.txt(ui, "SW%d" % swi, 124, y - 5, self.f_tiny, (200, 215, 255))
            pygame.draw.line(ui, (150, 150, 158), (148, y), (160, y), 3)
        self.txt(ui, "+5V", 164, 207, self.f_tiny, (190, 40, 40))
        for i, n in enumerate("CBA"):                # three 10k pull-down resistors (top end is soldered to the switch output)
            x = 46 + i * 36
            pygame.draw.line(ui, (170, 170, 175), (x, 326), (x, 392), 3)
            pygame.draw.rect(ui, (214, 180, 120), (x - 7, 340, 14, 38), border_radius=6)
            for j, col in enumerate([(150, 90, 40), (20, 20, 20), (235, 120, 30)]):
                pygame.draw.rect(ui, col, (x - 7, 345 + j * 9, 14, 4))
            self.txt(ui, n, x - 3, 400, self.f_tiny, (60, 60, 55))
        self.txt(ui, "10k pull-downs: lower end to GND", 30, 418, self.f_tiny, (95, 95, 85))
        # 7-segment display with 220 ohm resistors
        for i, s in enumerate(SEGS):
            y = 150 + i * 48
            self.draw_resistor(ui, 668, y, [(200, 40, 40), (200, 40, 40), (150, 90, 40)])
            self.txt(ui, "220", 656, y - 21, self.f_tiny, (95, 95, 85))
        pygame.draw.rect(ui, (12, 12, 16), (770, 128, 160, 230), border_radius=8)
        draw_set(ui, self.on_of(self.code3()), 800, 150, 100, 180, (40, 22, 24))
        for i, s in enumerate(SEGS):
            self.txt(ui, s, 774, 136 + i * 32, self.f_tiny, (200, 200, 210))
        self.txt(ui, "COM", 902, 306, self.f_tiny, (60, 60, 55))
        self.ctxt(ui, "7-SEGMENT (common cathode)", 850, 336, self.f_tiny, (180, 180, 195))
        k = self.code3()
        pygame.draw.rect(ui, (17, 26, 43), (770, 366, 160, 56), border_radius=6)
        self.ctxt(ui, "INPUT CBA = %d%d%d" % (c, b, a), 850, 374, self.f_s)
        self.ctxt(ui, ("should show %s" % CHAR_NAME[k]) if k in CHAR_NAME else "(never occurs)", 850, 396, self.f_tiny, muted)
        # power status lights (like the LEDs of a real bench)
        pygame.draw.rect(ui, (17, 26, 43), (770, 430, 160, 62), border_radius=6)
        self.txt(ui, "POWER", 778, 434, self.f_tiny, muted)
        for i, u in enumerate(UNITS):
            pygame.draw.rect(ui, (34, 197, 94) if powered(w, u) else (160, 60, 60), (780 + i * 36, 448, 14, 14), border_radius=3)
            self.txt(ui, u, 780 + i * 36, 464, self.f_tiny, muted)
        pd_n = sum(w.get(k) == "0" for k in ("pd.C", "pd.B", "pd.A"))
        self.txt(ui, "DIP %s  PD %d/3  COM %s" % ("ok" if w.get("dip.vcc") == "1" else "--", pd_n, "ok" if w.get("seg.com") == "0" else "--"),
                 778, 478, self.f_tiny, muted)
        # wires
        cache = {}
        ce, be, ae = levels(w, c, b, a)
        for sink, src in w.items():
            if src not in cache: cache[src] = val(w, src, ce, be, ae)
            pts = SRC_POS[src]
            p0 = min(pts, key=lambda p: (p[0] - SINK_POS[sink][0]) ** 2 + (p[1] - SINK_POS[sink][1]) ** 2)
            col = src_color(src)
            if not cache[src]: col = tuple(int(v * 0.5) for v in col)
            if self.wsrc is not None and SINKS[self.wcur] == sink: col = (255, 255, 120)
            pygame.draw.lines(ui, col, False, wire_pts(p0, SINK_POS[sink]), 3)
            pygame.draw.circle(ui, col, (int(p0[0]), int(p0[1])), 5)
            pygame.draw.circle(ui, col, (int(SINK_POS[sink][0]), int(SINK_POS[sink][1])), 5)
        # nodes
        for src, pts in SRC_POS.items():
            for p in pts:
                pygame.draw.circle(ui, src_color(src), p, 7)
                pygame.draw.circle(ui, (20, 20, 26), p, 7, 2)
        for sink in SINKS:
            p = SINK_POS[sink]
            ring = (215, 60, 60) if sink.endswith(".vcc") else ((80, 110, 230) if (sink.endswith(".gnd") or sink in ("pd.C", "pd.B", "pd.A", "seg.com")) else (20, 20, 26))
            pygame.draw.circle(ui, (255, 165, 60) if sink in w else (245, 245, 250), p, 7)
            pygame.draw.circle(ui, ring, p, 7, 3 if ring != (20, 20, 26) else 2)
        for lbl, p in (("C", (160, 238)), ("B", (160, 270)), ("A", (160, 302))):
            self.txt(ui, lbl, p[0] + 10, p[1] - 8, self.f_s, (40, 40, 40))
        if not done:
            if self.wcur < len(SINKS):                   # cursor: dark-orange ring with a black outline so it shows on every pin
                cp = SINK_POS[SINKS[self.wcur]]
                pygame.draw.circle(ui, (0, 0, 0), cp, 15, 7)
                pygame.draw.circle(ui, (220, 80, 0), cp, 15, 4)
            if self.wsrc is not None and w.get(SINKS[self.wcur]):
                for p in SRC_POS[w[SINKS[self.wcur]]]: pygame.draw.circle(ui, (255, 230, 120), p, 11, 3)
            if self.msel:
                for p in SRC_POS[self.msel]: pygame.draw.circle(ui, (56, 189, 248), p, 12, 3)
        # footer
        pygame.draw.rect(ui, (34, 40, 54), (0, 502, UW, 38))
        if self.cmsg: line, lc = self.cmsg, (255, 225, 120)
        elif done: line, lc = "Decoder verified. Leave through the exit door.", (150, 255, 170)
        elif self.wsrc is not None: line, lc = "%s  <-  %s" % (sink_name(SINKS[self.wcur]), src_name(w.get(SINKS[self.wcur]))), (255, 230, 120)
        elif self.msel: line, lc = "Selected: %s  ->  now click a white pin" % src_name(self.msel), (130, 215, 255)
        elif self.wcur < len(SINKS): line, lc = "%s  =  %s" % (sink_name(SINKS[self.wcur]), src_name(w.get(SINKS[self.wcur]))), muted
        else: line, lc = "Press BTNC to remove every wire", muted
        self.txt(ui, line, 14, 505, self.f_s, lc)
        self.txt(ui, "Mouse: colored output -> white pin (click a wired pin = remove) | Keys: L/R pin, BTNC wire, hold BTNC back | SW2-0 = test | Done? Esc, then ask the Boss",
                 14, 524, self.f_tiny, (140, 150, 180))

    # ---------------- drawing: overlays ----------------
    def draw_cards(self, ui, s):
        d = self.deck
        ov = pygame.Surface((UW, UH), pygame.SRCALPHA); ov.fill((0, 0, 0, 205)); ui.blit(ov, (0, 0))
        self.ctxt(s, "PICK A CARD  (ROUND %d)" % d["round"], 320, 30, self.f_l)

        for pos in range(3):
            r = pygame.Rect(65 + pos * 180, 95, 170, 170)
            idx = d["perm"][pos]
            item = CARD_ITEMS[d["round"]][idx]
            item_name = ITEM_TEXT[item][0]
            revealed = (d["face"] == pos)

            # --- บังคับใช้สีตาม self.career ที่ผู้เล่นเลือกไว้จาก Stage 1 เสมอ ---
            if self.career is not None:
                fb_col = CAREERS[self.career][1]
            else:
                fb_col = (80, 85, 100)

            drew_img = False
            if self.card_art:                                   # card pictures from demo_py/card_assets.py + assets/
                drew_img = self.card_art.draw_card(s, r, d["round"], self.career, pos, revealed, slot_idx=idx, fallback_color=fb_col)
            else:
                pygame.draw.rect(s, fb_col, r, border_radius=10)

            if not drew_img:                                    # no picture found: plain card with text
                if d["round"] == 1:
                    if revealed:
                        self.ctxt(s, CAREERS[idx][0], r.centerx, r.y + 60, self.f_m)
                        self.ctxt(s, item_name, r.centerx, r.y + 120, self.f_s)
                    else:
                        self.ctxt(s, "?", r.centerx, r.y + 90, self.f_l, (200, 200, 200))
                else:
                    if self.career is not None:
                        self.ctxt(s, SYMBOLS[self.career][pos], r.centerx, r.y + 60, self.f_m)
                    if revealed:
                        self.ctxt(s, item_name, r.centerx, r.y + 120, self.f_s)
            elif revealed and d["round"] > 1:                   # picture + round 2/3: item name on a dark strip
                tag = pygame.Surface((r.w, 34), pygame.SRCALPHA)
                tag.fill((0, 0, 0, 180))
                s.blit(tag, (r.x, r.bottom - 42))
                self.ctxt(s, item_name, r.centerx, r.bottom - 34, self.f_s, (255, 230, 120))

            if d["face"] is None and pos == d["cursor"]:
                pygame.draw.rect(s, (255, 255, 255), r.inflate(10, 10), 4, border_radius=12)
            elif revealed and not CARD_BACKS:
                pygame.draw.rect(s, (255, 230, 120), r.inflate(10, 10), 4, border_radius=12)

        if d["face"] is not None:
            name, desc = ITEM_TEXT[CARD_ITEMS[d["round"]][d["perm"][d["face"]]]]
            pygame.draw.rect(s, (30, 35, 45), (60, 310, 520, 90), border_radius=8)
            self.ctxt(s, "Obtained: " + name, 320, 322, self.f_m, (255, 230, 120))
            self.ctxt(s, desc, 320, 356, self.f_s, (240, 240, 240))
            self.ctxt(s, "BTNC: continue", 320, 420, self.f_m, (170, 200, 255))
        else:
            self.ctxt(s, "L/R choose   BTNC pick", 320, 360, self.f_m, (170, 200, 255))

    def draw_inventory(self, s):
        self.draw_box(s, pygame.Rect(90, 80, 460, 340))
        self.ctxt(s, "INVENTORY  (SW15 / key I to close)", 320, 94, self.f_m)
        counts = [self.hh, self.hs, self.undo, self.freeze]
        names = ["Hint (wiring)", "Hint (smart)", "Undo", "Freeze"]
        for i in range(4):
            r = pygame.Rect(110 + i * 108, 130, 100, 90)
            pygame.draw.rect(s, (255, 230, 120) if i == self.inv_cur else (70, 74, 100), r, border_radius=8)
            col = (20, 20, 20) if i == self.inv_cur else (255, 255, 255)
            self.ctxt(s, names[i], r.centerx, r.y + 14, self.f_s, col)
            self.ctxt(s, "x%d" % counts[i], r.centerx, r.y + 46, self.f_l, col)
        self.txt(s, "Parts %d / %d  (see the notebook for details)" % (self.parts_total(), TOTAL_PARTS), 110, 240, self.f_s, (150, 255, 170))
        self.txt(s, "Armor x%d   (shields a failed QA penalty)" % self.armor, 110, 268, self.f_s)
        self.txt(s, "Armor shards %d / 2   (2 shards = 1 armor)" % self.shard, 110, 294, self.f_s)
        self.txt(s, "Speed Boost: %s   (used in Stage 3)" % ("yes" if self.boost else "no"), 110, 320, self.f_s)
        self.txt(s, "Slow: %s" % (("%.0f s left" % self.slow_t) if self.slow_t > 0 else "off"), 110, 346, self.f_s)
        self.ctxt(s, "L/R select   BTNC use", 320, 386, self.f_s, (170, 200, 255))

    def draw_notebook(self, s):
        self.draw_box(s, pygame.Rect(60, 50, 520, 420))
        self.ctxt(s, "NOTEBOOK  (SW14 / key N to close)", 320, 62, self.f_m)
        self.txt(s, "Parts %d / %d      QA tests passed: %d / %d" % (self.parts_total(), TOTAL_PARTS, self.rnd, ROUNDS),
                 80, 92, self.f_s, (255, 230, 120))
        for i, (k, _, q) in enumerate(PARTS):
            ok = self.found[k] >= q
            self.txt(s, "%s %d/%d" % (PART_SHORT[k], self.found[k], q), 80 + (i % 3) * 170, 116 + (i // 3) * 18,
                     self.f_tiny, (150, 255, 170) if ok else (230, 230, 230))
        if self.career is not None:
            self.txt(s, "Career card: %s" % CAREERS[self.career][0], 80, 176, self.f_s, CAREERS[self.career][1])
        y = 198
        self.txt(s, "Logged Actions & Clues:", 80, y, self.f_s, (170, 200, 255)); y += 20
        for n in self.notes[-8:]: y = self.blit_wrap(s, "- " + n, 80, y, 480, self.f_s, (230, 230, 230), 18)
        y += 6
        self.txt(s, "Hints Used:", 80, y, self.f_s, (170, 200, 255)); y += 20
        for h in self.hints_seen[-2:]:
            y = self.blit_wrap(s, "- " + h, 80, y, 480, self.f_tiny, (230, 230, 230), 15)

    def draw_help(self, ui, s):
        ov = pygame.Surface((UW, UH), pygame.SRCALPHA); ov.fill((0, 0, 0, 215)); ui.blit(ov, (0, 0))
        self.draw_box(s, pygame.Rect(30, 50, 580, 440))
        self.ctxt(s, "STAGE 2: INTERNSHIP - HOW TO PLAY", 320, 64, self.f_l)
        rows = [("Move", "W A S D / arrows   (BTNU BTND BTNL BTNR)"),
                ("Interact / confirm", "Space   (BTNC tap)"),
                ("Search / read a hint", "Space next to a suspicious spot"),
                ("Back / cancel", "hold Space 0.8 s, or Esc   (BTNC hold)"),
                ("Test input C B A", "keys 3 2 1 = SW2 SW1 SW0, or click them below"),
                ("Inventory / Notebook", "I (SW15)   /   N (SW14)"),
                ("Workshop-shirt skill", "E or SW13 or the SKILL button (after 2 min)"),
                ("This help", "H"),
                ("Test shortcuts", "F5 next part, F7 parts, F8 auto-wire, F9 skill ready")]
        for i, (a, b) in enumerate(rows):
            self.txt(s, a, 54, 114 + i * 29, self.f_s, (255, 230, 120))
            self.txt(s, b, 220, 114 + i * 29, self.f_s)
        self.blit_wrap(s, "Find all 18 lab parts hidden around the office (read the hints on notes and screens), install them on the "
                          "decoder bench, wire the 7-segment decoder on the breadboard, show it to the Boss for 3 QA tests, then leave by "
                          "the exit door. A failed QA test costs 1 heart.", 54, 370, 532, self.f_s, (170, 200, 255), 22)
        self.ctxt(s, "Press Space to start", 320, 456, self.f_m, (150, 255, 170))

    def draw_hud(self, ui):
        for i in range(3):
            col = (230, 50, 60) if i < self.hearts else (80, 50, 50)
            pygame.draw.circle(ui, col, (24 + i * 26, 22), 10)
        if self.armor > 0:
            pygame.draw.rect(ui, (80, 180, 255), (96, 12, 18, 22), border_radius=4)
            self.txt(ui, "x%d" % self.armor, 118, 14, self.f_s, (120, 200, 255))
        if self.slow_t > 0:
            self.txt(ui, "SLOW %.0fs" % self.slow_t, 16, 40, self.f_s, (255, 150, 80))
        if self.mode == "map" or not (self.cur and self.cur.kind == "bench" and self.page == 1):
            self.rtxt(ui, "Parts %d/%d" % (self.parts_total(), TOTAL_PARTS), UW - 14, 10, self.f_s, (150, 255, 170))
            self.rtxt(ui, "QA %d/%d" % (self.rnd, ROUNDS), UW - 14, 28, self.f_s, (255, 230, 120))

    def draw_skill_btn(self, ui):
        if not self.intro_started or self.mode != "map": return
        if self.skill_t > 0: bg, fg, txt = (40, 120, 60), (255, 255, 255), "SKILL ON  %ds" % math.ceil(self.skill_t)
        elif self.skill_used: bg, fg, txt = (50, 50, 56), (130, 130, 140), "SKILL USED"
        elif self.skill_ready():
            lit = int(time.time() * 3) % 2
            bg, fg, txt = ((230, 180, 40) if lit else (190, 140, 30)), (20, 20, 20), "SKILL [E] READY"
        else:
            left = max(0, math.ceil(SKILL_WAIT - self.play_t))
            bg, fg, txt = (50, 50, 56), (200, 200, 210), "SKILL  %d:%02d" % (left // 60, left % 60)
        pygame.draw.rect(ui, bg, SKILL_BTN, border_radius=8)
        pygame.draw.rect(ui, (255, 255, 255), SKILL_BTN, 1, border_radius=8)
        self.ctxt(ui, txt, SKILL_BTN.centerx, SKILL_BTN.y + 7, self.f_s, fg)

    def draw_toast(self, ui):
        if time.time() < self.toast[1]:
            img = self.f_m.render(self.toast[0], True, (255, 255, 255))
            r = pygame.Rect(UW // 2 - img.get_width() // 2 - 12, 44, img.get_width() + 24, 34)
            pygame.draw.rect(ui, (0, 0, 0), r, border_radius=8)
            ui.blit(img, (r.x + 12, r.y + 7))

    def seg_right(self):
        if self.state == "clear": return "PA55"
        if self.state == "over": return "dEAd"
        if self.wiring_live() and not self.deck["active"]:
            return "%d%d%d " % bits(self.code3())            # last digit is replaced by the live decoder output
        return ""

    def draw_panel(self, scr):
        y0 = SCR_H
        pygame.draw.rect(scr, (24, 26, 32), (0, y0, SCR_W, PANEL_H))
        pygame.draw.line(scr, (70, 74, 90), (0, y0), (SCR_W, y0), 2)
        leds = [False] * 16
        for i in range(3): leds[i] = self.hearts > i
        leds[3] = self.armor > 0
        for i, (k, _, q) in enumerate(PARTS): leds[4 + i] = self.found[k] >= q
        for i in range(ROUNDS): leds[13 + i] = self.rnd > i
        for i in range(16):
            pygame.draw.circle(scr, (255, 70, 60) if leds[i] else (70, 40, 40), (sw_cx(i), y0 + 18), 7)
        for i in range(16):
            r = self.sw_rects[i]
            pygame.draw.rect(scr, (230, 230, 230) if self.sw[i] else (80, 80, 90), r, border_radius=5)
            self.ctxt(scr, "SW%d" % i, r.centerx, r.y + 11, self.f_tiny, (20, 20, 20) if self.sw[i] else (200, 200, 200))
        text = ("H%d" % max(0, self.hearts)) + self.seg_right().rjust(6)[-6:]
        glyphs = [SEG_MAP.get(ch, "g") for ch in text]
        if self.state == "play" and self.wiring_live() and not self.deck["active"]:
            glyphs[7] = self.on_of(self.code3())
        for i, on in enumerate(glyphs):
            draw_set(scr, on, 14 + i * 40, y0 + 26, 32, 52)
        self.txt(scr, "7-SEG: H3 = hearts | at the bench: C B A + decoder output", 14, y0 + 84, self.f_tiny, (170, 170, 190))
        self.txt(scr, "LED: 0-2 hearts  3 armor  4-12 part types done  13-15 QA tests", 360, y0 + 78, self.f_tiny, (140, 140, 160))
        self.txt(scr, "Move WASD | BTNC = Space (hold = back) | SW0-7 = keys 1-8 or click | I inventory | N notebook | H help | E skill",
                 360, y0 + 94, self.f_tiny, (170, 170, 190))
        self.txt(scr, "Form: %s" % FORM_NAMES[self.look()], 14, y0 + 98, self.f_tiny, (140, 140, 160))

    def part_icon(self, key):            # optional picture assets/part_<key>.png (e.g. part_not.png); otherwise a drawn icon
        if key not in self.cu_cache or ("icon", key) not in self.cu_cache:
            img = load_img("part_%s.png" % key)
            if img: img = pygame.transform.smoothscale(img, (max(1, round(img.get_width() * 96 / img.get_height())), 96))
            self.cu_cache[("icon", key)] = img
        return self.cu_cache[("icon", key)]

    def draw_part_icon(self, ui, key, cx, cy):          # drawn pictures of the 9 kinds of parts, centred at (cx, cy)
        img = self.part_icon(key)
        if img:
            ui.blit(img, (cx - img.get_width() // 2, cy - img.get_height() // 2)); return
        if key in ("not", "and", "or"):                 # DIP-14 chip
            pygame.draw.rect(ui, (32, 33, 40), (cx - 50, cy - 22, 100, 44), border_radius=4)
            for i in range(7):
                for yy in (cy - 31, cy + 22):
                    pygame.draw.rect(ui, (190, 190, 198), (cx - 44 + i * 14, yy, 6, 9))
            pygame.draw.circle(ui, (14, 14, 18), (cx - 50, cy), 6)
            self.ctxt(ui, PART_SHORT[key], cx + 2, cy - 7, self.f_s, (220, 225, 235))
        elif key == "seg":
            pygame.draw.rect(ui, (12, 12, 16), (cx - 34, cy - 46, 68, 92), border_radius=6)
            draw_set(ui, "abcdefg", cx - 20, cy - 34, 40, 68, (60, 26, 28))
        elif key == "dip":
            pygame.draw.rect(ui, (36, 84, 190), (cx - 40, cy - 34, 80, 68), border_radius=4)
            for i in range(3):
                pygame.draw.rect(ui, (16, 40, 100), (cx - 28, cy - 22 + i * 18, 56, 12), border_radius=3)
                pygame.draw.rect(ui, (245, 245, 250), (cx - 28 + (28 if i == 1 else 0), cy - 22 + i * 18, 26, 12), border_radius=3)
        elif key in ("r10k", "r220"):
            bands = [(150, 90, 40), (20, 20, 20), (235, 120, 30)] if key == "r10k" else [(200, 40, 40), (200, 40, 40), (150, 90, 40)]
            pygame.draw.line(ui, (170, 170, 175), (cx - 58, cy), (cx + 58, cy), 4)
            pygame.draw.rect(ui, (214, 180, 120), (cx - 34, cy - 14, 68, 28), border_radius=12)
            for i, col in enumerate(bands): pygame.draw.rect(ui, col, (cx - 22 + i * 16, cy - 14, 7, 28))
        elif key == "bb":
            pygame.draw.rect(ui, (226, 222, 208), (cx - 56, cy - 36, 112, 72), border_radius=4)
            for x in range(cx - 50, cx + 52, 9):
                for y in range(cy - 30, cy + 32, 9): ui.fill((170, 166, 152), (x, y, 3, 3))
            for col, (a, b) in (((220, 60, 60), (-30, 20)), ((60, 90, 220), (0, 40)), ((70, 190, 90), (28, -10))):
                pygame.draw.lines(ui, col, False, [(cx + a, cy - 8), (cx + a, cy - 30), (cx + b, cy - 30), (cx + b, cy + 4)], 3)
        else:                                           # psu
            pygame.draw.rect(ui, (70, 74, 84), (cx - 56, cy - 34, 112, 68), border_radius=6)
            pygame.draw.rect(ui, (10, 30, 14), (cx - 44, cy - 24, 64, 24), border_radius=3)
            self.txt(ui, "5.00V", cx - 40, cy - 20, self.f_s, (90, 255, 110))
            pygame.draw.circle(ui, (210, 50, 50), (cx + 34, cy - 12), 7)
            pygame.draw.circle(ui, (30, 30, 36), (cx + 34, cy + 14), 7)

    def draw_found_card(self, ui):       # "FOUND!" card with a picture of the part, shown during the zoom
        z = self.zoom
        if not z: return
        k = z["t"] / ZOOM_SECS
        if k < 0.18: return
        f = 1.0 + (ZOOM_MAX - 1.0) * min(1.0, max(0.0, k / 0.25 if k < 0.5 else (1.0 - k) / 0.25))
        sy = (z["y"] - min(max(z["y"] - UH / f / 2, 0), UH - UH / f)) * f         # where the part is on screen now
        w, h = 300, 190
        r = pygame.Rect(UW // 2 - w // 2, 330 if sy < UH * 0.5 else 70, w, h)
        a = int(255 * min(1.0, (k - 0.18) / 0.1, (1.0 - k) / 0.1))
        card = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(card, (14, 18, 28, 235), (0, 0, w, h), border_radius=12)
        pygame.draw.rect(card, (255, 230, 120), (0, 0, w, h), 3, border_radius=12)
        self.ctxt(card, "FOUND!", w // 2, 10, self.f_l, (255, 230, 120))
        pygame.draw.rect(card, (30, 36, 52), (w // 2 - 80, 46, 160, 90), border_radius=8)
        self.draw_part_icon(card, z["part"], w // 2, 91)
        self.ctxt(card, PART_LABEL[z["part"]], w // 2, 142, self.f_m)
        self.ctxt(card, "%d / %d   |   Parts %d / %d" % (self.found[z["part"]], PART_QTY[z["part"]], self.parts_total(), TOTAL_PARTS),
                  w // 2, 166, self.f_s, (150, 255, 170))
        card.set_alpha(a)
        ui.blit(card, r.topleft)

    def apply_zoom(self, ui):            # camera pushes in on the part you just found, then pulls back out
        z = self.zoom
        if not z: return
        k = z["t"] / ZOOM_SECS
        e = min(1.0, k / 0.25) if k < 0.5 else min(1.0, (1.0 - k) / 0.25)      # ease in 25%, hold, ease out 25%
        e = e * e * (3 - 2 * e)
        f = 1.0 + (ZOOM_MAX - 1.0) * e
        w, h = UW / f, UH / f
        x = min(max(z["x"] - w / 2, 0), UW - w)
        y = min(max(z["y"] - h / 2, 0), UH - h)
        crop = ui.subsurface(pygame.Rect(int(x), int(y), int(w), int(h))).copy()
        ui.blit(pygame.transform.smoothscale(crop, (UW, UH)), (0, 0))

    def draw(self, ui, screen):
        ui.fill((18, 20, 26))
        s = ui.subsurface(pygame.Rect(CU_X, 0, CU_W, UH))
        if self.mode == "closeup" and self.cur: self.draw_closeup(ui, s)
        else:
            self.draw_world(ui)
            self.apply_zoom(ui)
            self.draw_found_card(ui)
        self.draw_hud(ui)
        self.draw_skill_btn(ui)
        if self.sw[14]: self.draw_notebook(s)
        if self.sw[15]: self.draw_inventory(s)
        if self.hint_popup:
            self.draw_box(s, pygame.Rect(60, 150, 520, 220))
            self.ctxt(s, self.hint_title.upper(), 320, 162, self.f_m, (255, 230, 120))
            self.blit_wrap(s, self.hint_popup, 84, 198, 472, self.f_m, (255, 255, 255), 24)
            self.ctxt(s, "BTNC: close", 320, 340, self.f_s, (170, 200, 255))
        if self.deck["active"]: self.draw_cards(ui, s)
        if self.talk: self.draw_talk(ui)
        if self.flash > 0:
            fl = pygame.Surface((UW, UH)); fl.fill((255, 0, 0)); fl.set_alpha(int(180 * self.flash / 0.4)); ui.blit(fl, (0, 0))
        if self.state == "over":
            ov = pygame.Surface((UW, UH)); ov.set_alpha(220); ui.blit(ov, (0, 0))
            self.ctxt(ui, "OUT OF HEARTS", UW // 2, 220, self.f_l, (255, 90, 90))
            self.ctxt(ui, "Restarting Stage 2...", UW // 2, 270, self.f_m)
        if self.state == "clear":
            ui.fill((15, 40, 25))
            self.ctxt(ui, "STAGE 2 CLEAR - INTERNSHIP COMPLETE!", UW // 2, 160, self.f_l, (150, 255, 170))
            self.ctxt(ui, "Hearts left: %d" % self.hearts, UW // 2, 220, self.f_m)
            self.ctxt(ui, "CHARACTER EVOLVED -> %s" % FORM_NAMES[2], UW // 2, 270, self.f_m, (255, 230, 120))
            self.ctxt(ui, "BTNC: play again" if self.standalone else "BTNC: continue to the next stage",
                      UW // 2, 370, self.f_s, (170, 200, 255))
        self.draw_toast(ui)
        if self.show_help: self.draw_help(ui, s)
        screen.blit(pygame.transform.smoothscale(ui, (SCR_W, SCR_H)), (0, 0))
        self.draw_panel(screen)


def main():
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_caption("CPE Escape - Stage 2 Internship (PC demo)")
    size = (SCR_W, SCR_H + PANEL_H)
    try:
        screen = pygame.display.set_mode(size, pygame.SCALED | pygame.RESIZABLE)
    except pygame.error:
        screen = pygame.display.set_mode(size)
    ui = pygame.Surface((UW, UH))
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