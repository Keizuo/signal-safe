"""
Shared configuration for Signal Safe.

Every tunable number lives here so experiments are reproducible and easy to
describe in a methods section ("we set phi = 0.6 and target = 0.35").
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
SCENARIO_FILE = DATA_DIR / "scenarios.json"
LOG_FILE = RESULTS_DIR / "game_logs.csv"

GAME_TITLE = "Signal Safe: Adaptive Inbox Defense"
COMPANY_NAME = "Northstar Creative Labs"   # fictional

# ---- Vocabulary ----------------------------------------------------------
TACTICS = ["urgency", "authority", "reward", "fear", "familiarity", "pretexting"]
ACTIONS = ["trust", "verify", "report", "ignore"]
STAGES = ["rapport", "pretext", "request", "escalation"]   # campaign order

# ---- Session shape -------------------------------------------------------
DEFAULT_ROUNDS = 20
LEGIT_FRACTION = 0.30     # EXACT share of legitimate messages per session
DIFFICULTY_MIN = 1        # 1 = obvious red flags ... 3 = subtle (but present)
DIFFICULTY_MAX = 3
FIXED_DIFFICULTY = 2      # used by non-adaptive-difficulty attackers

# ---- Scoring (points the PLAYER earns) -----------------------------------
SCAM_POINTS = {"report": 10, "verify": 8, "ignore": 3, "trust": -10}
LEGIT_POINTS = {"trust": 10, "verify": 7, "ignore": -2, "report": -5}

# ---- Attacker utility (see agents/expectimax.py for the formula) ---------
#   U = R_FALL*P(fall) + EXPLORE_WEIGHT*sd(P) - REPEAT_PENALTY*repeats
#       - FAIRNESS_WEIGHT*|P(fall) - TARGET_FALL_RATE| + PLAN_BONUS*[matches A* plan]
R_FALL = 1.0
EXPLORE_WEIGHT = 0.5
REPEAT_PENALTY = 0.12
FAIRNESS_WEIGHT = 0.6      # phi: set to 0 for a pure adversary
TARGET_FALL_RATE = 0.35    # teaching sweet spot: challenging but not crushing
PLAN_BONUS = 0.15
DISCOUNT = 0.9
EXPECTIMAX_DEPTH = 3       # number of attacker moves looked ahead
MAX_SAME_TACTIC_STREAK = 2 # fairness: never 3 identical tactics in a row

# ---- A* campaign planner (see agents/astar_planner.py) -------------------
SWITCH_COST = 0.30         # changing tactic mid-campaign hurts coherence
SKIP_COST = 0.90           # skipping a stage costs credibility
MIN_VULNERABILITY = 0.05   # avoids log(0)

# ---- Adaptive difficulty -------------------------------------------------
DIFFICULTY_WINDOW = 5
RAISE_AT = 0.80            # recent accuracy at/above this -> harder
LOWER_AT = 0.45            # recent accuracy at/below this -> easier
