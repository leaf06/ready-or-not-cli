"""Core game engine.

The engine never prints. Everything the player should see goes through
Game.say(); the CLI drains Game.messages after each command. That keeps the
rules testable and makes a different front end possible later.

Turn order: the player's command resolves, then (if it took time) tick() runs
the world: hostile suspects in your room fire, others react, suspects
elsewhere move, and stun timers count down.
"""
from __future__ import annotations

import random
from collections import deque
from typing import Dict, List, Optional, Tuple

from . import tuning
from .model import (ALERT, DEAD, ESCAPED, HOSTILE, INCAPACITATED, RESTRAINED, SURRENDERED,
                    UNAWARE, NPC, Door, Item, Officer, Scenario)

GRENADE_ALIASES = {
    "flash": "flashbang", "flashbang": "flashbang", "fb": "flashbang", "bang": "flashbang",
    "stinger": "stinger", "sting": "stinger",
    "gas": "gas", "cs": "gas",
}
BREACH_METHODS = {"open": "open", "pick": "pick", "kick": "kick", "ram": "kick", "c2": "c2"}
FILLER = {"the", "at", "on", "to", "into", "through", "door", "with", "and", "go"}

HELP = """\
MOVEMENT & INTEL
  look (l)                    describe your room, its exits and people
  map (m)                     floor plan with cleared rooms
  move <exit>  (go, enter)    move the team through an open door
  mirror <exit>  (peek)       check under a door: people inside, traps
DOORS (an <exit> is its number from 'look', or part of its name)
  open <exit> / close <exit>  quiet, but a locked door won't budge
  pick <exit>                 quietly pick a lock (takes 2 turns)
  kick <exit>                 loud, may take a few tries if locked
  c2 <exit>                   blow the door, stunning everyone behind it
  wedge <exit>                wedge a closed door so no one can use it
  disarm <exit>               disarm a trap you've spotted
  throw <flash|stinger|gas> <exit>   grenade through an open door
  breach <exit> [open|pick|kick|c2] [flash|stinger|gas]
                              breach, throw, and enter in one go
PEOPLE (a <target> is their letter, like 'a')
  yell [target]  (comply, y)  order everyone here to comply, or single one out
  restrain <target>  (cuff)   zip-tie someone who surrendered or is down
  shoot <target>              deadly force
  taser <target>  (tase)      less-lethal: subdues a non-compliant person
  report [target|all]  (r)    report secured or dead people in this room to TOC (free)
  collect  (secure)           bag all evidence and weapons in the room
OTHER
  wait (z) · status (s) · objectives (o) · help (?) · end (finish the mission)
  art on|off                  show or hide the ASCII art (free)

ROE: deadly force is authorized only against a suspect who is VISIBLY
armed and not surrendering. 'Hands not visible' is not a weapon."""


class Game:
    def __init__(self, scenario: Scenario, loadout: str, entry: str,
                 seed: Optional[int] = None, rng: Optional[random.Random] = None,
                 difficulty: str = tuning.DEFAULT_DIFFICULTY):
        self.T = tuning.settings(difficulty)
        self.difficulty = difficulty
        self.rng = rng or random.Random(seed)
        self.scenario = scenario
        self.rooms = {r.id: r for r in scenario.rooms}
        self.doors = {d.id: d for d in scenario.doors}
        self.npcs: List[NPC] = scenario.npcs
        self.items: Dict[str, Item] = {i.id: i for i in scenario.evidence}
        self.officers = [Officer(n, hp=self.T.OFFICER_HP, max_hp=self.T.OFFICER_HP, is_player=(i == 0))
                         for i, n in enumerate(self.T.OFFICER_NAMES)]
        self.inv = dict(self.T.LOADOUTS[loadout]["items"])
        self.loadout = loadout
        self.time = 0
        self.disoriented = 0
        self.penalties: List[Tuple[str, int]] = []
        self.messages: List[Tuple[str, str]] = []
        self.over = False
        self.outcome: Optional[str] = None  # "complete" | "incomplete" | "kia"
        self.objectives_announced = False
        self.in_tick = False
        self.just_entered = False
        self.team_room = entry
        self.rooms[entry].visited = True
        self._dist_cache: Dict[str, Dict[str, int]] = {}

        self.commands = {}
        for names, fn in [
            (("help", "?", "h"), self.cmd_help),
            (("look", "l"), self.cmd_look),
            (("map", "m"), self.cmd_map),
            (("status", "s", "team", "inv", "i"), self.cmd_status),
            (("objectives", "o", "obj"), self.cmd_objectives),
            (("move", "go", "enter", "walk"), self.cmd_move),
            (("mirror", "peek", "check"), self.cmd_mirror),
            (("open",), self.cmd_open),
            (("close", "shut"), self.cmd_close),
            (("pick", "lockpick"), self.cmd_pick),
            (("kick", "ram"), self.cmd_kick),
            (("c2", "blow"), self.cmd_c2),
            (("wedge",), self.cmd_wedge),
            (("disarm",), self.cmd_disarm),
            (("throw", "toss", "deploy"), self.cmd_throw),
            (("breach", "b"), self.cmd_breach),
            (("yell", "comply", "y", "shout"), self.cmd_yell),
            (("restrain", "cuff", "arrest", "zip"), self.cmd_restrain),
            (("shoot", "fire", "kill"), self.cmd_shoot),
            (("taser", "tase"), self.cmd_taser),
            (("report", "r"), self.cmd_report),
            (("collect", "secure", "bag", "grab"), self.cmd_collect),
            (("wait", "z", "hold"), self.cmd_wait),
        ]:
            for n in names:
                self.commands[n] = fn

    # ------------------------------------------------------------------ output
    def say(self, text: str, style: str = "info") -> None:
        self.messages.append((style, text))

    def drain(self) -> List[Tuple[str, str]]:
        out, self.messages = self.messages, []
        return out

    # ------------------------------------------------------------------ helpers
    @property
    def player(self) -> Officer:
        return self.officers[0]

    @property
    def clock(self) -> str:
        s = self.time * self.T.SECONDS_PER_TICK
        return f"T+{s // 60:02d}:{s % 60:02d}"

    def room_npcs(self, room_id: str) -> List[NPC]:
        return [n for n in self.npcs if n.room == room_id]

    def exits(self) -> List[Tuple[Door, str]]:
        return [(self.doors[d], self.doors[d].other(self.team_room))
                for d in self.rooms[self.team_room].doors]

    def dist(self, a: str, b: str) -> int:
        if a not in self._dist_cache:
            seen = {a: 0}
            q = deque([a])
            while q:
                cur = q.popleft()
                for did in self.rooms[cur].doors:
                    nxt = self.doors[did].other(cur)
                    if nxt not in seen:
                        seen[nxt] = seen[cur] + 1
                        q.append(nxt)
            self._dist_cache[a] = seen
        return self._dist_cache[a].get(b, 99)

    def label(self, n: NPC) -> str:
        if n.identified or n.state == HOSTILE or n.weapon_visible:
            who = n.kind.capitalize()
        else:
            who = "Unknown"
        return f"[{n.tag}] {who}, {n.desc}"

    def npc_line(self, n: NPC) -> str:
        bits = [self.label(n)]
        if n.minor:
            bits.append("JUVENILE")
        if n.state == DEAD:
            bits.append("DEAD")
        else:
            if n.weapon_visible and n.active:
                bits.append(f"armed: {n.weapon}")
            elif n.active and n.concealed:
                bits.append("hands not visible")
            state = {UNAWARE: "unaware", ALERT: "alert", HOSTILE: "WEAPON RAISED",
                     SURRENDERED: "hands up", RESTRAINED: "restrained",
                     INCAPACITATED: "down, incapacitated"}[n.state]
            if n.bound and n.state == SURRENDERED:
                state = "tied up"
            bits.append(state)
            if n.stunned and n.active:
                bits.append("stunned")
            if n.injured and n.state != INCAPACITATED:
                bits.append("injured")
        if n.reported:
            bits.append("reported")
        return " · ".join(bits)

    def door_status(self, d: Door) -> str:
        if d.kind != "door":
            return "open passage"
        bits = [{"closed": "closed", "open": "open", "broken": "breached"}[d.state]]
        if d.state == "closed" and d.lock_known:
            bits.append("locked" if d.locked else "unlocked")
        if d.wedged:
            bits.append("wedged")
        if d.trap and d.trap_known:
            bits.append("TRAPPED")
        return ", ".join(bits)

    def resolve_door(self, args: List[str]) -> Optional[Door]:
        exits = self.exits()
        if not args:
            if len(exits) == 1:
                return exits[0][0]
            self.say("Which way? Give an exit number or name (see 'look').", "warn")
            return None
        text = " ".join(args)
        if text.isdigit():
            i = int(text) - 1
            if 0 <= i < len(exits):
                return exits[i][0]
            self.say(f"There's no exit {text} here.", "warn")
            return None
        matches = []
        for d, dest in exits:
            room = self.rooms[dest]
            if any(text in s for s in (d.name.lower(), room.name.lower(), room.id)):
                matches.append(d)
        if len(matches) == 1:
            return matches[0]
        if not matches:
            self.say(f"No exit matching '{text}'. Type 'look' to see exits.", "warn")
        else:
            self.say(f"'{text}' could mean more than one exit. Use its number.", "warn")
        return None

    def resolve_npc(self, args: List[str]) -> Optional[NPC]:
        if not args:
            self.say("Who? Give their letter, like 'a'.", "warn")
            return None
        tag = args[0].strip("[]").upper()
        for n in self.room_npcs(self.team_room):
            if n.tag == tag:
                return n
        self.say(f"There's no one tagged [{tag}] in this room.", "warn")
        return None

    def penalize(self, text: str, points: int) -> None:
        self.penalties.append((text, points))
        self.say(f"PENALTY: {text} (-{points})", "danger")

    def suspects_down(self) -> int:
        return sum(1 for n in self.npcs if n.kind == "suspect" and not n.active)

    # ------------------------------------------------------------------ main entry
    def execute(self, line: str) -> None:
        if self.over:
            return
        words = line.strip().lower().split()
        if not words:
            return
        verb = words[0]
        args = [w for w in words[1:] if w not in FILLER]
        if verb == "end":
            self.end_mission()
            return
        fn = self.commands.get(verb)
        if fn is None:
            self.say(f"Unknown command '{verb}'. Type 'help' for commands.", "warn")
            return
        took_time = fn(args)
        if took_time and not self.over:
            self.tick()
        if not self.over:
            self.check_objectives()

    # ------------------------------------------------------------------ world tick
    def tick(self) -> None:
        self.in_tick = True
        self.time += 1
        here = [n for n in self.room_npcs(self.team_room) if n.alive]

        # 1. Hostile suspects in your room shoot.
        for n in here:
            if (n.state == HOSTILE and not n.stunned and n.weapon
                    and n.hostile_since < self.time):
                self.suspect_attack(n)
                if self.over:
                    self.in_tick = False
                    return

        # 2. Everyone else in your room reacts.
        for n in here:
            if n.stunned or not n.alive:
                continue
            if n.state == UNAWARE and not self.just_entered:
                n.state = ALERT
                self.say(f"{self.label(n)} notices you.", "warn")
            elif (n.state == ALERT and n.kind == "suspect" and n.weapon
                  and not self.just_entered
                  and self.rng.random() < n.aggression * self.T.ESCALATION_CHANCE):
                self.go_hostile(n)
            elif (n.state == SURRENDERED and n.kind == "suspect" and n.weapon
                  and self.rng.random() < n.aggression * self.T.FAKE_SURRENDER_CHANCE):
                self.say(f"{self.label(n)} was faking it and pulls a hidden {n.weapon}!", "danger")
                self.go_hostile(n)

        # 3. People elsewhere.
        for n in self.npcs:
            if n.room == self.team_room or not n.alive or n.state == ESCAPED:
                continue
            if n.state == HOSTILE:
                n.state = ALERT
            if (n.state == SURRENDERED and not n.bound
                    and self.rng.random() < self.T.SURRENDER_LAPSE_CHANCE):
                n.state = ALERT
                self.rearm(n)
            if n.kind == "suspect" and n.state == ALERT and not n.stunned:
                if n.escapes:
                    self.run_for_exit(n)
                elif self.rng.random() < self.T.ROAM_CHANCE:
                    self.npc_move(n, allow_team_room=True)

        # 4. Timers.
        for n in self.npcs:
            if n.stunned:
                n.stunned -= 1
        if self.disoriented:
            self.disoriented -= 1
            if not self.disoriented:
                self.say("Your vision clears.", "info")

        room = self.rooms[self.team_room]
        if not any(n.active for n in self.room_npcs(room.id)):
            room.cleared = True
        self.just_entered = False
        self.in_tick = False

    # ------------------------------------------------------------------ combat
    def pick_target(self) -> Officer:
        mates = [o for o in self.officers[1:] if not o.down]
        chance = self.T.POINT_MAN_TARGET_CHANCE if self.just_entered else self.T.PLAYER_TARGET_CHANCE
        if not mates or self.rng.random() < chance:
            return self.player
        return self.rng.choice(mates)

    def damage_officer(self, o: Officer, raw: int, can_crit: bool = False) -> None:
        if can_crit and self.rng.random() < self.T.CRIT_CHANCE:
            dmg = round(raw * self.T.CRIT_MULTIPLIER)
            self.say("  Critical hit, past the armor!", "danger")
        else:
            dmg = max(1, round(raw * (1 - self.T.ARMOR_REDUCTION)))
        o.hp = max(0, o.hp - dmg)
        if o.down:
            self.say(f"  {o.name} {'are' if o.is_player else 'is'} DOWN!", "danger")
            if o.is_player:
                self.end_mission(kia=True)
        else:
            self.say(f"  {o.name} hit (-{dmg} HP, {o.hp} left).", "danger")

    def suspect_attack(self, n: NPC) -> None:
        w = self.T.WEAPONS[n.weapon]
        target = self.pick_target()
        acc = w["accuracy"] * self.T.SUSPECT_ACCURACY_MULT
        acc += self.T.DISORIENTED_EXPOSURE if self.disoriented else 0
        if n.injured:
            acc *= self.T.INJURED_SUSPECT_ACCURACY
        if n.weapon != "knife":
            self.say("incoming", "fx")
        self.say(f"{self.label(n)} {w['verb']} {target.name}!", "danger")
        if self.rng.random() < acc:
            self.damage_officer(target, self.rng.randint(*w["damage"]), can_crit=True)
        else:
            self.say("  Missed!", "warn")
        if n.weapon != "knife":
            self.noise(n.room, None)
        if self.over:
            return
        mates = [o for o in self.officers[1:] if not o.down]
        if mates and self.rng.random() < self.T.TEAM_RETURN_FIRE:
            shooter = self.rng.choice(mates)
            self.say(f"  {shooter.name} returns fire.", "alert")
            self.neutralize(n, by="team")

    def go_hostile(self, n: NPC, immediate: bool = False) -> None:
        n.state = HOSTILE
        n.concealed = False
        n.identified = True
        if immediate:
            n.hostile_since = -1
        elif not self.in_tick and self.rng.random() < n.aggression * self.T.QUICK_DRAW_CHANCE:
            n.hostile_since = -1
            self.say(f"{self.label(n)} draws a {n.weapon} and fires!", "danger")
        else:
            # Gives the player one action to respond before they fire.
            n.hostile_since = self.time if self.in_tick else self.time + 1
            self.say(f"{self.label(n)} raises a {n.weapon} at the team!", "danger")

    def drop_weapon(self, n: NPC, found: bool = False) -> None:
        if not n.weapon:
            return
        item = Item(id=f"w_{n.id}", name=f"{n.weapon} ({n.desc})", room=n.room)
        self.items[item.id] = item
        n.dropped_item = item.id
        n.identified = True  # anyone carrying a weapon is a suspect
        self.say(f"  {'Found' if found else 'Dropped'}: {item.name}.", "info")
        n.weapon = None
        n.concealed = False

    def rearm(self, n: NPC) -> None:
        item = self.items.get(n.dropped_item or "")
        if item and not item.collected and item.room == n.room:
            n.weapon = item.name.split(" ", 1)[0]
            del self.items[item.id]
            n.dropped_item = None

    def neutralize(self, n: NPC, by: str) -> None:
        if self.rng.random() < self.T.KILL_CHANCE:
            n.state = DEAD
            self.say(f"  {self.label(n)} is killed.", "alert")
        else:
            n.state = INCAPACITATED
            self.say(f"  {self.label(n)} goes down, incapacitated.", "alert")
        n.identified = True
        n.killed_by = by
        n.stunned = 0
        self.drop_weapon(n)

    def deadly_authorized(self, n: NPC) -> bool:
        return n.kind == "suspect" and n.weapon_visible and n.active and not n.minor

    # ------------------------------------------------------------------ noise & movement
    def noise(self, origin: str, radius: Optional[int]) -> None:
        for n in self.npcs:
            if n.state == UNAWARE and (radius is None or self.dist(origin, n.room) <= radius):
                n.state = ALERT

    def quiet_noise(self, room_id: str) -> None:
        for n in self.room_npcs(room_id):
            if n.state == UNAWARE and self.rng.random() < self.T.QUIET_ALERT_CHANCE:
                n.state = ALERT

    def npc_move(self, n: NPC, allow_team_room: bool) -> bool:
        options = []
        for did in self.rooms[n.room].doors:
            d = self.doors[did]
            dest = d.other(n.room)
            if not self.npc_can_use(d, dest):
                continue
            if dest == self.team_room and not allow_team_room:
                continue
            options.append((d, dest))
        if not options:
            return False
        d, dest = self.rng.choice(options)
        src = n.room
        if d.kind == "door" and d.state == "closed":
            d.state, d.locked = "open", False
        n.room = dest
        if src == self.team_room:
            self.say(f"{self.label(n)} bolts through the {d.name}!", "warn")
        elif dest == self.team_room:
            self.say(f"Contact! {self.label(n)} comes through the {d.name}!", "danger")
            self.rooms[dest].cleared = False
            if n.weapon and self.rng.random() < n.aggression * self.T.FLANK_HOSTILE_CHANCE:
                self.go_hostile(n)
        return True

    def npc_can_use(self, d: Door, dest: str) -> bool:
        return not (self.rooms[dest].outdoor or d.wedged or (d.trap and d.state == "closed"))

    def run_for_exit(self, n: NPC) -> None:
        """A runner bolts out an escape door, or moves one room closer to one."""
        for did in self.rooms[n.room].doors:
            d = self.doors[did]
            if d.escape and not d.wedged:
                if d.other(n.room) == self.team_room:
                    return  # the team is standing right outside
                if self.rng.random() < self.T.ESCAPE_CHANCE:
                    d.state, d.locked = "open", False
                    n.state, n.room = ESCAPED, ""
                    self.say(f'TOC: "Element, a suspect just fled out the {d.name}! '
                             f'We lost them."', "danger")
                return
        if self.rng.random() >= self.T.ESCAPE_MOVE_CHANCE:
            return
        step = self.step_toward_exit(n.room)
        if step:
            d, dest = step
            if d.kind == "door" and d.state == "closed":
                d.state, d.locked = "open", False
            n.room = dest
            if dest == self.team_room:
                self.say(f"Contact! {self.label(n)} runs in through the {d.name}!", "danger")
                self.rooms[dest].cleared = False

    def step_toward_exit(self, start: str) -> Optional[Tuple[Door, str]]:
        """First move on the shortest path to an unwedged escape door, avoiding the team."""
        q = deque([(start, None)])
        seen = {start}
        while q:
            room, first = q.popleft()
            if room != start and any(self.doors[did].escape and not self.doors[did].wedged
                                     for did in self.rooms[room].doors):
                return first
            for did in self.rooms[room].doors:
                d = self.doors[did]
                nxt = d.other(room)
                if nxt in seen or nxt == self.team_room or not self.npc_can_use(d, nxt):
                    continue
                seen.add(nxt)
                q.append((nxt, first or (d, nxt)))
        return None

    def trigger_trap(self, d: Door) -> None:
        trap, d.trap = d.trap, None
        self.say(f"trap_{trap}", "fx")
        if trap == "flash":
            self.say("BANG! A flashbang rigged to the door goes off in your face!", "danger")
            self.disoriented = self.T.TRAP_FLASH_DISORIENT
        else:
            self.say("BOOM! The door was rigged with an explosive!", "danger")
            standing = [o for o in self.officers if not o.down]
            for o in self.rng.sample(standing, min(len(standing),
                                                   self.rng.randint(*self.T.TRAP_EXPLOSIVE_VICTIMS))):
                self.damage_officer(o, self.rng.randint(*self.T.TRAP_EXPLOSIVE_DAMAGE))
                if self.over:
                    return
        self.noise(self.team_room, None)

    def reveal_room(self, room_id: str, how: str) -> None:
        people = [n for n in self.room_npcs(room_id)]
        room = self.rooms[room_id]
        if not people:
            self.say(f"{how}: no one visible in the {room.name}.", "info")
            return
        self.say(f"{how}: {len(people)} in the {room.name}:", "info")
        for n in people:
            self.say("    " + self.npc_line(n), "info")

    # ------------------------------------------------------------------ door actions
    # Each _do_* returns (succeeded, took_time).
    def _closed_door(self, d: Door) -> bool:
        if d.kind != "door":
            self.say(f"The {d.name} is an open passage.", "warn")
            return False
        if d.state != "closed":
            self.say(f"The {d.name} is already open.", "warn")
            return False
        return True

    def _do_open(self, d: Door, quiet_check: bool = True) -> Tuple[bool, bool]:
        if not self._closed_door(d):
            return False, False
        if d.wedged:
            d.wedged = False
            self.say(f"You pull the wedge from the {d.name}.", "info")
        if d.locked:
            d.lock_known = True
            self.say(f"The {d.name} is locked. Pick it, kick it, or use C2.", "warn")
            return False, False
        if d.trap:
            self.trigger_trap(d)
            if self.over:
                return False, True
        d.state = "open"
        dest = d.other(self.team_room)
        if quiet_check:
            self.quiet_noise(dest)
        self.reveal_room(dest, f"The {d.name} swings open")
        return True, True

    def _do_pick(self, d: Door) -> Tuple[bool, bool]:
        if not self._closed_door(d):
            return False, False
        if not d.locked:
            d.lock_known = True
            self.say(f"The {d.name} isn't locked.", "info")
            return False, False
        self.say(f"Picking the lock on the {d.name}...", "info")
        for _ in range(self.T.PICK_TICKS - 1):
            self.tick()
            if self.over:
                return False, False
        d.locked = False
        d.lock_known = True
        self.quiet_noise(d.other(self.team_room))
        self.say("Lock picked.", "good")
        return True, True

    def _do_kick(self, d: Door) -> Tuple[bool, bool]:
        if not self._closed_door(d):
            return False, False
        d.wedged = False
        dest = d.other(self.team_room)
        self.noise(self.team_room, self.T.LOUD_RADIUS)
        if d.locked and self.rng.random() >= self.T.KICK_CHANCE:
            d.lock_known = True
            self.say("kick_fail", "fx")
            self.say(f"You kick the {d.name}. It holds!", "warn")
            return False, True
        if d.trap:
            self.trigger_trap(d)
            if self.over:
                return False, True
        d.state, d.locked = "broken", False
        self.say("kick", "fx")
        self.reveal_room(dest, f"The {d.name} slams open")
        return True, True

    def _do_c2(self, d: Door) -> Tuple[bool, bool]:
        if not self._closed_door(d):
            return False, False
        if self.inv["c2"] <= 0:
            self.say("You're out of C2.", "warn")
            return False, False
        self.inv["c2"] -= 1
        d.wedged = False
        dest = d.other(self.team_room)
        self.say("c2", "fx")
        self.say(f"Breaching charge set... BOOM! The {d.name} blows inward.", "alert")
        if d.trap:
            d.trap = None
            self.say("  The blast sets off a device rigged to the door. The team was stacked clear.", "good")
        d.state, d.locked = "broken", False
        for n in self.room_npcs(dest):
            if n.alive:
                self.stun(n, self.T.C2_STUN, self.T.GRENADES["flashbang"]["comply_bonus"])
                if n.state not in (RESTRAINED, INCAPACITATED) and self.rng.random() < self.T.C2_INJURE_CHANCE:
                    n.injured = True
                    if n.kind == "civilian":
                        self.penalize(f"Civilian injured by breach ({n.desc})", self.T.PENALTY_CIVILIAN_INJURED)
        self.noise(self.team_room, None)
        self.reveal_room(dest, "Through the smoke")
        return True, True

    def stun(self, n: NPC, ticks: int, bonus: float) -> None:
        # Aggressive suspects sometimes see it coming and cover up.
        if (n.kind == "suspect" and n.active
                and self.rng.random() < n.aggression * self.T.STUN_RESIST_CHANCE):
            return
        n.stunned = max(n.stunned, ticks)
        n.stun_bonus = max(n.stun_bonus, bonus)

    def apply_grenade(self, kind: str, room_id: str) -> None:
        g = self.T.GRENADES[kind]
        room = self.rooms[room_id]
        self.say(kind, "fx")
        self.say({"flashbang": f"BANG! Flashbang goes off in the {room.name}.",
                  "stinger": f"CRACK! Stinger rounds pepper the {room.name}.",
                  "gas": f"Hiss... CS gas fills the {room.name}."}[kind], "alert")
        for n in self.room_npcs(room_id):
            if not n.alive:
                continue
            self.stun(n, g["stun"], g["comply_bonus"])
            if n.state not in (RESTRAINED, INCAPACITATED) and self.rng.random() < g["injure"]:
                n.injured = True
                if n.kind == "civilian":
                    self.penalize(f"Civilian injured by stinger ({n.desc})", self.T.PENALTY_CIVILIAN_INJURED)
        if g["loud"]:
            self.noise(room_id, self.T.LOUD_RADIUS)

    def enter(self, dest: str, via: Door) -> None:
        self.team_room = dest
        room = self.rooms[dest]
        room.visited = True
        self.just_entered = True
        self.say(f"Team moves through the {via.name} into the {room.name}.", "info")
        self.cmd_look([])
        for n in self.room_npcs(dest):
            if (n.state == ALERT and n.kind == "suspect" and n.weapon and not n.stunned
                    and self.rng.random() < n.aggression * self.T.AMBUSH_CHANCE):
                self.say(f"Contact! {self.label(n)} was waiting for you!", "danger")
                self.go_hostile(n, immediate=True)

    # ------------------------------------------------------------------ commands
    def cmd_help(self, args) -> bool:
        self.say(HELP, "info")
        return False

    def cmd_look(self, args) -> bool:
        room = self.rooms[self.team_room]
        self.say(room.id, "scene")
        tag = "CLEARED" if room.cleared else ("exterior" if room.outdoor else "UNCLEARED")
        self.say(f"== {room.name} ({room.floor}) == [{tag}]", "title")
        self.say(room.desc, "info")
        self.say("Exits:", "dim")
        for i, (d, dest) in enumerate(self.exits(), 1):
            self.say(f"  [{i}] {d.name} -> {self.rooms[dest].name} ({self.door_status(d)})", "info")
        people = self.room_npcs(room.id)
        if people:
            self.say("People:", "dim")
            for n in people:
                style = "danger" if n.state == HOSTILE else "info"
                self.say("  " + self.npc_line(n), style)
        items = [i for i in self.items.values() if i.room == room.id and not i.collected]
        if items:
            self.say("Evidence: " + ", ".join(i.name for i in items), "good")
        return False

    def cmd_map(self, args) -> bool:
        floors: Dict[str, list] = {}
        for r in self.rooms.values():
            floors.setdefault(r.floor, []).append(r)
        for floor, rooms in floors.items():
            self.say(f"-- {floor} --", "title")
            for r in rooms:
                if r.id == self.team_room:
                    mark = "YOU ARE HERE"
                elif r.outdoor:
                    mark = ""
                elif r.cleared:
                    mark = "cleared"
                elif r.visited:
                    mark = "visited"
                else:
                    mark = "uncleared"
                links = ", ".join(self.rooms[self.doors[d].other(r.id)].name for d in r.doors)
                self.say(f"  {r.name:<15} {mark:<13} -> {links}", "info")
        return False

    def cmd_status(self, args) -> bool:
        self.say(f"Mission clock {self.clock}", "title")
        for o in self.officers:
            style = "danger" if o.down else ("warn" if o.hp < self.T.OFFICER_HP else "info")
            self.say(f"  {o.name:<11} {o.hp:>3} HP  {o.status}", style)
        self.say("  Gear: " + ", ".join(f"{k} x{v}" for k, v in self.inv.items())
                 + ", taser, zip-ties", "info")
        if self.disoriented:
            self.say("  The team is DISORIENTED.", "danger")
        return False

    def objective_progress(self) -> List[Tuple[str, int, int]]:
        sus = [n for n in self.npcs if n.kind == "suspect"]
        civ = [n for n in self.npcs if n.kind == "civilian"]
        ev = [i for i in self.items.values() if i.objective]
        return [
            ("Arrest or neutralize all suspects", sum(n.resolved for n in sus), len(sus)),
            ("Rescue all civilians", sum(n.state == RESTRAINED for n in civ), len(civ)),
            ("Secure evidence (" + ", ".join(i.name for i in ev) + ")",
             sum(i.collected for i in ev), len(ev)),
        ]

    def objectives_done(self) -> bool:
        return all(done == total for _, done, total in self.objective_progress())

    def cmd_objectives(self, args) -> bool:
        for text, done, total in self.objective_progress():
            mark = "[x]" if done == total else "[ ]"
            self.say(f"  {mark} {text}: {done}/{total}", "good" if done == total else "info")
        escaped = [n for n in self.npcs if n.state == ESCAPED]
        if escaped:
            self.say(f"  {len(escaped)} suspect(s) escaped the building.", "danger")
        unreported = [n for n in self.npcs if n.resolved and not n.reported]
        if unreported:
            self.say(f"  {len(unreported)} secured or neutralized but not yet reported to TOC.", "warn")
        return False

    def cmd_move(self, args) -> bool:
        d = self.resolve_door(args)
        if not d:
            return False
        if not d.passable:
            self.say(f"The {d.name} is closed. Open, pick, kick, or C2 it first, or use 'breach'.", "warn")
            return False
        self.enter(d.other(self.team_room), d)
        return True

    def cmd_mirror(self, args) -> bool:
        d = self.resolve_door(args)
        if not d:
            return False
        dest = d.other(self.team_room)
        if d.passable:
            self.reveal_room(dest, f"You peek through the {d.name}")
            return True
        self.say(f"You slide the mirror gun under the {d.name}.", "info")
        self.say(dest, "mirror")
        if d.trap:
            d.trap_known = True
            self.say(f"  There's {'a flashbang' if d.trap == 'flash' else 'an explosive'} "
                     "rigged to the door! 'disarm' it or use C2.", "danger")
        else:
            self.say("  No traps on the door.", "good")
        self.reveal_room(dest, "  Under the door")
        for n in self.room_npcs(dest):
            if (n.state == ALERT and n.kind == "suspect" and n.weapon_visible and not n.stunned
                    and self.rng.random() < n.aggression * self.T.MIRROR_SPOTTED_CHANCE):
                self.say(f"{self.label(n)} spots the mirror and fires through the door!", "danger")
                target = self.pick_target()
                w = self.T.WEAPONS[n.weapon]
                if self.rng.random() < (w["accuracy"] * self.T.SUSPECT_ACCURACY_MULT
                                         * self.T.THROUGH_DOOR_ACCURACY):
                    self.damage_officer(target, self.rng.randint(*w["damage"]))
                else:
                    self.say("  Splinters fly. Nobody's hit.", "warn")
                self.noise(dest, None)
                break
        return True

    def cmd_open(self, args) -> bool:
        d = self.resolve_door(args)
        return bool(d) and self._do_open(d)[1]

    def cmd_close(self, args) -> bool:
        d = self.resolve_door(args)
        if not d:
            return False
        if d.kind != "door" or d.state != "open":
            self.say(f"You can't close the {d.name}.", "warn")
            return False
        d.state = "closed"
        self.say(f"You close the {d.name}.", "info")
        return True

    def cmd_pick(self, args) -> bool:
        d = self.resolve_door(args)
        return bool(d) and self._do_pick(d)[1]

    def cmd_kick(self, args) -> bool:
        d = self.resolve_door(args)
        return bool(d) and self._do_kick(d)[1]

    def cmd_c2(self, args) -> bool:
        d = self.resolve_door(args)
        return bool(d) and self._do_c2(d)[1]

    def cmd_wedge(self, args) -> bool:
        d = self.resolve_door(args)
        if not d or not self._closed_door(d):
            return False
        if d.wedged:
            self.say("It's already wedged.", "warn")
            return False
        if self.inv["wedge"] <= 0:
            self.say("You're out of door wedges.", "warn")
            return False
        self.inv["wedge"] -= 1
        d.wedged = True
        self.say(f"You wedge the {d.name}. No one's getting through it.", "good")
        return True

    def cmd_disarm(self, args) -> bool:
        d = self.resolve_door(args)
        if not d:
            return False
        if not (d.trap and d.trap_known):
            self.say("You haven't spotted a trap on that door. Mirror it first.", "warn")
            return False
        if self.rng.random() < self.T.DISARM_FAIL_CHANCE:
            self.say("You cut the wrong wire...", "danger")
            self.trigger_trap(d)
            return True
        d.trap = None
        self.say(f"You cut the wire. The trap on the {d.name} is disarmed.", "good")
        return True

    def cmd_throw(self, args) -> bool:
        if not args or args[0] not in GRENADE_ALIASES:
            self.say("Throw what? flash, stinger, or gas. e.g. 'throw flash 2'", "warn")
            return False
        kind = GRENADE_ALIASES[args[0]]
        d = self.resolve_door(args[1:])
        if not d:
            return False
        if not d.passable:
            self.say(f"The {d.name} is closed. Open it first.", "warn")
            return False
        if self.inv[kind] <= 0:
            self.say(f"You're out of {kind}s.", "warn")
            return False
        self.inv[kind] -= 1
        self.apply_grenade(kind, d.other(self.team_room))
        return True

    def cmd_breach(self, args) -> bool:
        method = grenade = None
        rest = []
        for a in args:
            if a in BREACH_METHODS and method is None:
                method = BREACH_METHODS[a]
            elif a in GRENADE_ALIASES and grenade is None:
                grenade = GRENADE_ALIASES[a]
            else:
                rest.append(a)
        d = self.resolve_door(rest)
        if not d:
            return False
        if grenade and self.inv[grenade] <= 0:
            self.say(f"You're out of {grenade}s.", "warn")
            return False
        if not d.passable:
            explicit = method is not None
            method = method or ("kick" if d.locked and d.lock_known else "open")
            if method == "open" and d.locked and not explicit:
                d.lock_known = True
                self.say(f"The {d.name} is locked. Kicking it!", "warn")
                method = "kick"
            if method == "pick":
                ok, took = self._do_pick(d)
                if ok:
                    self.tick()
                    if self.over:
                        return False
                    ok, took = self._do_open(d, quiet_check=False)
                    took = False  # opening is part of the entry action
            else:
                ok, took = {"open": self._do_open, "kick": self._do_kick,
                            "c2": self._do_c2}[method](d)
                if ok:
                    self.tick()
                    took = False
            if not ok or self.over:
                return took
        if grenade:
            self.inv[grenade] -= 1
            self.apply_grenade(grenade, d.other(self.team_room))
        self.enter(d.other(self.team_room), d)
        return True

    def comply_chance(self, n: NPC) -> float:
        p = 1 - n.resistance
        if n.kind == "suspect":
            p -= self.T.SUSPECT_RESISTANCE_BONUS
        if n.stunned:
            p += n.stun_bonus
        if n.state == UNAWARE:
            p += self.T.SURPRISE_BONUS
        if n.state == HOSTILE:
            p -= self.T.HOSTILE_PENALTY
        if n.injured:
            p += self.T.INJURED_BONUS
        p += min(n.yells, self.T.MAX_YELL_STACK) * self.T.YELL_STACK_BONUS
        if n.kind == "suspect":
            p += self.suspects_down() * self.T.MORALE_PER_DOWN
        if self.disoriented:
            p -= self.T.DISORIENTED_PENALTY
        return max(0.02, min(0.98, p))

    def surrender(self, n: NPC) -> None:
        n.state = SURRENDERED
        self.say(f"{self.label(n)} gets down, hands up.", "good")
        if not n.concealed:
            self.drop_weapon(n)

    def cmd_yell(self, args) -> bool:
        focus = None
        if args:
            focus = self.resolve_npc(args)
            if not focus:
                return False
            if not focus.active:
                self.say(f"{self.label(focus)} is already under control.", "dim")
                return False
        self.say('"POLICE! SEARCH WARRANT! GET ON THE GROUND! SHOW ME YOUR HANDS!"', "alert")
        targets = [focus] if focus else [n for n in self.room_npcs(self.team_room) if n.active]
        if not targets:
            anyone = any(n.alive for n in self.room_npcs(self.team_room))
            self.say("Everyone here is complying." if anyone else "No one here.", "dim")
            return True
        for n in targets:
            p = self.comply_chance(n) + (self.T.FOCUSED_YELL_BONUS if focus else 0)
            n.yells += 1
            if self.rng.random() < p:
                self.surrender(n)
                continue
            if n.stunned:
                self.say(f"{self.label(n)} is staggering and doesn't respond.", "warn")
            elif n.kind == "civilian":
                if self.rng.random() < self.T.CIV_FLEE_CHANCE and self.npc_move(n, allow_team_room=False):
                    pass
                else:
                    self.say(f"{self.label(n)} panics and won't get down.", "warn")
                if n.state == UNAWARE:
                    n.state = ALERT
            else:
                r = self.rng.random()
                if n.weapon and r < n.aggression and n.state != HOSTILE:
                    self.go_hostile(n)
                elif (r < n.aggression + (1 - n.aggression) * self.T.SUSPECT_FLEE_CHANCE
                      and self.npc_move(n, allow_team_room=False)):
                    pass
                else:
                    self.say(f"{self.label(n)} ignores you.", "warn")
                if n.state == UNAWARE:
                    n.state = ALERT
        return True

    def cmd_shoot(self, args) -> bool:
        n = self.resolve_npc(args)
        if not n:
            return False
        if not n.alive:
            self.say("They're already dead.", "warn")
            return False
        authorized = self.deadly_authorized(n)
        acc = self.T.PLAYER_ACCURACY * (self.T.DISORIENTED_ACCURACY if self.disoriented else 1)
        self.say("gunfire", "fx")
        self.say(f"You fire on {self.label(n)}.", "alert")
        self.noise(self.team_room, None)
        if self.rng.random() >= acc:
            self.say("  Miss!", "warn")
            return True
        was_civ = n.kind == "civilian"
        self.neutralize(n, by="player")
        if not authorized:
            self.penalize(f"Unauthorized use of deadly force ({n.desc})", self.T.PENALTY_UNAUTHORIZED_DEADLY)
        if n.minor:
            self.penalize(f"Deadly force on a juvenile ({n.desc})", self.T.PENALTY_DEADLY_JUVENILE)
        if was_civ and n.state == DEAD:
            self.penalize(f"Civilian killed ({n.desc})", self.T.PENALTY_CIVILIAN_KILLED)
        return True

    def cmd_taser(self, args) -> bool:
        n = self.resolve_npc(args)
        if not n:
            return False
        if not n.alive:
            self.say("They're dead.", "warn")
            return False
        authorized = n.active
        self.say(f"You fire the taser at {self.label(n)}.", "alert")
        if self.rng.random() >= self.T.TASER_ACCURACY:
            self.say("  The probes miss.", "warn")
            return True
        if not authorized:
            self.penalize(f"Unauthorized use of force ({n.desc})", self.T.PENALTY_UNAUTHORIZED_FORCE)
        if n.state in (RESTRAINED, INCAPACITATED):
            self.say("  They twitch on the floor.", "info")
            return True
        n.state = SURRENDERED
        n.stunned = max(n.stunned, self.T.TASER_STUN)
        self.say(f"  {self.label(n)} locks up and drops.", "good")
        self.drop_weapon(n)
        return True

    def cmd_restrain(self, args) -> bool:
        n = self.resolve_npc(args)
        if not n:
            return False
        if n.state == RESTRAINED:
            self.say("They're already restrained.", "warn")
            return False
        if n.state == DEAD:
            self.say("They're dead. Report them instead.", "warn")
            return False
        if n.active:
            self.say(f"{self.label(n)} isn't complying. Yell, use less-lethal, or take cover.", "warn")
            return False
        n.state = RESTRAINED
        n.identified = True
        how = "cut loose, zip-tied and searched" if n.bound else "restrained and searched"
        self.say(f"{self.label(n)} {how}.", "good")
        if n.weapon:
            self.drop_weapon(n, found=True)
        return True

    def cmd_report(self, args) -> bool:
        here = self.room_npcs(self.team_room)
        if args and args[0] != "all":
            n = self.resolve_npc(args)
            targets = [n] if n else []
            if not targets:
                return False
        else:
            targets = [n for n in here if n.resolved and not n.reported]
            if not targets:
                self.say("Nothing new to report here.", "dim")
        for n in targets:
            if n.reported:
                self.say(f"{self.label(n)} was already reported.", "dim")
            elif not n.resolved:
                self.say(f"Restrain {self.label(n)} before reporting them.", "warn")
            else:
                what = "neutralized" if n.state == DEAD else "restrained"
                n.reported = True
                self.say(f'"TOC, {n.kind} {what}." TOC: "Copy, {n.kind} {what}."', "radio")
        elsewhere = sorted({self.rooms[n.room].name for n in self.npcs
                            if n.resolved and not n.reported})
        if elsewhere:
            self.say("Still unreported (you have to be with them): " + ", ".join(elsewhere) + ".",
                     "warn")
        return False

    def cmd_collect(self, args) -> bool:
        items = [i for i in self.items.values() if i.room == self.team_room and not i.collected]
        if not items:
            self.say("No evidence here.", "dim")
            return False
        for i in items:
            i.collected = True
            self.say(f"Secured: {i.name}.", "good")
        return True

    def cmd_wait(self, args) -> bool:
        self.say("The team holds position.", "dim")
        return True

    # ------------------------------------------------------------------ end
    def check_objectives(self) -> None:
        if not self.objectives_announced and self.objectives_done():
            self.objectives_announced = True
            self.say('TOC: "Element, all objectives complete. Finish reporting and '
                     "type 'end' when you're ready.\"", "radio")

    def end_mission(self, kia: bool = False) -> None:
        self.over = True
        if kia:
            self.outcome = "kia"
            self.say('TOC: "Officer down! Element lead is down! Mission failed."', "danger")
        else:
            self.outcome = "complete" if self.objectives_done() else "incomplete"
