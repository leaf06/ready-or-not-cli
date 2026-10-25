"""ASCII art: room scenes, people drawn by state, and action effects.

Everything here returns plain lists of strings. The engine only queues
markers ("scene", "fx", "mirror"); the CLI turns them into art, so the
rules stay free of presentation.

Two sizes: detailed scenes (up to DETAILED_WIDTH, for an 80-column
terminal) with people drawn standing on the floor, and compact scenes
(up to MAX_WIDTH, for phones) with people in a strip underneath.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .model import ALERT, DEAD, HOSTILE, INCAPACITATED, RESTRAINED, SURRENDERED, UNAWARE, NPC

MAX_WIDTH = 58        # compact art, and everything else drawn here
DETAILED_WIDTH = 78   # detailed scenes
STAGE_ROWS = 6        # the last rows of a detailed scene are its floor
STAGE_LEFT, STAGE_RIGHT = 14, 64  # floor columns clear of the side walls
CELL = 9  # columns per person
PER_ROW = MAX_WIDTH // CELL


def load_room_art(path: Path) -> Dict[str, List[str]]:
    """Parse a .art file: '== room_id ==' headers, '#' comment lines."""
    art: Dict[str, List[str]] = {}
    if not path.exists():
        return art
    current = None
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            continue
        if line.startswith("== ") and line.rstrip().endswith(" =="):
            current = line.strip()[3:-3].strip()
            art[current] = []
        elif current is not None:
            art[current].append(line.rstrip())
    for lines in art.values():
        while lines and not lines[-1]:
            lines.pop()
    return art


# --- people -----------------------------------------------------------------
# Three rows per figure, drawn left-aligned in a CELL-wide column.
FIGURES = {
    "standing": ["   O     ", "  /|\\    ", "  / \\    "],
    "armed":    ["   O     ", "  /|\\_   ", "  / \\    "],
    "hostile":  ["   O  __ ", "  /|--'  ", "  / \\    "],
    "hands_up": ["  \\O/    ", "   |     ", "  / \\    "],
    "cuffed":   ["   O     ", "  (|)    ", "  _/\\_   "],
    "tied":     ["   O     ", "  #|#    ", "  |_|    "],
    "down":     ["         ", "         ", " _o__/_  "],
    "dead":     ["         ", "         ", " _x__/_  "],
}


def figure(n: NPC):
    """The figure key and a short status label for one person."""
    if n.state == DEAD:
        return "dead", "dead"
    if n.state == INCAPACITATED:
        return "down", "down"
    if n.state == RESTRAINED:
        return "cuffed", "cuffed"
    if n.state == SURRENDERED:
        return ("tied", "tied up") if n.bound else ("hands_up", "hands up")
    if n.state == HOSTILE:
        return "hostile", "KID AIMS" if n.minor else "AIMING"
    if n.weapon_visible:
        return "armed", "KID+GUN" if n.minor else "ARMED"
    if n.concealed:
        return "standing", "hands?"
    return "standing", {UNAWARE: "unaware", ALERT: "alert"}.get(n.state, n.state)


def person(n: NPC) -> List[str]:
    """One person as STAGE_ROWS rows of CELL columns: stun, figure, tag, label."""
    key, label = figure(n)
    stunned = n.stunned and n.alive and n.state != RESTRAINED
    return ["  * * *  " if stunned else " " * CELL,
            *FIGURES[key],
            f" [{n.tag}]".ljust(CELL),
            f" {label}"[:CELL].ljust(CELL)]


def people_strip(npcs: List[NPC]) -> List[str]:
    out: List[str] = []
    for start in range(0, len(npcs), PER_ROW):
        cells = [person(n) for n in npcs[start:start + PER_ROW]]
        for i in range(STAGE_ROWS):
            line = "".join(c[i] for c in cells).rstrip()
            if line or i:  # skip an empty stun row
                out.append(line)
    return out


def stage(room_art: List[str], npcs: List[NPC]) -> List[str]:
    """Draw people standing on the floor of a detailed scene.

    Anyone who doesn't fit across the floor goes in a strip underneath.
    """
    lines = [l.ljust(DETAILED_WIDTH) for l in room_art]
    floor = (STAGE_RIGHT - STAGE_LEFT) // (CELL + 1)
    here, extra = npcs[:floor], npcs[floor:]
    if here and len(lines) >= STAGE_ROWS:
        gap = (STAGE_RIGHT - STAGE_LEFT) // len(here)
        top = len(lines) - STAGE_ROWS
        for i, n in enumerate(here):
            col = STAGE_LEFT + gap * i + (gap - CELL) // 2
            for r, cell in enumerate(person(n)):
                if cell.strip():  # blank rows let the floor show through
                    row = lines[top + r]
                    lines[top + r] = row[:col] + cell + row[col + CELL:]
    lines = [l.rstrip() for l in lines]
    if extra:
        lines.append("")
        lines.extend(people_strip(extra))
    return lines


def scene(room_art: List[str], npcs: List[NPC], detailed: bool = False) -> List[str]:
    if detailed:
        return [l[:DETAILED_WIDTH] for l in stage(room_art, npcs)]
    lines = list(room_art)
    if npcs:
        lines.append("")
        lines.extend(people_strip(npcs))
    return [l[:MAX_WIDTH] for l in lines]


def mirror_view(npcs: List[NPC]) -> List[str]:
    """What the mirror sees: a strip of feet under the door."""
    inner = MAX_WIDTH - 4
    alive = [n for n in npcs if n.alive and n.state not in (DEAD, INCAPACITATED)]
    feet = "".join("_||_   " for _ in alive) or "(nothing moving)"
    tags = "".join(f"[{n.tag}]".ljust(7) for n in alive)
    down = len(npcs) - len(alive)
    lines = [
        " ." + "-" * inner + ".",
        " | " + "under the door...".ljust(inner - 1) + "|",
        " | " + ("  " + feet).ljust(inner - 1) + "|",
        " | " + ("  " + tags).ljust(inner - 1) + "|",
    ]
    if down:
        lines.append(" | " + f"  + {down} on the floor".ljust(inner - 1) + "|")
    lines.append(" '" + "-" * inner + "'")
    return lines


# --- effects ----------------------------------------------------------------
FX = {
    "flashbang": [
        r"         \    |    /",
        r"      '.  \   |   /  .'",
        r"    ----=====BANG!=====----",
        r"      .'  /   |   \  '.",
        r"         /    |    \ ",
    ],
    "stinger": [
        r"     .  :  .  :  .  :  .",
        r"   :  . CRACK-CRACK! .  :",
        r"     .  :  .  :  .  :  .",
    ],
    "gas": [
        r"    (  ~  )  ( ~   )  (~  )",
        r"  (   ~   CS  GAS   ~   )",
        r"    ( ~   )  (   ~ )  ( ~ )",
    ],
    "c2": [
        r"        .  *  .   *  .",
        r"     *   \  \ | /  /   *",
        r"   ---===  B O O M  ===---",
        r"     *   /  / | \  \   *",
        r"        '  *  '   *  '",
    ],
    "kick": [
        r"     ______",
        r"    |  __  |  \\",
        r"    | |  | |   >> WHAM!",
        r"    |_|__|_|  //",
    ],
    "kick_fail": [
        r"     ______",
        r"    |  __  |  <- THUD",
        r"    |_|__|_|     (it holds)",
    ],
    "gunfire": [
        r"   ==[||||]=-   *BLAM*  - - - ->",
    ],
    "incoming": [
        r"   <- - - -  *BLAM*   -=[||||]==",
    ],
    "trap_flash": [
        r"      \  |  /    TRAP!",
        r"   ---= FLASH =---",
        r"      /  |  \ ",
    ],
    "trap_explosive": [
        r"     . * ' . * ' . * '",
        r"   *  \\  KA-BOOM!  //  *",
        r"     ' * . ' * . ' * .",
    ],
}

BANNERS = {
    "complete": [
        r"   __  __ ___ ___ ___ ___ ___  _  _",
        r"  |  \/  |_ _/ __/ __|_ _/ _ \| \| |",
        r"  | |\/| || |\__ \__ \| | (_) | .` |",
        r"  |_|  |_|___|___/___/___\___/|_|\_|",
        r"           C O M P L E T E",
    ],
    "incomplete": [
        r"   ___ _  _ ___  ___ ___",
        r"  | __| \| |   \| __|   \ ",
        r"  | _|| .` | |) | _|| |) |",
        r"  |___|_|\_|___/|___|___/",
        r"     objectives incomplete",
    ],
    "kia": [
        r"   _  _____   _",
        r"  | |/ /_ _| /_\ ",
        r"  | ' < | | / _ \ ",
        r"  |_|\_\___/_/ \_\ ",
        r"   element lead down",
    ],
}
