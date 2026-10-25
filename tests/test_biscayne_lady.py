import random
import unittest

from readyornot.engine import Game
from readyornot.model import ALERT, ESCAPED, RESTRAINED, SURRENDERED
from readyornot.scenario import load_scenario
from readyornot.scoring import score
from tests.test_engine import FuzzTests, Rigged


def yacht(entry="pier", roll=None, seed=0, difficulty="medium"):
    rng = Rigged(roll) if roll is not None else None
    return Game(load_scenario("biscayne_lady"), "standard", entry, seed=seed, rng=rng,
                difficulty=difficulty)


def npc(game, npc_id):
    return next(n for n in game.npcs if n.id == npc_id)


class DepartureTests(unittest.TestCase):
    def test_clock_scales_with_difficulty(self):
        self.assertGreater(yacht(difficulty="easy").departure, yacht().departure)
        self.assertLess(yacht(difficulty="hard").departure, yacht().departure)

    def test_yacht_leaves_when_the_clock_runs_out(self):
        g = yacht(roll=0.99)  # nothing else happens
        while not g.over:
            g.execute("wait")
        self.assertEqual(g.outcome, "departed")
        self.assertTrue(all(n.state == ESCAPED for n in g.npcs
                            if n.kind == "suspect"))
        self.assertTrue(all(i.destroyed for i in g.items.values()))
        self.assertEqual(score(g)["suspects_escaped"], 8)

    def test_alerted_captain_leaves_sooner(self):
        calm, rushed = yacht(roll=0.99), yacht(roll=0.99)
        npc(rushed, "captain").state = ALERT
        calm.execute("wait")
        rushed.execute("wait")
        self.assertLess(rushed.departure, calm.departure)

    def test_stopping_the_captain_stops_the_clock(self):
        g = yacht(roll=0.99)
        npc(g, "captain").state = RESTRAINED
        left = g.departure
        for _ in range(60):
            g.execute("wait")
        self.assertFalse(g.over)
        self.assertEqual(g.departure, left)
        self.assertTrue(any("out of action" in t for _, t in g.drain()))

    def test_an_uncuffed_captain_can_start_the_clock_again(self):
        g = yacht(roll=0.99)
        cap = npc(g, "captain")
        cap.state = SURRENDERED
        g.execute("wait")
        left = g.departure
        cap.state = ALERT  # stopped complying
        g.execute("wait")
        self.assertLess(g.departure, left)


class DumpingTests(unittest.TestCase):
    def test_alerted_dumper_destroys_evidence_in_front_of_you(self):
        g = yacht(roll=0.0)
        g.team_room = "salon"
        npc(g, "reydolfo").state = ALERT
        g.execute("wait")
        self.assertTrue(g.items["duffels"].destroyed)
        self.assertTrue(any("over the side" in t for _, t in g.drain()))

    def test_dumper_needs_the_team_in_the_room(self):
        g = yacht(roll=0.0)
        g.team_room = "aft_deck"  # right next door
        npc(g, "reydolfo").state = ALERT
        g.execute("wait")
        self.assertFalse(g.items["duffels"].destroyed)

    def test_destroyed_evidence_cannot_be_collected(self):
        g = yacht()
        g.items["duffels"].destroyed = True
        g.team_room = "salon"
        g.execute("collect")
        self.assertFalse(g.items["duffels"].collected)

    def test_stunned_or_unaware_dumpers_do_nothing(self):
        g = yacht(roll=0.0)
        rey = npc(g, "reydolfo")
        rey.state, rey.stunned = ALERT, 3
        g.execute("wait")
        self.assertFalse(g.items["duffels"].destroyed)
        g = yacht(roll=0.99)  # unaware, and the roll would fail anyway
        g.execute("wait")
        self.assertFalse(g.items["duffels"].destroyed)


class HelmTests(unittest.TestCase):
    def test_captain_stays_at_the_helm(self):
        g = yacht(roll=0.0)  # every roam roll would succeed
        cap = npc(g, "captain")
        cap.state = ALERT
        for _ in range(5):
            g.execute("wait")
        self.assertEqual(cap.room, "bridge")

    def test_clock_pauses_when_the_captain_leaves_the_helm(self):
        g = yacht(roll=0.99)
        cap = npc(g, "captain")
        cap.state, cap.room = ALERT, "aft_deck"  # e.g. he ran from a yell
        left = g.departure
        g.execute("wait")
        self.assertEqual(g.departure, left)


class EscapeTests(unittest.TestCase):
    def test_patrol_boat_at_the_stern_blocks_the_tender(self):
        g = yacht(entry="harbor", roll=0.0)
        fuente = npc(g, "fuente")
        fuente.room, fuente.state = "swim_platform", ALERT
        g.execute("wait")
        self.assertNotEqual(fuente.state, ESCAPED)


class YachtPlaythroughTests(unittest.TestCase):
    def test_random_play_never_crashes(self):
        cmds = FuzzTests.COMMANDS + ["move 4", "breach 4 flash", "move 5", "wedge 1",
                                     "yell l", "restrain c", "status"]
        for difficulty in ("easy", "medium", "hard"):
            for seed in range(40):
                rng = random.Random(seed)
                g = yacht(entry=rng.choice(["pier", "harbor"]), seed=seed,
                          difficulty=difficulty)
                for _ in range(120):
                    if g.over:
                        break
                    g.execute(rng.choice(cmds))
                    g.drain()
                if not g.over:
                    g.end_mission()
                score(g)


if __name__ == "__main__":
    unittest.main()
