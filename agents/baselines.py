"""
Non-adaptive comparison attackers (same interface as the adaptive one).

  random   : random tactic and stage, fixed difficulty.
  scripted : round-robin through tactics and stages in a fixed order.
  greedy   : belief only. Thompson-samples the player model and attacks the
             most promising tactic. NO lookahead, NO planner, NO adaptive
             difficulty (isolates the value of those layers).
All use FIXED_DIFFICULTY so only the selection strategy differs.
"""
from agents.base import AttackChoice
from config import FIXED_DIFFICULTY, MAX_SAME_TACTIC_STREAK, STAGES, TACTICS


class RandomAttacker:
    name = "random"

    def __init__(self, rng):
        self.rng = rng

    def choose_attack(self, model, state):
        return AttackChoice(self.rng.choice(TACTICS), self.rng.choice(STAGES), FIXED_DIFFICULTY)

    def observe(self, record):
        pass


class ScriptedAttacker:
    name = "scripted"

    def __init__(self, rng=None):
        self.i = 0

    def choose_attack(self, model, state):
        choice = AttackChoice(TACTICS[self.i % len(TACTICS)], STAGES[self.i % len(STAGES)],
                              FIXED_DIFFICULTY)
        self.i += 1
        return choice

    def observe(self, record):
        pass


class GreedyThompsonAttacker:
    name = "greedy"

    def __init__(self, rng):
        self.rng = rng
        self.i = 0
        self.recent = []

    def choose_attack(self, model, state):
        draws = {t: model.sample(t, self.rng) for t in TACTICS}
        n = MAX_SAME_TACTIC_STREAK
        if len(self.recent) >= n and len(set(self.recent[-n:])) == 1:
            draws.pop(self.recent[-1])                  # same fairness rule as the adaptive agent
        tactic = max(draws, key=draws.get)
        self.recent.append(tactic)
        stage = STAGES[self.i % len(STAGES)]
        self.i += 1
        return AttackChoice(tactic, stage, FIXED_DIFFICULTY)

    def observe(self, record):
        pass
