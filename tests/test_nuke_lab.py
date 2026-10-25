import random
import unittest

from readyornot.engine import Game
from readyornot.model import ALERT, ESCAPED, RESTRAINED, SURRENDERED
from readyornot.scenario import load_scenario
from readyornot.scoring import score
from tests.test_engine import FuzzTests, Rigged


def nuke_game(entry="street", roll=None, seed=0, difficulty="medium"):
    rng = Rigged(roll) if roll is not None else None
    return Game(load_scenario("nuke_lab"), "standard", entry, seed=seed, rng=rng,
                difficulty=difficulty)


def npc(game, npc_id):
    return next(n for n in game.npcs if n.id == npc_id)


class JuvenileTests(unittest.TestCase):
    def test_deadly_force_on_armed_juvenile_is_never_authorized(self):
        g = nuke_game(roll=0.0)
        g.team_room = "breakroom"
        hob = npc(g, "hob")
        g.go_hostile(hob)  # weapon up and pointed at the team
        self.assertFalse(g.deadly_authorized(hob))
        g.execute("shoot " + hob.tag)
        reasons = [p for p, _ in g.penalties]
        self.assertTrue(any("deadly force" in p.lower() for p in reasons))
        self.assertTrue(any("juvenile" in p for p in reasons))

    def test_taser_on_armed_juvenile_is_fine(self):
        g = nuke_game(roll=0.0)
        g.team_room = "breakroom"
        hob = npc(g, "hob")
        hob.state = ALERT
        g.execute("taser " + hob.tag)
        self.assertEqual(g.penalties, [])
        self.assertEqual(hob.state, SURRENDERED)

    def test_juvenile_is_marked(self):
        g = nuke_game()
        self.assertIn("JUVENILE", g.npc_line(npc(g, "hob")))


class EscapeTests(unittest.TestCase):
    def test_runner_at_the_dock_escapes(self):
        g = nuke_game(roll=0.0)  # every escape roll succeeds
        hob = npc(g, "hob")
        hob.room, hob.state = "dock", ALERT
        g.execute("wait")
        self.assertEqual(hob.state, ESCAPED)
        self.assertTrue(any("fled" in t for _, t in g.drain()))

    def test_wedged_dock_door_stops_the_escape(self):
        g = nuke_game(entry="alley", roll=0.0)
        g.execute("wedge 1")
        g.team_room = "street"  # walk away; the wedge stays
        hob = npc(g, "hob")
        hob.room, hob.state = "dock", ALERT
        for _ in range(5):
            g.execute("wait")
        self.assertNotEqual(hob.state, ESCAPED)

    def test_team_outside_the_door_blocks_it(self):
        g = nuke_game(entry="alley", roll=0.0)
        hob = npc(g, "hob")
        hob.room, hob.state = "dock", ALERT
        g.execute("wait")
        self.assertNotEqual(hob.state, ESCAPED)

    def test_runners_head_for_the_exit(self):
        g = nuke_game(roll=0.0)
        cain = npc(g, "cain")
        cain.state = ALERT
        g.execute("wait")      # office -> catwalk
        g.execute("wait")      # catwalk -> dock
        g.execute("wait")      # out the door
        self.assertEqual(cain.state, ESCAPED)

    def test_escaped_suspect_fails_the_objective(self):
        g = nuke_game()
        for n in g.npcs:
            n.state, n.reported = RESTRAINED, True
        npc(g, "cain").state = ESCAPED
        for i in g.items.values():
            i.collected = True
        g.end_mission()
        result = score(g)
        self.assertEqual(g.outcome, "incomplete")
        self.assertEqual(result["suspects_escaped"], 1)
        self.assertLess(result["total"], 100)


class NukeLabPlaythroughTests(unittest.TestCase):
    def test_random_play_never_crashes(self):
        cmds = FuzzTests.COMMANDS + ["move 4", "breach 4 flash", "wedge 1", "taser i", "yell i"]
        for difficulty in ("easy", "medium", "hard"):
            for seed in range(40):
                rng = random.Random(seed)
                g = nuke_game(entry=rng.choice(["street", "alley"]), seed=seed,
                              difficulty=difficulty)
                for _ in range(120):
                    if g.over:
                        break
                    g.execute(rng.choice(cmds))
                    g.drain()
                g.end_mission()
                score(g)


if __name__ == "__main__":
    unittest.main()
