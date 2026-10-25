import random
import unittest

from readyornot import tuning as T
from readyornot.engine import Game
from readyornot.model import ALERT, DEAD, INCAPACITATED, RESTRAINED, SURRENDERED
from readyornot.scenario import list_scenarios, load_scenario
from readyornot.scoring import score


class Rigged(random.Random):
    """random() always returns `value`; everything else behaves normally."""

    def __init__(self, value):
        super().__init__(0)
        self.value = value

    def random(self):
        return self.value


def new_game(entry="front_yard", roll=None, seed=0):
    rng = Rigged(roll) if roll is not None else None
    return Game(load_scenario("larkspur_lane"), "standard", entry, seed=seed, rng=rng)


def npc(game, npc_id):
    return next(n for n in game.npcs if n.id == npc_id)


class ScenarioTests(unittest.TestCase):
    def test_all_scenarios_load(self):
        scns = list_scenarios()
        self.assertTrue(scns)
        for s in scns:
            scn = load_scenario(s["id"])
            self.assertTrue(any(r.entry for r in scn.rooms))

    def test_every_scenario_folder_is_complete(self):
        from readyornot.scenario import SCENARIO_DIR
        folders = [p for p in SCENARIO_DIR.iterdir() if p.is_dir()]
        self.assertEqual(len(folders), len(list_scenarios()))
        for folder in folders:
            for name in ("scenario.json", "detailed.art", "compact.art"):
                self.assertTrue((folder / name).exists(), f"{folder.name}/{name} is missing")
            self.assertEqual(load_scenario(folder.name).id, folder.name)

    def test_every_room_reachable(self):
        g = new_game()
        for r in g.rooms:
            self.assertLess(g.dist("front_yard", r), 99, r)


class DoorTests(unittest.TestCase):
    def test_open_locked_door_takes_no_time(self):
        g = new_game()
        g.execute("open 1")
        self.assertEqual(g.time, 0)
        self.assertTrue(g.doors["front_door"].lock_known)
        self.assertEqual(g.doors["front_door"].state, "closed")

    def test_c2_breaks_door_stuns_room_and_clears_trap(self):
        g = new_game(roll=0.99)
        g.team_room = "hallway"
        g.execute("c2 master")
        d = g.doors["master_door"]
        self.assertEqual(d.state, "broken")
        self.assertIsNone(d.trap)
        self.assertGreater(npc(g, "coyle").stunned, 0)
        self.assertEqual(g.disoriented, 0)

    def test_opening_trapped_door_sets_it_off(self):
        g = new_game(roll=0.99)
        g.team_room = "hallway"
        g.doors["master_door"].locked = False
        g.execute("open master")
        self.assertEqual(g.doors["master_door"].state, "open")
        self.assertGreater(g.disoriented, 0)

    def test_mirror_reveals_trap(self):
        g = new_game(roll=0.99)
        g.team_room = "hallway"
        g.execute("mirror basement")
        self.assertTrue(g.doors["basement_door"].trap_known)
        g.execute("disarm basement")
        self.assertIsNone(g.doors["basement_door"].trap)

    def test_suspects_cannot_pass_wedged_door(self):
        g = new_game()
        g.team_room = "front_yard"
        g.doors["garage_door"].wedged = True
        lookout = npc(g, "lookout")
        self.assertFalse(g.npc_move(lookout, allow_team_room=True))


class ROETests(unittest.TestCase):
    def setUp(self):
        self.g = new_game(roll=0.0)  # every roll succeeds
        self.g.team_room = "basement"

    def test_letter_targets_parse(self):
        # Regression: 'a' used to be stripped as a filler word.
        g = new_game(roll=0.0)
        g.team_room = "living"
        npc(g, "dice").aggression = 0  # no fake surrender
        g.execute("yell")
        g.execute("restrain a")
        self.assertEqual(npc(g, "dice").state, RESTRAINED)

    def test_shooting_unarmed_suspect_is_unauthorized(self):
        self.g.execute("shoot " + npc(self.g, "bagger").tag)
        self.assertTrue(any("deadly" in p for p, _ in self.g.penalties))

    def test_shooting_concealed_weapon_is_unauthorized(self):
        self.g.execute("shoot " + npc(self.g, "chemist").tag)
        self.assertTrue(any("deadly" in p for p, _ in self.g.penalties))

    def test_shooting_visibly_armed_suspect_is_authorized(self):
        g = new_game(roll=0.0)
        g.team_room = "garage"
        g.execute("shoot " + npc(g, "lookout").tag)
        self.assertEqual(g.penalties, [])
        self.assertIn(npc(g, "lookout").state, (DEAD, INCAPACITATED))

    def test_shooting_civilian_is_double_penalty(self):
        g = new_game(roll=0.0)
        g.team_room = "living"
        g.execute("shoot " + npc(g, "tasha").tag)
        self.assertEqual(len(g.penalties), 2)

    def test_taser_on_surrendered_is_unauthorized(self):
        g = new_game(roll=0.0)
        g.team_room = "spare"
        homeowner = npc(g, "homeowner")
        homeowner.state = SURRENDERED
        g.execute("taser " + homeowner.tag)
        self.assertTrue(any("Unauthorized use of force" in p for p, _ in g.penalties))

    def test_cannot_restrain_noncompliant(self):
        g = new_game(roll=0.99)
        g.team_room = "living"
        g.execute("restrain a")
        self.assertEqual(npc(g, "dice").state, "unaware")
        self.assertEqual(g.time, 0)

    def test_hidden_weapon_found_on_search(self):
        g = new_game(roll=0.0)
        g.team_room = "living"
        dice = npc(g, "dice")
        dice.aggression = 0  # no fake surrender
        g.execute("yell")
        self.assertEqual(dice.weapon, "pistol")  # concealed weapons aren't dropped on surrender
        g.execute("restrain a")
        self.assertIsNone(dice.weapon)
        self.assertIn("w_dice", g.items)


class CombatTests(unittest.TestCase):
    def test_raised_weapon_gives_one_action_warning(self):
        g = new_game(roll=0.99)
        g.team_room = "garage"
        lookout = npc(g, "lookout")
        g.go_hostile(lookout)  # outside a tick: player gets the next action
        hp = sum(o.hp for o in g.officers)
        g.execute("shoot " + lookout.tag)  # 0.99 roll = miss, then the tick fires
        self.assertEqual(lookout.state, "hostile")
        self.assertTrue(any("at" in t for _, t in g.drain()))
        self.assertEqual(sum(o.hp for o in g.officers), hp)  # 0.99 roll also misses us

    def test_player_death_ends_mission(self):
        g = new_game()
        g.damage_officer(g.player, 10_000)
        self.assertTrue(g.over)
        self.assertEqual(g.outcome, "kia")
        self.assertEqual(score(g)["grade"], "F")

    def test_breach_flash_stuns_before_entry(self):
        g = new_game(roll=0.99)
        g.team_room = "hallway"
        g.execute("breach master c2 flash")
        self.assertEqual(g.team_room, "master")
        self.assertGreater(npc(g, "coyle").stunned, 0)


class ScoringTests(unittest.TestCase):
    def test_perfect_run_scores_s(self):
        g = new_game()
        for n in g.npcs:
            n.state = RESTRAINED
            n.reported = True
        for i in g.items.values():
            i.collected = True
        g.end_mission()
        result = score(g)
        self.assertEqual(g.outcome, "complete")
        self.assertEqual(result["total"], 100)
        self.assertEqual(result["grade"], "S")

    def test_quitting_immediately_scores_nothing(self):
        g = new_game()
        g.end_mission()
        self.assertEqual(score(g)["total"], 0)


class V02Tests(unittest.TestCase):
    def test_explosive_trap_grammar(self):
        g = new_game(roll=0.99)
        g.team_room = "hallway"
        g.execute("mirror basement")
        text = " ".join(t for _, t in g.drain())
        self.assertIn("an explosive", text)
        self.assertNotIn("a explosive", text)

    def test_bound_civilian_starts_compliant_and_never_lapses(self):
        g = new_game(roll=0.0)  # every chance roll would succeed
        homeowner = npc(g, "homeowner")
        self.assertTrue(homeowner.bound)
        self.assertEqual(homeowner.state, SURRENDERED)
        g.execute("wait")  # team is elsewhere; would normally lapse at roll 0.0
        self.assertEqual(homeowner.state, SURRENDERED)
        g.team_room = "spare"
        self.assertIn("tied up", g.npc_line(homeowner))
        g.execute("restrain " + homeowner.tag)
        self.assertEqual(homeowner.state, RESTRAINED)

    def test_focused_yell_only_targets_one_person(self):
        g = new_game(roll=0.0)
        g.team_room = "living"
        npc(g, "dice").aggression = 0
        g.execute("yell b")
        self.assertEqual(npc(g, "tasha").state, SURRENDERED)
        self.assertNotEqual(npc(g, "dice").state, SURRENDERED)  # wasn't yelled at

    def test_report_all_points_to_unreported_elsewhere(self):
        g = new_game()
        tasha = npc(g, "tasha")
        tasha.state = RESTRAINED
        g.execute("report all")
        text = " ".join(t for _, t in g.drain())
        self.assertIn("Living Room", text)

    def test_disarm_can_fail(self):
        g = new_game(roll=0.0)  # below DISARM_FAIL_CHANCE
        g.team_room = "hallway"
        g.doors["master_door"].trap_known = True
        g.execute("disarm master")
        self.assertIsNone(g.doors["master_door"].trap)
        self.assertGreater(g.disoriented, 0)

    def test_aggressive_suspect_can_resist_stun(self):
        g = new_game(roll=0.0)  # below aggression * STUN_RESIST_CHANCE
        coyle = npc(g, "coyle")
        g.apply_grenade("flashbang", "master")
        self.assertEqual(coyle.stunned, 0)
        g = new_game(roll=0.99)
        g.apply_grenade("flashbang", "master")
        self.assertGreater(npc(g, "coyle").stunned, 0)


class DifficultyTests(unittest.TestCase):
    def test_presets_do_not_leak_into_each_other(self):
        hard = Game(load_scenario("larkspur_lane"), "standard", "front_yard", difficulty="hard")
        easy = Game(load_scenario("larkspur_lane"), "standard", "front_yard", difficulty="easy")
        self.assertEqual(easy.T.MIRROR_SPOTTED_CHANCE, 0.0)
        self.assertGreater(hard.T.MIRROR_SPOTTED_CHANCE, 0.0)
        self.assertEqual(T.MIRROR_SPOTTED_CHANCE, T.settings("medium").MIRROR_SPOTTED_CHANCE)
        hard.T.LOADOUTS["standard"]["items"]["flashbang"] = 99
        self.assertNotEqual(T.LOADOUTS["standard"]["items"]["flashbang"], 99)

    def test_easy_matches_original_v010_kit(self):
        easy = Game(load_scenario("larkspur_lane"), "less_lethal", "front_yard", difficulty="easy")
        self.assertEqual(easy.inv["flashbang"], 4)
        self.assertEqual(easy.inv["c2"], 1)

    def test_easy_mirror_never_draws_fire(self):
        g = Game(load_scenario("larkspur_lane"), "standard", "hallway",
                 rng=Rigged(0.0), difficulty="easy")
        g.execute("mirror master")
        self.assertTrue(all(o.hp == o.max_hp for o in g.officers))

    def test_hard_suspects_resist_more(self):
        med = new_game()
        hard = Game(load_scenario("larkspur_lane"), "standard", "front_yard", difficulty="hard")
        self.assertLess(hard.comply_chance(npc(hard, "coyle")), med.comply_chance(npc(med, "coyle")))
        # civilians are unaffected
        self.assertEqual(hard.comply_chance(npc(hard, "tasha")), med.comply_chance(npc(med, "tasha")))

    def test_every_difficulty_plays_without_crashing(self):
        for difficulty in T.DIFFICULTIES:
            for seed in range(30):
                rng = random.Random(seed)
                g = Game(load_scenario("larkspur_lane"), rng.choice(list(T.LOADOUTS)),
                         "front_yard", seed=seed, difficulty=difficulty)
                for _ in range(80):
                    if g.over:
                        break
                    g.execute(rng.choice(FuzzTests.COMMANDS))
                g.end_mission()
                score(g)


class FuzzTests(unittest.TestCase):
    COMMANDS = ["look", "map", "status", "o", "help", "yell", "wait", "collect", "report",
                "report all", "move 1", "move 2", "move 3", "mirror 1", "mirror 2", "open 1",
                "open 2", "kick 1", "kick 2", "pick 1", "c2 1", "wedge 2", "close 1",
                "disarm 1", "throw flash 1", "throw gas 2", "breach 1 flash", "breach 2 c2 stinger",
                "breach 3 pick", "shoot a", "shoot c", "taser b", "restrain a", "restrain b",
                "restrain d", "cuff e", "yell a", "yell g", "report b", "nonsense", "", "move kitchen", "breach hall"]

    def test_random_commands_never_crash(self):
        for seed in range(150):
            rng = random.Random(seed)
            scn = load_scenario("larkspur_lane")
            entry = rng.choice([r.id for r in scn.rooms if r.entry])
            g = Game(scn, rng.choice(list(T.LOADOUTS)), entry, seed=seed)
            for _ in range(120):
                if g.over:
                    break
                g.execute(rng.choice(self.COMMANDS))
                g.drain()
            g.end_mission()
            score(g)


if __name__ == "__main__":
    unittest.main()
