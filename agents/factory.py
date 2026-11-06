"""Build an attacker by name (used by the CLI, Pygame UI and experiments)."""
import random

from agents.attacker_agent import AdaptiveAttacker
from agents.baselines import GreedyThompsonAttacker, RandomAttacker, ScriptedAttacker

ATTACKER_TYPES = ["random", "scripted", "greedy", "expectimax",
                  "expectimax_astar", "full", "full_phi0"]


def make_attacker(name, seed=None):
    rng = random.Random(f"{seed}-{name}")        # deterministic per (seed, name)
    if name == "random":
        return RandomAttacker(rng)
    if name == "scripted":
        return ScriptedAttacker(rng)
    if name == "greedy":
        return GreedyThompsonAttacker(rng)
    if name == "expectimax":              # lookahead only
        return AdaptiveAttacker(rng, name, use_astar=False, adaptive_difficulty=False)
    if name == "expectimax_astar":        # + campaign planner
        return AdaptiveAttacker(rng, name, use_astar=True, adaptive_difficulty=False)
    if name == "full":                    # + adaptive difficulty
        return AdaptiveAttacker(rng, name, use_astar=True, adaptive_difficulty=True)
    if name == "full_phi0":               # pure adversary (no fairness term)
        return AdaptiveAttacker(rng, name, use_astar=True, adaptive_difficulty=True, phi=0.0)
    raise ValueError(f"Unknown attacker '{name}'. Choose from {ATTACKER_TYPES}")
