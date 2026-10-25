from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# NPC states
UNAWARE, ALERT, HOSTILE = "unaware", "alert", "hostile"
SURRENDERED, RESTRAINED = "surrendered", "restrained"
INCAPACITATED, DEAD = "incapacitated", "dead"
ESCAPED = "escaped"             # got out of the building; no longer in any room
ACTIVE_STATES = (UNAWARE, ALERT, HOSTILE)


@dataclass
class Room:
    id: str
    name: str
    floor: str
    desc: str
    outdoor: bool = False
    entry: bool = False
    doors: List[str] = field(default_factory=list)
    visited: bool = False
    cleared: bool = False


@dataclass
class Door:
    id: str
    a: str
    b: str
    name: str
    kind: str = "door"          # "door" can be opened/locked; "opening" is always passable
    locked: bool = False
    trap: Optional[str] = None  # "flash" | "explosive"
    state: str = "closed"       # closed | open | broken
    wedged: bool = False
    escape: bool = False        # suspects who reach this door can flee through it
    lock_known: bool = False
    trap_known: bool = False

    def other(self, room_id: str) -> str:
        return self.b if room_id == self.a else self.a

    @property
    def passable(self) -> bool:
        return self.kind != "door" or self.state in ("open", "broken")


@dataclass
class NPC:
    id: str
    tag: str                    # letter the player uses to target them
    kind: str                   # "suspect" | "civilian"
    desc: str
    room: str
    weapon: Optional[str] = None
    concealed: bool = False     # weapon hidden until they draw it or are searched
    bound: bool = False         # tied up: starts compliant, never resists or runs
    minor: bool = False         # juvenile: deadly force is never authorized
    escapes: bool = False       # once alerted, heads for an escape door
    resistance: float = 0.4
    aggression: float = 0.0
    state: str = UNAWARE
    stunned: int = 0
    stun_bonus: float = 0.0
    injured: bool = False
    yells: int = 0
    identified: bool = False
    hostile_since: int = -1
    reported: bool = False
    killed_by: Optional[str] = None
    dropped_item: Optional[str] = None

    @property
    def alive(self) -> bool:
        return self.state != DEAD

    @property
    def active(self) -> bool:
        return self.state in ACTIVE_STATES

    @property
    def weapon_visible(self) -> bool:
        return bool(self.weapon) and not self.concealed

    @property
    def resolved(self) -> bool:
        return self.state in (RESTRAINED, DEAD)


@dataclass
class Item:
    id: str
    name: str
    room: str
    objective: bool = False
    collected: bool = False


@dataclass
class Officer:
    name: str
    hp: int = 100
    max_hp: int = 100
    is_player: bool = False

    @property
    def down(self) -> bool:
        return self.hp <= 0

    @property
    def status(self) -> str:
        if self.down:
            return "DOWN"
        if self.hp < self.max_hp:
            return "injured"
        return "healthy"


@dataclass
class Scenario:
    id: str
    title: str
    subtitle: str
    difficulty: str
    briefing: List[str]
    rooms: List[Room]
    doors: List[Door]
    npcs: List[NPC]
    evidence: List[Item]
    art: Dict[str, List[str]] = field(default_factory=dict)          # detailed, 80 columns
    art_compact: Dict[str, List[str]] = field(default_factory=dict)  # narrow screens
