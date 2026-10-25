"""Load scenarios from the scenarios/ folder at the project root.

Each scenario is a folder named after its id:

    scenarios/<id>/scenario.json   rooms, doors, people, evidence, briefing
    scenarios/<id>/detailed.art    80-column scenes (optional)
    scenarios/<id>/compact.art     phone-sized scenes (optional)
"""
from __future__ import annotations

import json
import string
from pathlib import Path
from typing import List

from .art import load_room_art
from .model import NPC, Door, Item, Room, Scenario

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def list_scenarios() -> List[dict]:
    out = []
    for path in sorted(SCENARIO_DIR.glob("*/scenario.json")):
        data = json.loads(path.read_text())
        out.append({k: data[k] for k in ("id", "title", "subtitle", "difficulty")})
    return out


def load_scenario(scenario_id: str) -> Scenario:
    """Build a fresh Scenario (new objects every call, so each run starts clean)."""
    folder = SCENARIO_DIR / scenario_id
    data = json.loads((folder / "scenario.json").read_text())
    if data["id"] != scenario_id:
        raise ValueError(f"{folder}/scenario.json has id {data['id']!r}; "
                         f"it must match its folder name")
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
        departure=data.get("departure"),
        banners=data.get("banners", {}),
        headlines=data.get("headlines", {}),
        art=load_room_art(folder / "detailed.art"),
        art_compact=load_room_art(folder / "compact.art"),
    )
