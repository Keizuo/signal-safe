"""
Automated checks. Run from the project root:   python -m unittest discover -s tests -v

Each test group maps to a claim you make in the paper (e.g. "A* is optimal").
"""
import csv
import json
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.astar_planner import brute_force_cost, plan_campaign
from agents.difficulty import DifficultyController
from agents.expectimax import UtilityParams, choose_tactic
from agents.factory import ATTACKER_TYPES, make_attacker
from agents.player_model import PlayerModel
from config import STAGES, TACTICS
from evaluation.logger import FIELDS, GameLogger
from evaluation.metrics import d_prime, identification, session_metrics
from evaluation.run_experiments import run_session
from evaluation.simulated_players import SimulatedPlayer
from game.scenarios import ScenarioBank, load_scenarios
from game.scoring import score_action
from game.session import Session


def play_with_bot(condition, profile="fear_sensitive", seed=1, rounds=20, learn=0.12):
    bank = ScenarioBank()
    session = Session(make_attacker(condition, seed), rounds=rounds, seed=seed, bank=bank,
                      agent_type=condition)
    bot = SimulatedPlayer(profile, random.Random(seed), learn)
    while (sc := session.next_scenario()) is not None:
        action, rt = bot.respond(sc)
        session.submit(action, rt)
        bot.learn(sc, action)
    return session, bot


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.scenarios = load_scenarios()
        self.scams = [s for s in self.scenarios if s["is_scam"]]

    def test_bank_size_and_coverage(self):
        self.assertEqual(len(self.scams), 72)
        self.assertEqual(len([s for s in self.scenarios if not s["is_scam"]]), 11)
        cells = {(s["tactic"], s["stage"], s["difficulty"]) for s in self.scams}
        self.assertEqual(len(cells), 6 * 4 * 3)          # every tactic x stage x difficulty

    def test_fairness_floor_every_scam_has_a_red_flag(self):
        for s in self.scams:
            self.assertGreaterEqual(len(s["red_flags"]), 1, s["id"])

    def test_easier_levels_show_at_least_as_many_flags(self):
        by_template = {}
        for s in self.scams:
            by_template.setdefault(s["template_id"], {})[s["difficulty"]] = len(s["red_flags"])
        for tid, d in by_template.items():
            self.assertGreaterEqual(d[1], d[2], tid)
            self.assertGreaterEqual(d[2], d[3], tid)

    def test_no_leftover_placeholders(self):
        for s in self.scenarios:
            self.assertNotIn("[[", s["message"])
            self.assertNotIn("{player_name}", s["message"])

    def test_loader_rejects_real_looking_domain(self):
        bad = dict(self.scenarios[0], message="Visit paypal.com now")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_text(json.dumps([bad]))
            with self.assertRaises(ValueError):
                load_scenarios(path)


class ScoringTests(unittest.TestCase):
    scam = {"is_scam": True}
    legit = {"is_scam": False}

    def test_scam_outcomes(self):
        self.assertTrue(score_action(self.scam, "trust")["fell_for"])
        self.assertLess(score_action(self.scam, "trust")["points"], 0)
        self.assertTrue(score_action(self.scam, "report")["detected"])
        self.assertTrue(score_action(self.scam, "verify")["is_correct"])

    def test_ignoring_a_scam_is_not_correct_or_detection(self):
        out = score_action(self.scam, "ignore")
        self.assertFalse(out["is_correct"])
        self.assertFalse(out["detected"])

    def test_false_alarm_is_penalised(self):
        out = score_action(self.legit, "report")
        self.assertTrue(out["false_alarm"])
        self.assertLess(out["points"], 0)
        self.assertTrue(score_action(self.legit, "verify")["is_correct"])


class PlayerModelTests(unittest.TestCase):
    def test_bayesian_update(self):
        m = PlayerModel()
        self.assertAlmostEqual(m.vulnerability("urgency"), 0.5)
        m.update("urgency", True)
        self.assertAlmostEqual(m.vulnerability("urgency"), 2 / 3)
        m.update("urgency", False)
        self.assertAlmostEqual(m.vulnerability("urgency"), 0.5)

    def test_uncertainty_shrinks_with_evidence(self):
        m = PlayerModel()
        before = m.uncertainty("fear")
        for _ in range(6):
            m.update("fear", True)
        self.assertLess(m.uncertainty("fear"), before)

    def test_top_belief_none_on_ties(self):
        m = PlayerModel()
        self.assertIsNone(m.top_belief())
        m.update("fear", True)
        self.assertEqual(m.top_belief(), "fear")


class ExpectimaxTests(unittest.TestCase):
    def setUp(self):
        self.m = PlayerModel()
        for _ in range(4):
            self.m.update("fear", True)       # looks very vulnerable to fear
            self.m.update("urgency", False)

    def test_depth_one_picks_highest_belief_with_pure_adversary(self):
        params = UtilityParams(explore=0, repeat=0, phi=0, plan_bonus=0)
        best, _, _, nodes = choose_tactic(self.m.snapshot(), (), depth=1, params=params)
        self.assertEqual(best, ["fear"])
        self.assertEqual(nodes, 6)

    def test_lookahead_really_expands_a_tree(self):
        _, _, _, n1 = choose_tactic(self.m.snapshot(), (), depth=1)
        _, _, _, n3 = choose_tactic(self.m.snapshot(), (), depth=3)
        self.assertEqual(n1, 6)
        self.assertGreater(n3, 500)

    def test_streak_rule_blocks_third_repeat(self):
        _, _, q, _ = choose_tactic(self.m.snapshot(), ("fear", "fear"), depth=2)
        self.assertNotIn("fear", q)

    def test_fairness_term_changes_preference(self):
        pure = UtilityParams(phi=0, explore=0, repeat=0, plan_bonus=0)
        fair = UtilityParams(phi=5.0, explore=0, repeat=0, plan_bonus=0, target=0.3)
        b1, *_ = choose_tactic(self.m.snapshot(), (), 1, pure)
        b2, *_ = choose_tactic(self.m.snapshot(), (), 1, fair)
        self.assertEqual(b1, ["fear"])
        self.assertNotEqual(b2, ["fear"])      # strong fairness weight avoids the 'crushing' tactic


class AStarTests(unittest.TestCase):
    def test_optimal_against_brute_force(self):
        rng = random.Random(0)
        for _ in range(25):
            vuln = {t: rng.uniform(0.05, 0.95) for t in TACTICS}
            plan = plan_campaign(vuln)
            self.assertAlmostEqual(plan.cost, brute_force_cost(vuln), places=9)

    def test_path_reaches_escalation_in_stage_order(self):
        plan = plan_campaign({t: 0.5 for t in TACTICS})
        stages = [s for s, _ in plan.path]
        self.assertEqual(stages[-1], "escalation")
        self.assertEqual(stages, sorted(stages, key=STAGES.index))

    def test_plan_depends_on_player_model(self):
        gullible = plan_campaign({t: 0.8 for t in TACTICS})
        vigilant = plan_campaign({t: 0.1 for t in TACTICS})
        self.assertGreater(len(gullible.path), len(vigilant.path))   # skips stages vs. vigilant player
        only_fear = {t: 0.1 for t in TACTICS}
        only_fear["fear"] = 0.9
        self.assertIn("fear", [t for _, t in plan_campaign(only_fear).path])


class DifficultyTests(unittest.TestCase):
    def test_raises_one_level_after_good_streak_and_clears_window(self):
        d = DifficultyController()
        for _ in range(3):
            d.observe(True)
        self.assertEqual(d.level, 2)
        d.observe(True)                # window was cleared: not enough evidence yet
        self.assertEqual(d.level, 2)

    def test_lowers_after_poor_run_and_respects_bounds(self):
        d = DifficultyController(start=3)
        for _ in range(3):
            d.observe(False)
        self.assertEqual(d.level, 2)
        for _ in range(30):
            d.observe(False)
        self.assertEqual(d.level, 1)
        for _ in range(60):
            d.observe(True)
        self.assertEqual(d.level, 3)


class SessionTests(unittest.TestCase):
    def test_exact_legit_share_and_fresh_first_selection(self):
        for cond in ATTACKER_TYPES:
            session, _ = play_with_bot(cond, seed=4)
            rows = session.records
            self.assertEqual(sum(1 for r in rows if not r["is_scam"]), 6, cond)
            # Fresh-first rule: a message repeats ONLY after all 4 templates of that
            # tactic were used (each tactic has 4 templates, one per campaign stage).
            for tactic in TACTICS:
                ids = [r["template_id"] for r in rows if r["is_scam"] and r["tactic"] == tactic]
                self.assertEqual(len(set(ids)), min(len(ids), 4), f"{cond}/{tactic}")
            legit_ids = [r["template_id"] for r in rows if not r["is_scam"]]
            self.assertEqual(len(legit_ids), len(set(legit_ids)), cond)

    def test_adaptive_and_greedy_never_use_a_tactic_three_times_in_a_row(self):
        for cond in ("greedy", "expectimax", "expectimax_astar", "full", "full_phi0"):
            session, _ = play_with_bot(cond, seed=9, rounds=60)
            tactics = [r["tactic"] for r in session.records if r["is_scam"]]
            for a, b, c in zip(tactics, tactics[1:], tactics[2:]):
                self.assertFalse(a == b == c, cond)

    def test_same_seed_gives_identical_sessions(self):
        a, _ = play_with_bot("full", seed=11)
        b, _ = play_with_bot("full", seed=11)
        key = lambda s: [(r["scenario_id"], r["player_action"]) for r in s.records]
        self.assertEqual(key(a), key(b))

    def test_player_model_is_updated_for_baselines_too(self):
        session, _ = play_with_bot("scripted", seed=2)
        self.assertGreater(sum(session.model.observations.values()), 0)

    def test_submit_before_next_scenario_fails(self):
        s = Session(make_attacker("random", 1), rounds=2, seed=1)
        with self.assertRaises(RuntimeError):
            s.submit("trust")

    def test_logger_writes_header_and_rows(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "log.csv"
            session = Session(make_attacker("full", 1), rounds=4, seed=1, logger=GameLogger(path))
            while session.next_scenario() is not None:
                session.submit("verify", 1.5)
            with open(path, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 4)
            self.assertEqual(list(rows[0].keys()), FIELDS)
            self.assertEqual(rows[0]["agent_type"], "full")


class SimulationTests(unittest.TestCase):
    def test_learning_lowers_true_vulnerability_and_static_does_not(self):
        _, learner = play_with_bot("full", learn=0.12)
        _, static = play_with_bot("full", learn=0.0)
        self.assertLess(learner.posttest(), learner.initial_posttest)
        self.assertAlmostEqual(static.posttest(), static.initial_posttest)

    def test_paranoid_bot_raises_more_false_alarms(self):
        bank = ScenarioBank()
        legit = bank.legits[0]
        counts = {}
        for profile in ("balanced", "paranoid"):
            bot = SimulatedPlayer(profile, random.Random(0))
            counts[profile] = sum(bot.respond(legit)[0] == "report" for _ in range(500))
        self.assertGreater(counts["paranoid"], counts["balanced"] * 3)

    def test_run_session_returns_metrics(self):
        _, m = run_session("full", "fear_sensitive", 5, 20, 0.0, ScenarioBank())
        for key in ("fall_rate", "d_prime", "stable_id_round", "weak_share", "posttest_drop"):
            self.assertIn(key, m)


class MetricsTests(unittest.TestCase):
    def test_d_prime_sign(self):
        self.assertGreater(d_prime(9, 10, 1, 10), 0)
        self.assertLess(d_prime(1, 10, 9, 10), 0)

    def test_identification_requires_staying_correct(self):
        mk = lambda r, top: {"round": r, "is_scam": True, "top_belief": top}
        rows = [mk(1, "fear"), mk(2, "urgency"), mk(3, "fear"), mk(4, "fear")]
        out = identification(rows, "fear", 4)
        self.assertEqual(out["first_id_round"], 1)
        self.assertEqual(out["stable_id_round"], 3)
        never = identification([mk(1, "fear"), mk(2, "urgency")], "fear", 2)
        self.assertEqual(never["stable_id_round"], 3)       # censored = rounds + 1
        self.assertFalse(never["identified"])


class PackagingTests(unittest.TestCase):
    def test_cli_entry_point_does_not_need_pygame(self):
        """Regression: main.py used to import pygame at the top, breaking --cli."""
        sys.modules.pop("pygame", None)
        sys.modules.pop("main", None)
        sys.modules["pygame"] = None            # makes `import pygame` raise ImportError
        try:
            import main  # noqa: F401
        finally:
            sys.modules.pop("pygame", None)
            sys.modules.pop("main", None)


if __name__ == "__main__":
    unittest.main()
