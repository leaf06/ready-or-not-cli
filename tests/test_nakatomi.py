import contextlib
import io
import random
import unittest

from readyornot import cli
from readyornot.engine import Game
from readyornot.model import ALERT, ESCAPED, RESTRAINED
from readyornot.scenario import load_scenario
from readyornot.scoring import score
from tests.test_engine import FuzzTests, Rigged


def nakatomi(entry="plaza", roll=None, seed=0, difficulty="medium"):
    rng = Rigged(roll) if roll is not None else None
    return Game(load_scenario("nakatomi"), "standard", entry, seed=seed, rng=rng,
                difficulty=difficulty)


def npc(game, npc_id):
    return next(n for n in game.npcs if n.id == npc_id)


class FriendlyCopTests(unittest.TestCase):
    def test_armed_civilian_looks_unknown(self):
        g = nakatomi()
        line = g.npc_line(npc(g, "mcclane"))
        self.assertIn("Unknown", line)
        self.assertIn("armed: smg", line)

    def test_shooting_the_armed_civilian_is_unauthorized(self):
        g = nakatomi(roll=0.0)
        g.team_room = "unfinished"
        mcclane = npc(g, "mcclane")
        self.assertFalse(g.deadly_authorized(mcclane))
        g.execute("shoot " + mcclane.tag)
        self.assertTrue(any("deadly force" in p.lower() for p, _ in g.penalties))

    def test_securing_him_counts_as_a_rescue(self):
        g = nakatomi(roll=0.0)
        g.team_room = "unfinished"
        mcclane = npc(g, "mcclane")
        npc(g, "hans").aggression = 0
        g.execute("yell " + mcclane.tag)
        g.execute("restrain " + mcclane.tag)
        self.assertEqual(mcclane.state, RESTRAINED)
        self.assertIn("Civilian", g.label(mcclane))


class HansTests(unittest.TestCase):
    def test_hans_passes_for_a_hostage_until_searched(self):
        g = nakatomi(roll=0.0)
        g.team_room = "unfinished"
        hans = npc(g, "hans")
        hans.aggression = 0  # no fake surrender for this test
        self.assertIn("Unknown", g.label(hans))
        self.assertFalse(g.deadly_authorized(hans))  # hands not visible isn't a weapon
        g.execute("yell " + hans.tag)
        g.execute("restrain " + hans.tag)
        self.assertIn("Suspect", g.label(hans))
        self.assertIn("w_hans", g.items)  # the hidden pistol turned up in the search

    def test_hans_runs_for_the_garage(self):
        g = nakatomi(entry="helipad", roll=0.0)
        hans = npc(g, "hans")
        hans.state = ALERT
        for _ in range(6):
            g.execute("wait")
            if hans.state == ESCAPED:
                break
        self.assertEqual(hans.state, ESCAPED)


class VaultClockTests(unittest.TestCase):
    def test_stopping_theo_stops_the_vault(self):
        g = nakatomi(roll=0.99)
        npc(g, "theo").state = RESTRAINED
        for _ in range(80):
            g.execute("wait")
        self.assertFalse(g.over)

    def test_vault_opening_uses_the_scenario_banner(self):
        g = nakatomi(roll=0.99)
        while not g.over:
            g.execute("wait")
        self.assertEqual(g.outcome, "departed")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.debrief(g)
        out = buf.getvalue()
        self.assertIn("V A U L T   O P E N", out)
        self.assertIn("the vault opened and the roof blew", out)
        self.assertNotIn("DEPARTED", out)

    def test_winning_shows_the_christmas_banner(self):
        g = nakatomi()
        for n in g.npcs:
            n.state, n.reported = RESTRAINED, True
        for i in g.items.values():
            i.collected = True
        g.end_mission()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.debrief(g)
        self.assertIn("C H R I S T M A S", buf.getvalue())
        self.assertIn("Merry Christmas", buf.getvalue())


class NakatomiPlaythroughTests(unittest.TestCase):
    def test_random_play_never_crashes(self):
        cmds = FuzzTests.COMMANDS + ["move 4", "breach 4 flash", "yell l", "yell m",
                                     "taser k", "shoot k", "restrain l", "status"]
        for difficulty in ("easy", "medium", "hard"):
            for seed in range(40):
                rng = random.Random(seed)
                g = nakatomi(entry=rng.choice(["plaza", "helipad"]), seed=seed,
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
