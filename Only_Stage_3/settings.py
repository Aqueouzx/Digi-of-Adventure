"""Edit filenames here. All art paths below are relative to assets/."""
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
TIME_LIMIT = 120
COYOTE_TIME = 0.15        # seconds after walking off an edge
JUMP_BUFFER = 0.15        # remember an early press until landing
TICK = 1 / 120
SPAWNS = {1: (6, 3), 2: (5, 3), 3: (6, 3)}
ROUTES = {1: ("S6", "S4"), 2: ("S4", "CB2"), 3: ("N17", "N16")}
LEVEL_CLEAR_TIME = 2.0
RUN_SPEED = 5
ENEMY_SPEED = 2
PLAYER_WIDTH, PLAYER_HEIGHT = 0.63, 1.5
JUMP_HEIGHT, JUMP_TIME = 2.5, 0.7
DOUBLE_HEIGHT, DOUBLE_TIME, DOUBLE_RANGE = 4.5, 1.2, 5.5
PUZZLE = (240, 5)
SKILL_TIME = INTERVIEW_TIME = 5
MAPS = {1: "map_1.tmj", 2: "map_2.tmj", 3: "map_3.tmj"}
BACKGROUND = {1: "sunset_2.png", 2: "mountains_1.png", 3: "night_3.png"}
# Ground-level threshold at the classroom building entrance.
DOOR_X, DOOR_Y, DOOR_WIDTH, DOOR_HEIGHT = 247.2, 2, 1.5, 2.3
REPORTER_WIDTH, REPORTER_HEIGHT = PLAYER_WIDTH, PLAYER_HEIGHT
REPORTER_GAP = 1.15  # minimum centre-to-centre distance in metres
REPORTER_DELAY = .28
CLOAK_FOLLOW_TIME = .60
RETREAT_TIME = 2.0
RETREAT_SPEED = 3.0
TEA_HEIGHT = 1.7
GOLD_SCALE = 1.08
ANIMAL_HEIGHT = PLAYER_HEIGHT / 1.75
TILESET_KIND = {"S4": "decor", "N17": "decor", "S6": "decor",
                "water_1": "water", "water1_1": "water", "water1_2": "water", "water_2_2": "water",
                "waterkonmai_2": "solid"}
# Three poses per player: stand, left step, right step. Source faces right.
PLAYER = {
    "gown": ["player_form2_right_stand.png", "player_form2_right_stepl.png", "player_form2_right_stepr.png"],
    "cloak": ["player_form2_right2_stand.png", "player_form2_right2_stepl.png", "player_form2_right2_stepr.png"],
    "gold": ["player_form3_right_stand.png", "player_form3_right_stepl.png", "player_form3_right_stepr.png"],
}
REPORTER = ["reporter_stand.png", "reporter_step.png"]
# One of the listed appearances is selected at spawn.
ANIMALS = {
    "snail": ["snail_2.png", "snail_22.png", "snail1_2.png", "snail1_22.png", "snail.png", "snail1.png"],
    "squirrel": ["squirrel_2.png", "squirrel.png"], "ant": ["ant_2.png"], "goose": ["goose_2.png", "goose.png"],
}
STAGE_ONE_ANIMALS = {
    "snail": ["snail_1.png", "snail1_1.png", "snail.png", "snail1.png"],
    "squirrel": ["squirrel_1.png", "squirrel.png"], "ant": ["ant_1.png"],
}
TEA, BLOCK, CLOCK = "milk_tea_2.png", "puzzle_2.png", None  # custom clock PNG, or None for the blue pixel clock
SKILL_ICONS = {"cloak": ("skill_cloak.png", "skill_cloak_used.png"),
               "phase": ("skill_phase.png", "skill_phase_used.png")}
# Override individual block pictures without changing the map or its collision.
# Keys are (tileset name in Tiled, local tile ID starting from 0).
# Example: TILE_IMAGES = {("floor1_2", 0): "grass_new.png", ("water1_2", 0): "water_new.png"}
TILE_IMAGES = {}
# Optional atlas replacement. Keep the original grid, margin and spacing.
# Example: ATLAS_IMAGES = {"floor1_2": "grass_new.png"}
ATLAS_IMAGES = {}

# -1 for source images facing left, +1 for source images facing right.
ANIMAL_FACING = {"snail": -1, "squirrel": -1, "ant": -1, "goose": -1}
# Each pair is one line-wrapped interview prompt.
QUESTIONS = (
    ("วิ่งไวขนาดนี้", "ตอนไปเรียน 9 โมงเช้าเคยไวเท่านี้ไหมคะ!"),
    ("ติด F ไว้กี่วิชาคะ", "ถึงต้องสปีดหนีตายขนาดนี้!"),
    ("วิ่งหนีนักข่าว", "หรือวิ่งหนีเดดไลน์โปรเจกต์คะเนี่ย!"),
    ("อาจารย์วียืนถือใบปริญญารอตากแดด", "จนตะคริวจะกินแล้วค่ะ!"),
    ("ถ้าหยุดคุยตรงนี้ 5 วินาที", "ใบปริญญาในมืออาจารย์วีอาจจะบินได้นะคะ!"),
    ("คิดว่าสปีดพ้นนักข่าว", "แล้วจะผ่านสายตาอันแหลมคมของอาจารย์วีเหรอคะ!"),
    ("อาจารย์วีฝากถามมาค่ะว่า...", "สรุปโปรเจกต์ผ่านจริงใช่ไหมคะ!"),
    ("อุตส่าห์เรียนถึกทนมาตั้ง 4 ปี", "จะมาสายวันรับปริญญาไม่ได้นะคะ!"),
    ("หยุดตอบคำถามก่อนค่ะ!", "จบไปแล้วจะเอาแรงที่ไหนไปตื่นทำงาน!"),
    ("กล้องช่องเราจับภาพอยู่ค่ะ!", "ยิ้มหวานๆ ให้อาจารย์วีหน่อยค่ะ!"),
    ("เรียนจบแล้ว จะไปขายก๋วยเตี๋ยว", "หรือทำงานตรงสายคะ ตอบ!"),
    ("สปีดแรงขนาดนี้", "ตอนกดลงทะเบียนเรียนเคยไวเท่านี้ไหมคะ!"),
    ("ทรงนี้แก้โค้ดหน้าห้อง", "ใช่ไหมคะสารภาพมาซะดีๆ!"),
    ("อาจารย์วีนับ 1 ถึง 3 แล้วค่ะ!","ถ้ายังมาไม่ถึงถือว่าเรียนใหม่อีกปีนะคะ!"),
    ("ลืมบัตรคิวรับใบปริญญาหรือเปล่าคะ", "เห็นวิ่งลนลานขนาดนี้!"),


)


ANT_HIDDEN, ANT_RISE, ANT_ABOVE, ANT_FALL = 2., 1., 2., 1.

TILESET_KIND["N16"] = "decor"
PLAYER["phase"] = [f"player_form3_right2_{pose}.png" for pose in ("stand", "stepl", "stepr")]
STAGE_THREE_ANIMALS = {
    "snail": ["snail_3.png", "snail1_3.png", "snail.png", "snail1.png"],
    "squirrel": ["squirrel_3.png", "squirrel.png"], "ant": ["ant_3.png"], "goose": ["goose_3.png", "goose.png"],
}
# Platform top heights are in metres above the map origin.
LIFT_LOW, LIFT_HIGH, LIFT_SPEED = 3., 5., 0.8
SINK_SPEED = 0.6
