"""
Simulated players (bots) with hidden vulnerability profiles.

ASSUMPTIONS (state these in the paper -- they are modelling choices, not facts):
  * Each bot has a hidden P(trust) per tactic (weak tactic 0.80, others 0.30).
  * Visible red flags help: P(trust) is multiplied by TELL_FACTOR[difficulty]
    (easy 0.45, medium 0.75, hard 1.00).
  * LEARNING: after every scam (the game shows feedback) the bot becomes less
    vulnerable to THAT tactic: p *= 1 - learn_rate (x1.5 if it just fell for it),
    plus a small transfer to the other tactics (20% of the effect).
    learn_rate = 0 gives a bot that never improves (used to test how fast the
    attacker identifies a fixed weakness).
Because the bot's learning rule is something WE wrote, results validate the
attacker logic and the pipeline; they are NOT evidence about human learning.
"""
from config import TACTICS

BASE_P, WEAK_P = 0.30, 0.80
TELL_FACTOR = {1: 0.45, 2: 0.75, 3: 1.00}
P_FLOOR = 0.02

SENSITIVE_PROFILES = {f"{t}_sensitive": {"weak": t, "false_alarm": 0.03} for t in TACTICS}
PROFILES = {
    **SENSITIVE_PROFILES,
    "balanced": {"weak": None, "false_alarm": 0.03},
    "paranoid": {"weak": None, "base": 0.08, "false_alarm": 0.35},   # reports too much
}


class SimulatedPlayer:
    def __init__(self, profile_name, rng, learn_rate=0.12):
        spec = PROFILES[profile_name]
        self.profile_name = profile_name
        self.rng = rng
        self.learn_rate = learn_rate
        self.false_alarm = spec["false_alarm"]
        base = spec.get("base", BASE_P)
        self.p = {t: base for t in TACTICS}
        self.weak_tactic = spec["weak"]
        if self.weak_tactic:
            self.p[self.weak_tactic] = WEAK_P
        self.initial_posttest = self.posttest()

    def posttest(self):
        """Mean TRUE vulnerability at fixed medium difficulty (a clean 'post-test')."""
        return sum(self.p.values()) / len(self.p) * TELL_FACTOR[2]

    def respond(self, scenario):
        """Returns (action, response_time_seconds)."""
        rng = self.rng
        if scenario["is_scam"]:
            p_trust = self.p[scenario["tactic"]] * TELL_FACTOR[scenario["difficulty"]]
            p_trust = min(0.95, max(0.01, p_trust))
            if rng.random() < p_trust:
                action = "trust"
            else:
                action = rng.choices(["verify", "report", "ignore"], weights=[0.45, 0.40, 0.15])[0]
        else:
            fa = self.false_alarm
            weights = [0.65, 0.25, fa, 0.07]
            action = rng.choices(["trust", "verify", "report", "ignore"], weights=weights)[0]
        rt = max(1.0, rng.gauss(5.0, 1.5)) + (2.0 if action in ("verify", "report") else 0.0)
        return action, round(rt, 3)

    def learn(self, scenario, action):
        if self.learn_rate <= 0 or not scenario["is_scam"]:
            return
        t = scenario["tactic"]
        effect = self.learn_rate * (1.5 if action == "trust" else 1.0)
        for tactic in TACTICS:
            e = effect if tactic == t else 0.2 * effect
            self.p[tactic] = max(P_FLOOR, self.p[tactic] * (1 - e))
