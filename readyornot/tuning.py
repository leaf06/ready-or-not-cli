"""Every balance knob in one place.

v0.1 exists to tune mechanics, so if something feels off (suspects too
trigger-happy, flashbangs too strong, etc.) this is the file to edit.
Probabilities are 0.0-1.0. One "tick" is one player action.

The values below are MEDIUM. DIFFICULTIES at the bottom lists what Easy
and Hard change; settings(name) resolves a full copy for one game.
"""
import copy
from types import SimpleNamespace

SECONDS_PER_TICK = 6

# --- Team -------------------------------------------------------------------
OFFICER_NAMES = ["You (Lead)", "Hammer", "Rook", "Ghost", "Echo"]
OFFICER_HP = 100
ARMOR_REDUCTION = 0.20          # fraction of incoming damage the plate absorbs
CRIT_CHANCE = 0.25              # hit finds a gap in the armor: ignores plate...
CRIT_MULTIPLIER = 2.5           # ...and does this much more damage
PLAYER_TARGET_CHANCE = 0.40     # chance a suspect aims at you rather than a teammate
POINT_MAN_TARGET_CHANCE = 0.70  # same, on the turn you come through the door first
PLAYER_ACCURACY = 0.90
TEAM_RETURN_FIRE = 0.45         # chance the squad drops a suspect who just fired
KILL_CHANCE = 0.55              # a hit kills (otherwise incapacitates)
TASER_ACCURACY = 0.80
TASER_STUN = 2

LOADOUTS = {
    "standard": {
        "label": "Standard Assault",
        "desc": "Balanced kit for most warrants.",
        "items": {"flashbang": 2, "stinger": 1, "gas": 1, "c2": 2, "wedge": 2},
    },
    "breacher": {
        "label": "Breacher",
        "desc": "Heavy on C2 for locked and trapped doors.",
        "items": {"flashbang": 1, "stinger": 1, "gas": 0, "c2": 4, "wedge": 2},
    },
    "less_lethal": {
        "label": "Less-Lethal",
        "desc": "Extra grenades for maximum compliance, light on explosives.",
        "items": {"flashbang": 3, "stinger": 2, "gas": 1, "c2": 0, "wedge": 1},
    },
}

# --- Grenades ---------------------------------------------------------------
# stun: ticks the target can't act. comply_bonus: added to comply chance while
# stunned. injure: chance to injure each person in the room.
GRENADES = {
    "flashbang": {"stun": 3, "comply_bonus": 0.30, "injure": 0.00, "loud": True},
    "stinger":   {"stun": 2, "comply_bonus": 0.30, "injure": 0.30, "loud": True},
    "gas":       {"stun": 4, "comply_bonus": 0.25, "injure": 0.00, "loud": False},
}

# --- Breaching --------------------------------------------------------------
KICK_CHANCE = 0.55              # chance to kick open a locked door per attempt
PICK_TICKS = 2
QUIET_ALERT_CHANCE = 0.25       # chance a quiet action alerts each person behind the door
LOUD_RADIUS = 2                 # rooms away a kick / flashbang is heard
C2_STUN = 2
C2_INJURE_CHANCE = 0.15
STUN_RESIST_CHANCE = 0.40      # x aggression: suspect covers up and shrugs off a grenade or C2

# --- Traps ------------------------------------------------------------------
TRAP_FLASH_DISORIENT = 2        # ticks the team is disoriented
DISARM_FAIL_CHANCE = 0.10       # cutting the wrong wire sets the trap off
TRAP_EXPLOSIVE_DAMAGE = (30, 55)
TRAP_EXPLOSIVE_VICTIMS = (1, 3)
DISORIENTED_EXPOSURE = 0.20     # added to suspect accuracy while you're disoriented
DISORIENTED_ACCURACY = 0.60     # multiplier on your accuracy while disoriented
DISORIENTED_PENALTY = 0.20      # subtracted from comply chance while disoriented

# --- Compliance -------------------------------------------------------------
# Base comply chance is (1 - resistance) from the scenario file.
SURPRISE_BONUS = 0.20           # target hadn't noticed you yet
HOSTILE_PENALTY = 0.25          # target already has a weapon on you
INJURED_BONUS = 0.20
YELL_STACK_BONUS = 0.10         # per previous yell at the same person...
MAX_YELL_STACK = 3              # ...up to this many
FOCUSED_YELL_BONUS = 0.10       # 'yell <target>' singles one person out
MORALE_PER_DOWN = 0.06          # per suspect already arrested or neutralized
CIV_FLEE_CHANCE = 0.25          # a civilian who refuses runs instead
SUSPECT_FLEE_CHANCE = 0.50      # a suspect who refuses and doesn't draw runs instead

# --- Suspect AI -------------------------------------------------------------
WEAPONS = {
    "pistol":  {"accuracy": 0.50, "damage": (25, 40), "verb": "fires a pistol at"},
    "shotgun": {"accuracy": 0.60, "damage": (40, 65), "verb": "blasts a shotgun at"},
    "rifle":   {"accuracy": 0.55, "damage": (35, 55), "verb": "opens up with a rifle on"},
    "knife":   {"accuracy": 0.60, "damage": (20, 35), "verb": "lunges with a knife at"},
    "smg":     {"accuracy": 0.55, "damage": (25, 40), "verb": "sprays an SMG at"},
}
INJURED_SUSPECT_ACCURACY = 0.60  # multiplier
MIRROR_SPOTTED_CHANCE = 0.35    # x aggression: alert suspect spots your mirror and shoots through the door
THROUGH_DOOR_ACCURACY = 0.50    # multiplier on accuracy for blind fire through a door
AMBUSH_CHANCE = 0.80            # x aggression: alert suspect fires as you enter
ESCALATION_CHANCE = 0.75        # x aggression: per tick, an alert suspect raises a weapon
QUICK_DRAW_CHANCE = 0.70       # x aggression: a suspect who refuses draws AND fires, no warning
FAKE_SURRENDER_CHANCE = 0.25    # x aggression: per tick, uncuffed suspect pulls a hidden weapon
SURRENDER_LAPSE_CHANCE = 0.20   # per tick, an uncuffed suspect you left behind stops complying
ROAM_CHANCE = 0.18              # per tick, an alert suspect moves to a neighbouring room
ESCAPE_MOVE_CHANCE = 0.35       # per tick, an alerted runner moves a room closer to the exit
ESCAPE_CHANCE = 0.50            # per tick, a runner at an unwedged escape door gets out
FLANK_HOSTILE_CHANCE = 0.70     # x aggression: a roaming suspect walks in weapon-up

# --- Scoring (max 100) ------------------------------------------------------
SCORE_OBJECTIVES = 35
SCORE_ARRESTS = 20
SCORE_REPORTS = 10
SCORE_EVIDENCE = 10
SCORE_TEAM = 15
SCORE_CONDUCT = 10
TEAM_INJURED_COST = 4
TEAM_DOWN_COST = 10
PENALTY_UNAUTHORIZED_FORCE = 5
PENALTY_UNAUTHORIZED_DEADLY = 15
PENALTY_CIVILIAN_KILLED = 20
PENALTY_CIVILIAN_INJURED = 3
PENALTY_DEADLY_JUVENILE = 20    # on top of unauthorized deadly force
GRADES = [(95, "S"), (90, "A"), (80, "B"), (70, "C"), (60, "D"), (0, "F")]
# Hard-only knobs (neutral on Easy and Medium).
SUSPECT_ACCURACY_MULT = 1.0     # multiplier on every suspect weapon's accuracy
SUSPECT_RESISTANCE_BONUS = 0.0  # added to every suspect's resistance (harder to make comply)

# --- Difficulty presets -----------------------------------------------------
# Only what differs from the Medium values above. LOADOUTS replace whole kits.
DIFFICULTIES = {
    "easy": {
        "label": "Easy",
        "desc": "Forgiving. Intel and utility are risk-free and you carry plenty of grenades.",
        "overrides": {
            "CRIT_CHANCE": 0.20,
            "POINT_MAN_TARGET_CHANCE": 0.40,
            "TEAM_RETURN_FIRE": 0.50,
            "STUN_RESIST_CHANCE": 0.0,
            "DISARM_FAIL_CHANCE": 0.0,
            "MIRROR_SPOTTED_CHANCE": 0.0,
            "ESCALATION_CHANCE": 0.60,
            "QUICK_DRAW_CHANCE": 0.50,
            "ROAM_CHANCE": 0.12,
            "FLANK_HOSTILE_CHANCE": 0.50,
            "LOADOUTS": {
                "standard": {"flashbang": 3, "stinger": 2, "gas": 1, "c2": 2, "wedge": 3},
                "breacher": {"flashbang": 2, "stinger": 1, "gas": 1, "c2": 4, "wedge": 2},
                "less_lethal": {"flashbang": 4, "stinger": 3, "gas": 2, "c2": 1, "wedge": 2},
            },
        },
    },
    "medium": {
        "label": "Medium",
        "desc": "Careful play is rewarded but never safe. Gear is scarce.",
        "overrides": {},
    },
    "hard": {
        "label": "Hard",
        "desc": "Suspects are sharper, tougher to break, and quicker to fight. One mistake can end it.",
        "overrides": {
            "ARMOR_REDUCTION": 0.15,
            "CRIT_CHANCE": 0.30,
            "POINT_MAN_TARGET_CHANCE": 0.80,
            "TEAM_RETURN_FIRE": 0.40,
            "KICK_CHANCE": 0.45,
            "STUN_RESIST_CHANCE": 0.55,
            "DISARM_FAIL_CHANCE": 0.15,
            "MIRROR_SPOTTED_CHANCE": 0.50,
            "AMBUSH_CHANCE": 0.90,
            "ESCALATION_CHANCE": 0.90,
            "QUICK_DRAW_CHANCE": 0.85,
            "FAKE_SURRENDER_CHANCE": 0.35,
            "SURRENDER_LAPSE_CHANCE": 0.30,
            "ROAM_CHANCE": 0.22,
            "FLANK_HOSTILE_CHANCE": 0.85,
            "SUSPECT_ACCURACY_MULT": 1.15,
            "SUSPECT_RESISTANCE_BONUS": 0.10,
            "LOADOUTS": {
                "standard": {"flashbang": 2, "stinger": 1, "gas": 0, "c2": 1, "wedge": 1},
                "breacher": {"flashbang": 1, "stinger": 0, "gas": 0, "c2": 3, "wedge": 1},
                "less_lethal": {"flashbang": 2, "stinger": 2, "gas": 1, "c2": 0, "wedge": 1},
            },
        },
    },
}
DEFAULT_DIFFICULTY = "medium"


def settings(difficulty: str = DEFAULT_DIFFICULTY) -> SimpleNamespace:
    """A private copy of every knob with the difficulty's overrides applied.

    Each Game holds its own copy, so presets never leak between games.
    """
    values = {k: copy.deepcopy(v) for k, v in globals().items() if k.isupper()}
    for key, val in DIFFICULTIES[difficulty]["overrides"].items():
        if key == "LOADOUTS":
            for kit, items in val.items():
                values["LOADOUTS"][kit]["items"] = dict(items)
        else:
            values[key] = val
    values["DIFFICULTY"] = difficulty
    return SimpleNamespace(**values)
