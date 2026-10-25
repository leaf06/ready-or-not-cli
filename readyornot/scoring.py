"""After-action scoring, loosely modelled on Ready or Not's debrief."""
from __future__ import annotations

from typing import List, Tuple

from .engine import Game
from .model import DEAD, RESTRAINED


def grade_for(score: int, grades) -> str:
    for threshold, letter in grades:
        if score >= threshold:
            return letter
    return "F"


def score(game: Game) -> dict:
    T = game.T
    sus = [n for n in game.npcs if n.kind == "suspect"]
    rows: List[Tuple[str, int, int]] = []

    progress = game.objective_progress()
    per = T.SCORE_OBJECTIVES / len(progress)
    obj = sum(per * (done / total if total else 1) for _, done, total in progress)
    # Team health and conduct are only worth what you actually accomplished,
    # so walking away at the front door doesn't bank free points.
    done_frac = obj / T.SCORE_OBJECTIVES
    rows.append(("Mission objectives", round(obj), T.SCORE_OBJECTIVES))

    arrested = sum(n.state == RESTRAINED for n in sus)
    rows.append((f"Suspects arrested ({arrested}/{len(sus)})",
                 round(T.SCORE_ARRESTS * arrested / len(sus)) if sus else T.SCORE_ARRESTS,
                 T.SCORE_ARRESTS))

    reportable = [n for n in game.npcs if n.resolved]
    reported = sum(n.reported for n in reportable)
    rows.append((f"Reports to TOC ({reported}/{len(reportable)})",
                 round(T.SCORE_REPORTS * reported / len(reportable)) if reportable else 0,
                 T.SCORE_REPORTS))

    items = list(game.items.values())
    bagged = sum(i.collected for i in items)
    rows.append((f"Evidence secured ({bagged}/{len(items)})",
                 round(T.SCORE_EVIDENCE * bagged / len(items)) if items else T.SCORE_EVIDENCE,
                 T.SCORE_EVIDENCE))

    hurt = sum(1 for o in game.officers if 0 < o.hp < o.max_hp)
    down = sum(1 for o in game.officers if o.down)
    team = max(0, T.SCORE_TEAM - hurt * T.TEAM_INJURED_COST - down * T.TEAM_DOWN_COST)
    team = round(team * done_frac)
    rows.append((f"Team health ({hurt} injured, {down} down)", team, T.SCORE_TEAM))

    clean = not game.penalties
    rows.append(("No ROE violations" if clean else "ROE violations",
                 round(T.SCORE_CONDUCT * done_frac) if clean else 0, T.SCORE_CONDUCT))

    penalty_total = sum(p for _, p in game.penalties)
    total = max(0, min(100, sum(r[1] for r in rows) - penalty_total))
    if game.outcome == "kia":
        total = 0
    return {
        "rows": rows,
        "penalties": game.penalties,
        "total": total,
        "grade": "F" if game.outcome == "kia" else grade_for(total, T.GRADES),
        "suspects_arrested": arrested,
        "suspects_killed": sum(n.state == DEAD for n in sus),
        "civilians_rescued": sum(n.state == RESTRAINED for n in game.npcs if n.kind == "civilian"),
        "civilians_dead": sum(n.state == DEAD for n in game.npcs if n.kind == "civilian"),
    }
