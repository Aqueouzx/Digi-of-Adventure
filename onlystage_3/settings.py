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
    ("Running this fast", "were you ever this quick for a 9 AM lecture?!"),
    ("How many F's are you hiding", "to be sprinting for your life like this?!"),
    ("Are you running from reporters", "or running from a project deadline?!"),
    ("Ajarn Wee has been holding your diploma in the sun", "so long he's about to get a cramp!"),
    ("If you stop to chat for 5 seconds,", "that diploma in Ajarn Wee's hand might just fly away!"),
    ("Think you can outrun the press", "and get past Ajarn Wee's sharp eyes?!"),
    ("Ajarn Wee wanted me to ask...", "did you actually pass your senior project?!"),
    ("You survived four grueling years", "you can't be late to your own graduation!"),
    ("Stop and answer our questions!", "Where will you find the energy to wake up for work after this?!"),
    ("Our cameras are rolling!", "Give a sweet smile for Ajarn Wee!"),
    ("Now that you're graduating, will you sell noodles", "or actually work in your field?! Answer me!"),
    ("With speed like that,", "were you ever this fast during course registration?!"),
    ("Judging by that look, you debugged your code", "right outside the classroom, didn't you?! Confess!"),
    ("Ajarn Wee is counting to three!", "If you're not there yet, you're repeating another year!"),
    ("Did you forget your graduation queue card,", "or why else are you sprinting in a panic?!"),


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
