"""
Beta-Bernoulli model of how vulnerable the player is to each tactic.

For each tactic we keep Beta(alpha, beta):
  * a scam that the player TRUSTS ("fell for it")   -> alpha += 1
  * a scam that the player verified/reported/ignored -> beta  += 1
The belief about P(fall) is the posterior mean alpha / (alpha + beta).
Starting from Beta(1,1) means "no idea" (mean 0.5, maximum uncertainty).

We also track the player's false-alarm rate (reporting legitimate mail).
"""
import math

from config import TACTICS


class PlayerModel:
    def __init__(self, prior=1.0):
        self.alpha = {t: float(prior) for t in TACTICS}
        self.beta = {t: float(prior) for t in TACTICS}
        self.observations = {t: 0 for t in TACTICS}
        self.fa_alpha = float(prior)     # false-alarm belief (legit messages only)
        self.fa_beta = float(prior)

    # ---- beliefs -------------------------------------------------------
    def vulnerability(self, tactic):
        """Posterior mean of P(player falls for this tactic)."""
        if tactic not in self.alpha:
            return 0.5
        return self.alpha[tactic] / (self.alpha[tactic] + self.beta[tactic])

    def uncertainty(self, tactic):
        """Posterior standard deviation (how unsure we still are)."""
        a, b = self.alpha[tactic], self.beta[tactic]
        return math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))

    def beliefs(self):
        return {t: round(self.vulnerability(t), 4) for t in TACTICS}

    def snapshot(self):
        """Immutable (alpha, beta) pairs in TACTICS order, used by expectimax."""
        return tuple((self.alpha[t], self.beta[t]) for t in TACTICS)

    def sample(self, tactic, rng):
        """Thompson sample: one random draw from the posterior."""
        return rng.betavariate(self.alpha[tactic], self.beta[tactic])

    def top_belief(self):
        """Tactic with the strictly highest belief, or None if tied."""
        means = {t: self.vulnerability(t) for t in TACTICS}
        best = max(means.values())
        winners = [t for t, v in means.items() if abs(v - best) < 1e-12]
        return winners[0] if len(winners) == 1 else None

    def most_challenging_tactic(self):
        return max(TACTICS, key=self.vulnerability)

    # ---- learning ------------------------------------------------------
    def update(self, tactic, fell_for_scenario):
        """Update after a SCAM: did the player fall for this tactic?"""
        if tactic not in self.alpha:
            return
        if fell_for_scenario:
            self.alpha[tactic] += 1
        else:
            self.beta[tactic] += 1
        self.observations[tactic] += 1

    def update_legit(self, false_alarm):
        """Update after a LEGIT message: did the player report it?"""
        if false_alarm:
            self.fa_alpha += 1
        else:
            self.fa_beta += 1

    def false_alarm_rate(self):
        return self.fa_alpha / (self.fa_alpha + self.fa_beta)
