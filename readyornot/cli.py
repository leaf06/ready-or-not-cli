"""Menus, briefing, the command prompt, and the debrief."""
from __future__ import annotations

import argparse
from typing import List, Optional

from . import __version__
from . import tuning as T
from .engine import Game
from .scenario import list_scenarios, load_scenario
from .scoring import score
from .ui import out, paint, rule, set_color

try:  # command history and line editing; macOS ships libedit
    import readline  # noqa: F401
except ImportError:
    pass

TITLE = r"""
  ____                _                     _   _       _
 |  _ \ ___  __ _  __| |_   _    ___  _ __ | \ | | ___ | |_
 | |_) / _ \/ _` |/ _` | | | |  / _ \| '__||  \| |/ _ \| __|
 |  _ <  __/ (_| | (_| | |_| | | (_) | |   | |\  | (_) | |_
 |_| \_\___|\__,_|\__,_|\__, |  \___/|_|   |_| \_|\___/ \__|
                        |___/          terminal tactical"""


class Quit(Exception):
    pass


def ask(prompt: str) -> str:
    try:
        return input(paint(prompt, "title")).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise Quit()


def choose(prompt: str, options: List[str]) -> int:
    for i, opt in enumerate(options, 1):
        out(f"  [{i}] {opt}")
    while True:
        ans = ask(prompt)
        if ans.isdigit() and 1 <= int(ans) <= len(options):
            return int(ans) - 1
        out(f"Enter a number from 1 to {len(options)}.", "warn")


def flush(game: Game) -> None:
    for style, text in game.drain():
        out(text, style)


def play(scenario_id: str, seed: Optional[int]) -> None:
    scn = load_scenario(scenario_id)
    rule()
    out(f"{scn.title}: {scn.subtitle}", "title")
    out(f"Difficulty: {scn.difficulty}", "dim")
    rule()
    for para in scn.briefing:
        out(para, "radio")
        out()

    entries = [r for r in scn.rooms if r.entry]
    out("Choose your entry point:", "title")
    entry = entries[choose("Entry > ", [f"{r.name}: {r.desc}" for r in entries])].id

    keys = list(T.LOADOUTS)
    out("\nChoose a loadout (everyone carries a rifle, a taser, a mirror gun and zip-ties):", "title")
    labels = []
    for k in keys:
        lo = T.LOADOUTS[k]
        gear = ", ".join(f"{n} x{c}" for n, c in lo["items"].items())
        labels.append(f"{lo['label']}: {lo['desc']} ({gear})")
    loadout = keys[choose("Loadout > ", labels)]

    game = Game(scn, loadout, entry, seed=seed)
    out()
    out('TOC: "All elements, you are cleared to go. Good luck."', "radio")
    out("Type 'help' for commands.", "dim")
    out()
    game.cmd_look([])
    flush(game)

    while not game.over:
        room = game.rooms[game.team_room].name
        prompt = f"\n[{game.clock} | {room} | {game.player.hp} HP] > "
        line = ask(prompt)
        if line.lower() in ("end", "quit", "exit", "exfil"):
            if not game.objectives_done():
                if ask("Objectives aren't complete. End the mission anyway? (y/n) ").lower()[:1] != "y":
                    continue
            game.end_mission()
        else:
            game.execute(line)
        flush(game)

    debrief(game)


def debrief(game: Game) -> None:
    result = score(game)
    out()
    rule("title")
    headline = {"complete": "MISSION COMPLETE", "incomplete": "MISSION ENDED: objectives incomplete",
                "kia": "MISSION FAILED: element lead KIA"}[game.outcome]
    out(headline, "danger" if game.outcome == "kia" else "title")
    out(f"Time on target: {game.clock}", "dim")
    rule("title")
    for label, pts, mx in result["rows"]:
        out(f"  {label:<44} {pts:>3} / {mx}", "good" if pts == mx else "info")
    for text, pts in result["penalties"]:
        out(f"  PENALTY: {text:<35} -{pts}", "danger")
    rule()
    out(f"  Suspects arrested {result['suspects_arrested']}, killed {result['suspects_killed']} · "
        f"Civilians rescued {result['civilians_rescued']}, killed {result['civilians_dead']}", "info")
    out(f"  SCORE {result['total']} / 100   GRADE {result['grade']}", "alert")
    rule("title")


def how_to_play() -> None:
    out("""\
You lead a five-officer SWAT element. Each command you type is one action,
and after each action the house reacts: suspects hear noise, move around,
raise weapons and shoot.

The basics:
  1. Intel before entry. 'mirror' a closed door to see who's inside and
     whether it's trapped.
  2. Pick how to open it. 'open' and 'pick' are quiet. 'kick' and 'c2' are
     loud, but C2 stuns the room and sets off traps safely.
  3. Use utility. A flashbang through an open door stuns everyone inside
     for a few turns. Stunned people can't shoot and comply far more often.
     'breach 2 c2 flash' does all of it in one go.
  4. Take control. 'yell' at everyone. Anyone who gives up gets 'restrain'ed,
     and then you 'report' them to TOC. Cuff suspects quickly, because some
     hide weapons and fake surrender.
  5. ROE. Only shoot suspects who are visibly armed and not surrendering.
     A suspect who raises a weapon gives you one action to respond: shoot,
     tase, or yell again.
  6. 'collect' evidence, finish the objectives, and type 'end'.

The score adds up objectives, arrests over kills, reports, evidence, team
health and conduct, then gives you a grade from S down to F.""")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="readyornot", description="Terminal tactical game.")
    ap.add_argument("--seed", type=int, help="fix the random seed (repeatable runs, for tuning)")
    ap.add_argument("--no-color", action="store_true", help="disable ANSI colours")
    ap.add_argument("--scenario", help="skip the menu and start this scenario id")
    args = ap.parse_args(argv)
    if args.no_color:
        set_color(False)

    try:
        out(TITLE, "danger")
        out(f"  v{__version__}", "dim")
        if args.scenario:
            play(args.scenario, args.seed)
            return 0
        while True:
            out()
            pick = choose("> ", ["Select scenario", "How to play", "Quit"])
            if pick == 0:
                scns = list_scenarios()
                out("\nScenarios:", "title")
                idx = choose("Scenario > ", [f"{s['title']}: {s['subtitle']} [{s['difficulty']}]"
                                             for s in scns])
                play(scns[idx]["id"], args.seed)
            elif pick == 1:
                how_to_play()
            else:
                return 0
    except Quit:
        out("Stand down.", "dim")
        return 0
