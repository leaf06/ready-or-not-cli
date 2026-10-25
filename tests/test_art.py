import contextlib
import io
import random
import unittest

from readyornot import art, cli
from readyornot.engine import Game
from readyornot.model import (ALERT, DEAD, HOSTILE, INCAPACITATED, RESTRAINED, SURRENDERED,
                              UNAWARE)
from readyornot.scenario import list_scenarios, load_scenario
from tests.test_engine import FuzzTests


class RoomArtTests(unittest.TestCase):
    def test_every_room_has_art_that_fits_a_phone(self):
        for s in list_scenarios():
            scn = load_scenario(s["id"])
            for room in scn.rooms:
                self.assertIn(room.id, scn.art, f"{s['id']}: no art for {room.id}")
                for line in scn.art[room.id]:
                    self.assertLessEqual(len(line), art.MAX_WIDTH, f"{room.id}: {line!r}")

    def test_exit_labels_in_art_exist(self):
        scn = load_scenario("larkspur_lane")
        g = Game(scn, "standard", "front_yard")
        for room in scn.rooms:
            g.team_room = room.id
            text = "\n".join(scn.art[room.id])
            for i in range(1, len(g.exits()) + 1):
                self.assertIn(f"[{i}]", text, f"{room.id} art is missing exit [{i}]")


class FigureTests(unittest.TestCase):
    def test_figures_are_uniform_width(self):
        for key, rows in art.FIGURES.items():
            self.assertEqual(len(rows), 3, key)
            for row in rows:
                self.assertEqual(len(row), art.CELL, f"{key}: {row!r}")

    def test_every_state_draws(self):
        g = Game(load_scenario("larkspur_lane"), "standard", "front_yard")
        people = g.npcs
        states = [UNAWARE, ALERT, HOSTILE, SURRENDERED, RESTRAINED, INCAPACITATED, SURRENDERED,
                  DEAD, ALERT]
        for n, st in zip(people, states):
            n.state = st
        self.assertTrue(people[6].bound)  # the homeowner, surrendered = tied to the chair
        people[0].stunned = 2
        lines = art.people_strip(people)
        self.assertTrue(any("AIMING" in l for l in lines))
        self.assertTrue(any("tied up" in l for l in lines))  # bound homeowner
        self.assertTrue(any("* * *" in l for l in lines))
        for line in lines:
            self.assertLessEqual(len(line), art.MAX_WIDTH)

    def test_mirror_view_counts_feet(self):
        g = Game(load_scenario("larkspur_lane"), "standard", "front_yard")
        view = "\n".join(art.mirror_view(g.room_npcs("basement")))
        self.assertEqual(view.count("_||_"), 2)


class RenderTests(unittest.TestCase):
    def test_full_games_render_with_art(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            for seed in range(25):
                rng = random.Random(seed)
                g = Game(load_scenario("larkspur_lane"), "standard", "back_yard", seed=seed)
                for _ in range(60):
                    if g.over:
                        break
                    g.execute(rng.choice(FuzzTests.COMMANDS))
                    cli.render(g, g.drain())
                g.end_mission()
                cli.debrief(g)
        out = buf.getvalue()
        self.assertIn("|", out)
        for line in out.splitlines():
            if line.startswith(("  ", " |", " .", " '")) and "|" in line:
                self.assertLessEqual(len(line), 100)

    def test_art_off_prints_no_art(self):
        g = Game(load_scenario("larkspur_lane"), "standard", "front_yard")
        g.cmd_look([])
        buf = io.StringIO()
        cli.Settings.art = False
        try:
            with contextlib.redirect_stdout(buf):
                cli.render(g, g.drain())
        finally:
            cli.Settings.art = True
        self.assertNotIn("side path    ,,", buf.getvalue())
        self.assertIn("Front Yard", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
