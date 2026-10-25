"""Balance simulator: plays a scenario many times with scripted bots.

    python3 tools/simulate.py                 # 500 runs per bot, every difficulty
    python3 tools/simulate.py -n 2000 --difficulty hard

Change readyornot/tuning.py, rerun, and compare. The "tactical" bot mirrors,
disarms and flashes every room. The "reckless" bot kicks doors and walks in.
A good tuning keeps tactical clearly ahead without being risk-free.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from readyornot.engine import Game  # noqa: E402
from readyornot.model import HOSTILE, INCAPACITATED, SURRENDERED  # noqa: E402
from readyornot.scenario import load_scenario  # noqa: E402
from readyornot.scoring import score  # noqa: E402
from readyornot.tuning import DIFFICULTIES  # noqa: E402


def next_step(game: Game, target_ok):
    """Exit number of the first door on the shortest path to a room target_ok accepts."""
    start = game.team_room
    q = deque([(start, None)])
    seen = {start}
    while q:
        room, first = q.popleft()
        if room != start and target_ok(game.rooms[room]):
            return first
        for did in game.rooms[room].doors:
            d = game.doors[did]
            nxt = d.other(room)
            if nxt in seen:
                continue
            seen.add(nxt)
            if room == start:
                idx = [x[0].id for x in game.exits()].index(d.id) + 1
                q.append((nxt, idx))
            else:
                q.append((nxt, first))
    return None


def act(game: Game, tactical: bool) -> str:
    here = game.room_npcs(game.team_room)
    for n in here:
        if n.state == HOSTILE and n.weapon_visible:
            return f"shoot {n.tag}"
    if any(n.active for n in here):
        return "yell"
    for n in here:
        if n.state in (SURRENDERED, INCAPACITATED):
            return f"restrain {n.tag}"
    if any(n.resolved and not n.reported for n in here):
        return "report all"
    if any(i.room == game.team_room and not i.collected for i in game.items.values()):
        return "collect"
    if game.objectives_done():
        return "end"

    def wanted(room):
        if room.outdoor:
            return False
        if not room.visited:
            return True
        return any(not n.resolved for n in game.room_npcs(room.id)) or any(
            i.room == room.id and not i.collected for i in game.items.values())

    step = next_step(game, wanted)
    if step is None:
        return "end"
    d, dest = game.exits()[step - 1]
    first_time = not game.rooms[dest].visited
    if tactical and d.kind == "door" and d.state == "closed":
        if not getattr(d, "_mirrored", False):
            d._mirrored = True
            return f"mirror {step}"
        if d.trap and d.trap_known:
            return f"disarm {step}"
    grenade = ""
    if tactical and first_time and game.inv["flashbang"] > 0:
        grenade = " flash"
    elif tactical and first_time and game.inv["stinger"] > 0:
        grenade = " stinger"
    method = ""
    if d.kind == "door" and d.state == "closed" and d.locked and d.lock_known:
        method = " c2" if tactical and game.inv["c2"] > 0 else " kick"
    if not d.passable or grenade:
        return f"breach {step}{method}{grenade}"
    return f"move {step}"


def run(scenario_id: str, tactical: bool, seed: int, difficulty: str) -> dict:
    scn = load_scenario(scenario_id)
    entry = next(r.id for r in scn.rooms if r.entry)
    game = Game(scn, "standard", entry, seed=seed, difficulty=difficulty)
    for _ in range(400):
        if game.over:
            break
        game.execute(act(game, tactical))
        game.drain()
    if not game.over:
        game.end_mission()
    return {"outcome": game.outcome, "ticks": game.time, **score(game)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=500)
    ap.add_argument("--scenario", default="larkspur_lane")
    ap.add_argument("--difficulty", choices=list(DIFFICULTIES), action="append",
                    help="repeatable; default runs all of them")
    args = ap.parse_args()
    for difficulty in args.difficulty or list(DIFFICULTIES):
        print(f"\n=== {DIFFICULTIES[difficulty]['label']} ===")
        report(args, difficulty)


def report(args, difficulty: str) -> None:
    for name, tactical in (("tactical", True), ("reckless", False)):
        results = [run(args.scenario, tactical, s, difficulty) for s in range(args.n)]
        outcomes = Counter(r["outcome"] for r in results)
        grades = Counter(r["grade"] for r in results)
        avg = lambda k: sum(r[k] for r in results) / len(results)  # noqa: E731
        print(f"{name} bot, {args.n} runs")
        print("  outcome: " + ", ".join(f"{k} {v / args.n:.0%}" for k, v in outcomes.most_common()))
        print("  grades:  " + ", ".join(f"{g} {grades[g]}" for g in "SABCDF"))
        print(f"  avg score {avg('total'):.1f} · avg arrests {avg('suspects_arrested'):.1f}"
              f" · kills {avg('suspects_killed'):.1f} · civ deaths {avg('civilians_dead'):.2f}"
              f" · time {avg('ticks'):.0f} ticks")


if __name__ == "__main__":
    main()
