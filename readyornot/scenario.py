"""Load scenario JSON files from readyornot/scenarios/."""
from __future__ import annotations

import json
import string
from pathlib import Path
from typing import List

from .art import load_room_art
from .model import NPC, Door, Item, Room, Scenario

SCENARIO_DIR = Path(__file__).parent / "scenarios"


def list_scenarios() -> List[dict]:
    out = []
    for path in sorted(SCENARIO_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        out.append({k: data[k] for k in ("id", "title", "subtitle", "difficulty")})
    return out


def load_scenario(scenario_id: str) -> Scenario:
    """Build a fresh Scenario (new objects every call, so each run starts clean)."""
    data = json.loads((SCENARIO_DIR / f"{scenario_id}.json").read_text())
    rooms = [Room(**r) for r in data["rooms"]]
    by_id = {r.id: r for r in rooms}
    doors = [Door(**d) for d in data["doors"]]
    for d in doors:
        for rid in (d.a, d.b):
            if rid not in by_id:
                raise ValueError(f"door {d.id} references unknown room {rid}")
            by_id[rid].doors.append(d.id)
    npcs = []
    for tag, n in zip(string.ascii_uppercase, data["npcs"]):
        if n["room"] not in by_id:
            raise ValueError(f"npc {n['id']} is in unknown room {n['room']}")
        npcs.append(NPC(tag=tag, **n))
    evidence = [Item(objective=True, **e) for e in data["evidence"]]
    if not any(r.entry for r in rooms):
        raise ValueError("scenario needs at least one entry room")
    return Scenario(
        id=data["id"],
        title=data["title"],
        subtitle=data["subtitle"],
        difficulty=data["difficulty"],
        briefing=data["briefing"],
        rooms=rooms,
        doors=doors,
        npcs=npcs,
        evidence=evidence,
        art=load_room_art(SCENARIO_DIR / f"{scenario_id}.art"),
    )
