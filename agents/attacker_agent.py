"""
The adaptive attacker: glue for player model + A* + expectimax + difficulty.

Each scam round:
  1. A* (re)plans a campaign (stage, tactic) path from the current beliefs.
     The next stage on that path is today's stage.
  2. Expectimax chooses the actual TACTIC, with a small bonus for the tactic
     A* planned for this stage (so the two layers cooperate).
  3. The difficulty controller sets how visible the red flags are.
After the response: advance the plan; if the player REPORTED, the campaign was
detected, so throw the plan away and re-plan.

Ablations via flags: use_astar=False (stages simply cycle),
adaptive_difficulty=False (fixed medium difficulty), phi=0 (pure adversary).
"""
import dataclasses

from agents.astar_planner import plan_campaign
from agents.base import AttackChoice
from agents.difficulty import DifficultyController
from agents.expectimax import UtilityParams, choose_tactic
from config import EXPECTIMAX_DEPTH, FIXED_DIFFICULTY, STAGES, TACTICS


class AdaptiveAttacker:
    def __init__(self, rng, name="full", use_astar=True, adaptive_difficulty=True,
                 phi=None, depth=EXPECTIMAX_DEPTH):
        self.rng = rng
        self.name = name
        self.use_astar = use_astar
        self.adaptive_difficulty = adaptive_difficulty
        self.depth = depth
        self.params = UtilityParams()
        if phi is not None:
            self.params = dataclasses.replace(self.params, phi=phi)
        self.difficulty = DifficultyController()
        self.recent_tactics = []
        self.plan = None
        self.step = 0
        self.cycle = 0
        self.last_plan_cost = None

    def choose_attack(self, model, state):
        if self.use_astar:
            if self.plan is None or self.step >= len(self.plan.path):
                self.plan = plan_campaign(model.beliefs())
                self.step = 0
                self.last_plan_cost = self.plan.cost
            stage, planned = self.plan.path[self.step]
        else:
            stage, planned = STAGES[self.cycle % len(STAGES)], None
            self.cycle += 1

        best, value, _qvals, _nodes = choose_tactic(
            model.snapshot(), self.recent_tactics, self.depth, self.params, planned)
        tactic = self.rng.choice(best)          # seeded tie-break
        level = self.difficulty.level if self.adaptive_difficulty else FIXED_DIFFICULTY
        self.recent_tactics.append(tactic)
        return AttackChoice(tactic, stage, level, value, planned,
                            {"plan_cost": self.last_plan_cost})

    def observe(self, record):
        self.difficulty.observe(record["correct"])
        if record["is_scam"] and self.use_astar:
            self.step += 1
            if record["player_action"] == "report":   # campaign detected
                self.plan = None
