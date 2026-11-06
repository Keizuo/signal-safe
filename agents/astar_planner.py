"""
A* planner for a multi-stage campaign.

GRAPH
  A node is (stage, tactic) with stage in rapport < pretext < request < escalation.
  From a node you may move to the next stage, or SKIP one stage. The campaign
  starts at a virtual START node and must reach the ESCALATION stage.

COST of entering node (stage, tactic), given the player model:
    -ln P(fall | tactic)            = -ln(1 - detection risk)  "how likely is this step to be caught?"
    -ln fit(stage, tactic)          "how natural is this tactic at this stage?"
    + SWITCH_COST  if the tactic changed from the previous node (story coherence)
    + SKIP_COST    if a stage was skipped (less rapport built)

  Costs are non-negative and additive, so the cheapest path is the campaign
  with the lowest accumulated detection risk. Against a gullible player a long
  rapport-building path is cheap; against a vigilant one, skipping stages (a
  shorter, blunter campaign) becomes cheaper than paying a detection cost at
  every extra step.

HEURISTIC  h(stage) = ceil(stages_left / 2) * (cheapest possible node cost)
  Admissible: any real path needs at least ceil(stages_left/2) more nodes and
  each costs at least the cheapest node. (Also consistent.) Therefore A*
  returns an OPTIMAL path; tests compare it with brute force.
"""
import heapq
import itertools
import math
from dataclasses import dataclass, field

from config import MIN_VULNERABILITY, SKIP_COST, STAGES, SWITCH_COST, TACTICS

# Prior "naturalness" of a tactic at a stage (0..1). Hand-set, documented assumption.
STAGE_FIT = {
    "rapport":    {"familiarity": 0.95, "pretexting": 0.80, "authority": 0.70,
                   "reward": 0.70, "urgency": 0.35, "fear": 0.30},
    "pretext":    {"pretexting": 0.95, "authority": 0.85, "familiarity": 0.80,
                   "reward": 0.70, "fear": 0.55, "urgency": 0.50},
    "request":    {"urgency": 0.90, "authority": 0.85, "reward": 0.80,
                   "fear": 0.80, "pretexting": 0.80, "familiarity": 0.75},
    "escalation": {"fear": 0.95, "urgency": 0.95, "authority": 0.85,
                   "pretexting": 0.60, "familiarity": 0.50, "reward": 0.50},
}
GOAL = len(STAGES) - 1          # index of the escalation stage


@dataclass
class CampaignPlan:
    path: list = field(default_factory=list)    # [(stage, tactic), ...]
    cost: float = float("inf")
    expanded: int = 0


def node_cost(stage_idx, tactic, vulnerability):
    v = max(MIN_VULNERABILITY, min(1.0, vulnerability[tactic]))
    return -math.log(v) - math.log(STAGE_FIT[STAGES[stage_idx]][tactic])


def edge_cost(prev, node, vulnerability):
    """prev/node are (stage_idx, tactic); prev may be (-1, None) for START."""
    cost = node_cost(node[0], node[1], vulnerability)
    if prev[1] is not None and prev[1] != node[1]:
        cost += SWITCH_COST
    if node[0] - prev[0] == 2:
        cost += SKIP_COST
    return cost


def _successors(node):
    for step in (1, 2):
        s = node[0] + step
        if s <= GOAL:
            for t in TACTICS:
                yield (s, t)


def _heuristic(node, c_min):
    return math.ceil((GOAL - node[0]) / 2) * c_min


def plan_campaign(vulnerability):
    """A* from START to the escalation stage. `vulnerability` = {tactic: P(fall)}."""
    c_min = min(node_cost(s, t, vulnerability) for s in range(len(STAGES)) for t in TACTICS)
    start = (-1, None)
    tie = itertools.count()
    frontier = [(_heuristic(start, c_min), 0.0, next(tie), start, [])]
    best_g = {start: 0.0}
    expanded = 0
    while frontier:
        _, g, _, node, path = heapq.heappop(frontier)
        if g > best_g.get(node, float("inf")) + 1e-12:
            continue
        if node[0] == GOAL:
            return CampaignPlan([(STAGES[s], t) for s, t in path], g, expanded)
        expanded += 1
        for nxt in _successors(node):
            ng = g + edge_cost(node, nxt, vulnerability)
            if ng < best_g.get(nxt, float("inf")) - 1e-12:
                best_g[nxt] = ng
                heapq.heappush(frontier, (ng + _heuristic(nxt, c_min), ng, next(tie),
                                          nxt, path + [nxt]))
    return CampaignPlan()


def brute_force_cost(vulnerability):
    """Exhaustive minimum cost, used only in tests to prove A* is optimal."""
    best = [float("inf")]

    def dfs(node, g):
        if node[0] == GOAL:
            best[0] = min(best[0], g)
            return
        for nxt in _successors(node):
            dfs(nxt, g + edge_cost(node, nxt, vulnerability))

    dfs((-1, None), 0.0)
    return best[0]
