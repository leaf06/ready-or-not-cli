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
    def test_every_room_has_compact_art_that_fits_a_phone(self):
        for s in list_scenarios():
            scn = load_scenario(s["id"])
            for room in scn.rooms:
                self.assertIn(room.id, scn.art_compact, f"{s['id']}: no compact art for {room.id}")
                for line in scn.art_compact[room.id]:
                    self.assertLessEqual(len(line), art.MAX_WIDTH, f"{room.id}: {line!r}")

    def test_every_room_has_detailed_art_that_fits_80_columns(self):
        for s in list_scenarios():
            scn = load_scenario(s["id"])
            for room in scn.rooms:
                self.assertIn(room.id, scn.art, f"{s['id']}: no detailed art for {room.id}")
                lines = scn.art[room.id]
                self.assertGreaterEqual(len(lines), art.STAGE_ROWS, room.id)
                for line in lines:
                    self.assertLessEqual(len(line), art.DETAILED_WIDTH, f"{room.id}: {line!r}")

    def test_detailed_floor_is_clear_where_people_stand(self):
        for s in list_scenarios():
            scn = load_scenario(s["id"])
            for room in scn.rooms:
                if room.outdoor:
                    continue  # NPCs never go outside
                for line in scn.art[room.id][-art.STAGE_ROWS:]:
                    floor = line[art.STAGE_LEFT:art.STAGE_RIGHT]
                    self.assertEqual(floor.strip(" ."), "", f"{room.id} floor clutter: {line!r}")

    def test_exit_labels_in_art_exist(self):
        for s in list_scenarios():
            self._check_exit_labels(s["id"])

    def _check_exit_labels(self, scenario_id):
        scn = load_scenario(scenario_id)
        g = Game(scn, "standard", next(r.id for r in scn.rooms if r.entry))
        for room in scn.rooms:
            g.team_room = room.id
            for name, art_set in (("detailed", scn.art), ("compact", scn.art_compact)):
                text = "\n".join(art_set[room.id])
                for i in range(1, len(g.exits()) + 1):
                    self.assertIn(f"[{i}]", text, f"{name} {room.id} art is missing exit [{i}]")


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


class StageTests(unittest.TestCase):
    def test_people_stand_on_the_detailed_floor(self):
        scn = load_scenario("larkspur_lane")
        g = Game(scn, "standard", "front_yard")
        people = g.room_npcs("basement")
        lines = art.scene(scn.art["basement"], people, detailed=True)
        self.assertEqual(len(lines), len(scn.art["basement"]))  # nobody spilled below
        floor = "\n".join(lines[-art.STAGE_ROWS:])
        for n in people:
            self.assertIn(f"[{n.tag}]", floor)
        for line in lines:
            self.assertLessEqual(len(line), art.DETAILED_WIDTH)

    def test_crowded_room_overflows_into_a_strip(self):
        scn = load_scenario("larkspur_lane")
        g = Game(scn, "standard", "front_yard")
        for n in g.npcs:
            n.room = "kitchen"
        lines = art.scene(scn.art["kitchen"], g.room_npcs("kitchen"), detailed=True)
        text = "\n".join(lines)
        for n in g.npcs:
            self.assertIn(f"[{n.tag}]", text)
        self.assertGreater(len(lines), len(scn.art["kitchen"]))


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
