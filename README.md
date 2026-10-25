# Ready or Not: Terminal Tactical (v0.4.0)

A turn-based, text-command SWAT game for the macOS Terminal, inspired by
*Ready or Not*. You lead a five-officer element through a high-risk warrant.
You mirror doors, breach, throw flashbangs, order suspects and civilians to
comply, follow the rules of engagement, and get graded on how cleanly you did it.

Four scenarios so far:

- **4180 Larkspur Lane** (Moderate): a narcotics warrant on a house with a basement drug lab.
- **Delta Bottling Co.** (Hard): a raid on a Nuke packaging plant, an homage to the Nuke lab
  raid in *RoboCop 2*. Cain, Angie and the juvenile Hob will run for the loading dock the
  moment things get loud, and you can't use deadly force on Hob even when he's shooting at
  you. Plan the dock before you plan the breach.
- **M/Y Biscayne Lady** (Hard): a money-laundering bust on a drug kingpin's yacht at a Miami
  Beach marina, an homage to the *Miami Vice* episode "Payback" (season 2, 1986), where Fuente
  runs every deal from his boat so the money can go over the side at the first sign of trouble.
  The yacht is getting ready to leave: take the bridge before the captain casts off, stun the
  salon before the cash goes overboard, and hold the stern so Fuente can't reach the tender.
- **Nakatomi Plaza** (Very Hard): a Christmas Eve hostage rescue, an homage to *Die Hard*.
  Hans's crew has taken the 30th floor party, and Theo is cracking the vault's seven locks.
  Stop Theo before the last one opens. Hans may pose as a hostage, and the barefoot man with
  the submachine gun is a friendly. Fast-rope onto the roof or come in from the plaza (and
  think about the garage gate before you do).

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

Every room has a hand-drawn scene, shown whenever you enter or `look`. In an
80-column terminal you get a detailed first-person view through the doorway:
back wall, side walls and floor in perspective, with the people in the room
standing on the floor. On narrower screens (like a phone) the game switches
to compact scenes, with people in a strip underneath. Door labels like `[2]`
match the exit numbers you type, and exits behind you are labeled along the
ceiling. Each person is drawn by their current state, with their letter
underneath:

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
start with `--no-art`.

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
- **Runners** (Delta Bottling Co.). Some suspects head for an escape door once alerted. If they get out, they're gone and the objective fails. A wedged door, or the team standing outside it, stops them.
- **Departure clock** (Biscayne Lady). The captain is prepping to leave and will cast off after a set number of turns, much sooner once he's alerted. If the yacht leaves, the mission fails. A captain who's out of action, or off the helm, stops the clock. `status` shows the time left, and TOC calls it out.
- **Dumping evidence** (Biscayne Lady). Some suspects destroy evidence once alerted and you're in the room with them. A stunned dumper can't.
- **Armed civilians** (Nakatomi Plaza). A visible weapon usually marks a suspect, but an armed civilian shows as "Unknown" until you secure them. Read the briefing: shooting a friendly is unauthorized deadly force.
- **Juveniles** (Delta Bottling Co.). Deadly force on a juvenile is never authorized, even if they're shooting at you. Tase them or talk them down. Their figures read `KID+GUN` / `KID AIMS`.
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
Pass `--scenario nuke_lab` to simulate Delta Bottling Co. The bots don't plan
for runners, so they rarely complete it. Wedging the dock first (from the
alley) is what makes it winnable. The same goes for `--scenario biscayne_lady`:
the bots ignore the bridge, so the yacht usually leaves. Taking the bridge,
then the salon, then holding the swim platform completes it in about 63% of
Medium runs. For `--scenario nakatomi`, wedging the garage gate from the plaza
and then going straight for Theo completes about 83% of Medium runs.

## Adding scenarios

Drop a new JSON file in `readyornot/scenarios/` and it appears in the menu.
Use [`larkspur_lane.json`](readyornot/scenarios/larkspur_lane.json) as the
template:

- **rooms**: an `entry: true` room is a starting point, and `outdoor` rooms are off-limits to suspects
- **doors**: `kind` is `door` or `opening`, plus optional `locked` and `trap` (`flash` / `explosive`)
- **doors**: also optional `escape: true` for a door runners can flee through
- **departure** (optional): `{"ticks": 45, "pilot": "<npc id>", "alert_rate": 3, ...}` gives the scenario a clock that runs while the pilot is free at their starting room; see `biscayne_lady.json` (a yacht leaving) and `nakatomi.json` (a vault opening)
- **banners** / **headlines** (optional): per-outcome debrief art and titles, keyed by `complete`, `incomplete`, `departed` or `kia`
- **npcs**: `kind` is `suspect` or `civilian`. Also set `weapon` (`pistol`, `shotgun`, `rifle`, `smg`, `knife`), `concealed`, `resistance` (how hard they are to make comply), `aggression` (how likely they fight), and a starting `state` (`unaware`, `alert`, or `surrendered` with `bound: true` for someone tied up). `escapes: true` makes them run for an escape door, `dumps: true` makes them destroy evidence, and `minor: true` makes deadly force against them unauthorized.
- **evidence**: objective items to collect
- **art** (optional): `<scenario_id>.art` holds the detailed scenes (up to 78 columns, with the last 6 rows kept clear as the floor where people stand), and `<scenario_id>.compact.art` holds the phone-sized ones (up to 58 columns). Each has one `== room_id ==` block per room. The tests check the widths, the clear floor and the exit labels.

## Development

```sh
python3 -m unittest          # rules, ROE, doors, scoring, difficulty, plus fuzz tests
```

The engine (`engine.py`) never prints. It queues messages that the CLI
(`cli.py`) renders, which keeps the rules testable.
