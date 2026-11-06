"""
Expectimax lookahead over the player's (random) responses.

TREE
  MAX node    : the attacker chooses a tactic for its next message.
  CHANCE node : the player either FALLS (prob p) or RESISTS (prob 1-p), where
                p is the current posterior mean for that tactic.
  After each outcome the Beta belief is updated (alpha+1 or beta+1), so deeper
  levels use the beliefs the attacker WOULD have after seeing that response.
  That is the "look ahead a few steps over player responses".

  value(s, d) = max_a [ U(a, s) + gamma * sum_o P(o | a, s) * value(s', d-1) ]

UTILITY of sending a message with tactic a (beliefs Beta(alpha, beta)):

  U = R_FALL    * P(fall)                 attacker's goal: a successful trick
    + EXPLORE   * sd(P(fall))             curiosity: probe tactics we know little about
    - REPEAT    * (uses in last 2 msgs)   don't spam one tactic
    - PHI       * |P(fall) - TARGET|      FAIRNESS: aim for a teachable fall rate,
                                          not for crushing the player (PHI=0 is a
                                          "pure adversary", useful as an ablation)
    + PLAN      * [a == A* planned tactic] coherence with the campaign plan

Hard rule: never the same tactic 3 times in a row (MAX_SAME_TACTIC_STREAK).
With 6 tactics and depth 3 the tree has ~940 evaluations: instant.
"""
import math
from dataclasses import dataclass

import config
from config import TACTICS


@dataclass
class UtilityParams:
    r_fall: float = config.R_FALL
    explore: float = config.EXPLORE_WEIGHT
    repeat: float = config.REPEAT_PENALTY
    phi: float = config.FAIRNESS_WEIGHT
    target: float = config.TARGET_FALL_RATE
    plan_bonus: float = config.PLAN_BONUS
    gamma: float = config.DISCOUNT
    max_streak: int = config.MAX_SAME_TACTIC_STREAK


def beta_stats(a, b):
    mean = a / (a + b)
    sd = math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
    return mean, sd


def immediate_utility(a, b, repeats, is_planned, params):
    """The utility formula above, for ONE tactic with belief Beta(a, b)."""
    mean, sd = beta_stats(a, b)
    return (params.r_fall * mean
            + params.explore * sd
            - params.repeat * repeats
            - params.phi * abs(mean - params.target)
            + (params.plan_bonus if is_planned else 0.0))


def _legal(recent, params):
    """Tactic indexes allowed next (enforces the max-streak fairness rule)."""
    n = params.max_streak
    banned = None
    if len(recent) >= n and len(set(recent[-n:])) == 1:
        banned = recent[-1]
    return [i for i in range(len(TACTICS)) if i != banned]


def _updated(snapshot, i, fell):
    a, b = snapshot[i]
    pair = (a + 1, b) if fell else (a, b + 1)
    return snapshot[:i] + (pair,) + snapshot[i + 1:]


def _q_value(i, snapshot, recent, depth, params, counter, planned_index):
    a, b = snapshot[i]
    repeats = sum(1 for r in recent[-2:] if r == i)
    u = immediate_utility(a, b, repeats, planned_index == i, params)
    counter[0] += 1
    if depth <= 1:
        return u
    p = a / (a + b)
    nxt = (recent + (i,))[-2:]
    v_fall = _max_value(_updated(snapshot, i, True), nxt, depth - 1, params, counter)
    v_resist = _max_value(_updated(snapshot, i, False), nxt, depth - 1, params, counter)
    return u + params.gamma * (p * v_fall + (1 - p) * v_resist)


def _max_value(snapshot, recent, depth, params, counter):
    return max(_q_value(i, snapshot, recent, depth, params, counter, None)
               for i in _legal(recent, params))


def choose_tactic(snapshot, recent_tactics=(), depth=config.EXPECTIMAX_DEPTH,
                  params=None, planned_tactic=None):
    """
    Returns (best_tactic, value, {tactic: q_value}, nodes_evaluated).
    `snapshot` comes from PlayerModel.snapshot(); `recent_tactics` are tactic
    names of the last scam messages (oldest first).
    """
    params = params or UtilityParams()
    recent = tuple(TACTICS.index(t) for t in recent_tactics[-2:])
    planned_index = TACTICS.index(planned_tactic) if planned_tactic in TACTICS else None
    counter = [0]
    qvals = {TACTICS[i]: _q_value(i, snapshot, recent, depth, params, counter, planned_index)
             for i in _legal(recent, params)}
    best_value = max(qvals.values())
    best = [t for t, v in qvals.items() if abs(v - best_value) < 1e-9]
    return best, best_value, qvals, counter[0]
