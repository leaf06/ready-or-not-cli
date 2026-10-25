# Ready or Not: Terminal Tactical (v0.1.3)

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
./ron --scenario larkspur_lane --difficulty hard --no-color
./ron --no-art             # text only
```

## ASCII art

Every room has a hand-drawn scene, shown whenever you enter or `look`. Door
labels like `[2]` match the exit numbers you type. Below the scene, each
person is drawn by their current state, with their letter underneath:

```
  * * *                                  <- stunned
   O        \O/       O  __     O
  /|\_       |       /|--'     (|)       _x__/_
  / \       / \      / \       _/\_
 [A]      [B]      [C]      [D]      [E]
 ARMED    hands up AIMING   cuffed   dead
```

Flashbangs, C2, kicks, gunfire and traps get their own effects, and `mirror`
shows the feet under the door. Type `art off` / `art on` mid-game (free), or
start with `--no-art`. Everything stays under 58 columns so it fits a phone.

## Difficulty

You pick a difficulty before each mission. Scores are graded on the same
scale at every level, so an S on Hard means more than an S on Easy.

| | Easy | Medium | Hard |
|---|---|---|---|
| Intel and utility | Risk-free: mirrors are never spotted, disarms never fail, every grenade stuns | Mirrors can draw blind fire, 1 disarm in 10 fails, aggressive suspects sometimes cover up | Mirrors spotted more often, 15% of disarms fail, suspects cover up more |
| Gear (Standard kit) | 3 flash, 2 stinger, 1 gas, 2 C2, 3 wedges | 2 flash, 1 stinger, 1 gas, 2 C2, 2 wedges | 2 flash, 1 stinger, 1 C2, 1 wedge |
| Suspects | Slower to draw, roam less | Quick-draw and flank more often | 15% more accurate, harder to make comply, fake surrenders more, ambush almost every time |
| Your team | 1 in 5 hits is a crit, squad returns fire reliably | 1 in 4 crits, you draw fire as point man | Thinner armor, 30% crits, weaker return fire |

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
| `yell [x]` | Order everyone in the room to comply, or single one person out (slightly more effective) |
| `restrain <x>` · `report [x\|all]` · `collect` | Cuff, report to TOC (you must be in the same room), bag evidence |
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
- **Traps.** Some doors are rigged with flashbangs or explosives. Mirror the door, then `disarm` it, or C2 it. On Medium and Hard, disarming can fail.
- **Mirroring isn't free** (Medium and Hard). An alert, armed suspect may spot the mirror and fire blind through the door.
- **Covering up** (Medium and Hard). Aggressive suspects sometimes see a grenade coming and aren't stunned. Check for `stunned` before you trust it.
- **Point man.** On the turn you come through a door, you're the one most likely to be shot at.
- **Crits.** Some hits find a gap in the armor and ignore it. Walking into an unscouted room can kill you.
- **Scarce kit.** On Medium and Hard, loadouts carry fewer grenades than there are rooms, so decide where they count.

### Scoring (100 points)
Objectives 35 · Arrests (not kills) 20 · Reports 10 · Evidence 10 · Team
health 15 · No ROE violations 10, minus penalties. Team health and conduct are
scaled by how much of the mission you completed. Grades run S / A / B / C / D / F.
Dying is an automatic F.

## Tuning

Every balance number (accuracy, comply chances, stun lengths, AI odds,
loadouts, scoring weights) lives in [`readyornot/tuning.py`](readyornot/tuning.py).
The values at the top of the file are Medium. `DIFFICULTIES` at the bottom
lists only what Easy and Hard change. To measure a change, run the simulator,
which plays the scenario hundreds of times per difficulty with a careful bot
and a reckless bot:

```sh
python3 tools/simulate.py -n 1000                 # all difficulties
python3 tools/simulate.py -n 1000 --difficulty hard
```

Baseline on the current numbers (1,000 runs each):

| Difficulty | Tactical bot: KIA / S rank / avg | Reckless bot: KIA / avg |
|---|---|---|
| Easy | 1% / 69% / 94.7 | 11% / 74.3 |
| Medium | 7% / 37% / 85.3 | 21% / 65.8 |
| Hard | 15% / 21% / 76.3 | 35% / 53.8 |

The tactical bot plays close to perfectly, so expect human scores to be lower.

## Adding scenarios

Drop a new JSON file in `readyornot/scenarios/` and it appears in the menu.
Use [`larkspur_lane.json`](readyornot/scenarios/larkspur_lane.json) as the
template:

- **rooms**: an `entry: true` room is a starting point, and `outdoor` rooms are off-limits to suspects
- **doors**: `kind` is `door` or `opening`, plus optional `locked` and `trap` (`flash` / `explosive`)
- **npcs**: `kind` is `suspect` or `civilian`. Also set `weapon`, `concealed`, `resistance` (how hard they are to make comply), `aggression` (how likely they fight), and a starting `state` (`unaware` or `alert`)
- **evidence**: objective items to collect
- **art** (optional): a `<scenario_id>.art` file beside the JSON, with one `== room_id ==` block per room. Lines stay under 58 columns.

## Development

```sh
python3 -m unittest          # rules, ROE, doors, scoring, difficulty, plus fuzz tests
```

The engine (`engine.py`) never prints. It queues messages that the CLI
(`cli.py`) renders, which keeps the rules testable.
