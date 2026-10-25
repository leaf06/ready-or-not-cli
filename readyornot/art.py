"""ASCII art: room scenes, people drawn by state, and action effects.

Everything here returns plain lists of strings. The engine only queues
markers ("scene", "fx", "mirror"); the CLI turns them into art, so the
rules stay free of presentation. Keep every line within MAX_WIDTH so the
game still fits a phone screen.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .model import ALERT, DEAD, HOSTILE, INCAPACITATED, RESTRAINED, SURRENDERED, UNAWARE, NPC

MAX_WIDTH = 58
CELL = 9  # columns per person in the people strip
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
        return "hostile", "AIMING"
    if n.weapon_visible:
        return "armed", "ARMED"
    if n.concealed:
        return "standing", "hands?"
    return "standing", {UNAWARE: "unaware", ALERT: "alert"}.get(n.state, n.state)


def people_strip(npcs: List[NPC]) -> List[str]:
    out: List[str] = []
    for start in range(0, len(npcs), PER_ROW):
        row = npcs[start:start + PER_ROW]
        stun = "".join(("  * * *  " if n.stunned and n.alive and n.state != RESTRAINED
                        else " " * CELL) for n in row)
        if stun.strip():
            out.append(stun.rstrip())
        figs = [figure(n) for n in row]
        for i in range(3):
            out.append("".join(FIGURES[key][i] for key, _ in figs).rstrip())
        out.append("".join(f" [{n.tag}]".ljust(CELL) for n in row).rstrip())
        out.append("".join(f" {label}"[:CELL].ljust(CELL) for _, label in figs).rstrip())
    return out


def scene(room_art: List[str], npcs: List[NPC]) -> List[str]:
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
