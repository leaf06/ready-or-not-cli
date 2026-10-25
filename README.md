# Ready or Not: Terminal Tactical (v0.1)

A turn-based, text-command SWAT game for the macOS Terminal, inspired by
*Ready or Not*. You lead a five-officer element through a high-risk warrant.
You mirror doors, breach, throw flashbangs, order suspects and civilians to
comply, follow the rules of engagement, and get graded on how cleanly you did it.

v0.1 ships one scenario, **4180 Larkspur Lane**, so the mechanics can be tuned
before more content is added.

## Run it

It needs only Python 3.9 or newer, with no packages to install. On macOS,
`python3` is available once the Xcode Command Line Tools are installed
(`xcode-select --install`).

```sh
git clone <this repo> && cd ready-or-not-cli
./ron                      # or: python3 -m readyornot
./ron --seed 42            # repeatable run (useful when tuning)
./ron --scenario larkspur_lane --no-color
```

## How a turn works

Every command you type is one action. After the action resolves, the house
reacts. Hostile suspects in your room fire, others notice you or raise
weapons, suspects elsewhere move around, and stun timers count down. Info
commands (`look`, `map`, `status`, `objectives`, `help`, `report`) take no time.

| Command | What it does |
|---|---|
| `look` / `map` | Your room, exits and people / the floor plan with cleared rooms |
| `mirror <exit>` | Check under a door for people and traps |
| `open` / `pick` / `kick` / `c2 <exit>` | Quiet / quiet but 2 turns / loud, may fail / loud, stuns the room, sets off traps safely |
| `throw flash\|stinger\|gas <exit>` | Grenade through an open door |
| `breach <exit> [open\|pick\|kick\|c2] [flash\|stinger\|gas]` | Breach, throw and enter in one go |
| `move <exit>` | Go through an open door |
| `wedge` / `disarm <exit>` | Seal a door against suspects / cut a trap you've spotted |
| `yell` | Order everyone in the room to comply |
| `restrain <x>` · `report [x\|all]` · `collect` | Cuff, report to TOC, bag evidence |
| `shoot <x>` · `taser <x>` | Deadly force / less-lethal |
| `end` | Finish the mission and get your debrief |

An `<exit>` is its number from `look` or part of its name (`kitchen`, `front`).
People are targeted by their letter (`restrain b`).

**ROE:** deadly force is authorized only against a suspect who is *visibly
armed and not surrendering*. "Hands not visible" is not a weapon. Shooting an
unarmed suspect or a civilian costs heavily, and so does tasing someone who
already complied.

### Mechanics worth knowing
- **Noise.** Kicks and flashbangs alert anyone within two rooms. C2 and gunfire alert the whole house. Alerted suspects roam and may walk into your room with a weapon up.
- **Stuns.** Stunned people can't shoot and are much more likely to comply. Flashbangs last 3 turns, stingers 2 (and can injure), gas 4.
- **Warning beat.** A suspect who raises a weapon usually gives you one action to respond. Aggressive ones may draw and fire at once, especially when you yell at them unstunned.
- **Fake surrenders.** A suspect with a hidden weapon keeps it when they put their hands up. Cuff them fast. Anyone you leave uncuffed in another room may stop complying and grab their weapon again.
- **Traps.** Some doors are rigged with flashbangs or explosives. Mirror the door, then `disarm` it, or C2 it.
- **Crits.** About one hit in five finds a gap in the armor. Walking into an unscouted room can kill you.

### Scoring (100 points)
Objectives 35 · Arrests (not kills) 20 · Reports 10 · Evidence 10 · Team
health 15 · No ROE violations 10, minus penalties. Team health and conduct are
scaled by how much of the mission you completed. Grades run S / A / B / C / D / F.
Dying is an automatic F.

## Tuning

Every balance number (accuracy, comply chances, stun lengths, AI odds,
loadouts, scoring weights) lives in [`readyornot/tuning.py`](readyornot/tuning.py).
To measure a change, run the simulator, which plays the scenario hundreds of
times with a careful bot and a reckless bot:

```sh
python3 tools/simulate.py -n 1000
```

Baseline on the current numbers:

| Bot | Completes | KIA | Avg score | Mostly |
|---|---|---|---|---|
| tactical (mirror, disarm, flash every room) | 99% | 1% | 94.6 | S |
| reckless (kick and walk in) | 90% | 10% | 74.7 | B / C |

## Adding scenarios

Drop a new JSON file in `readyornot/scenarios/` and it appears in the menu.
Use [`larkspur_lane.json`](readyornot/scenarios/larkspur_lane.json) as the
template:

- **rooms**: an `entry: true` room is a starting point, and `outdoor` rooms are off-limits to suspects
- **doors**: `kind` is `door` or `opening`, plus optional `locked` and `trap` (`flash` / `explosive`)
- **npcs**: `kind` is `suspect` or `civilian`. Also set `weapon`, `concealed`, `resistance` (how hard they are to make comply), `aggression` (how likely they fight), and a starting `state` (`unaware` or `alert`)
- **evidence**: objective items to collect

## Development

```sh
python3 -m unittest          # rules, ROE, doors, scoring, plus a fuzz test
```

The engine (`engine.py`) never prints. It queues messages that the CLI
(`cli.py`) renders, which keeps the rules testable.
