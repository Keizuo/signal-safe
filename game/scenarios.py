"""
Scenario loading, validation and selection.

A *scenario* is one concrete message (a dict). The bank holds many variants:
24 scam templates x 3 difficulty levels + 11 legitimate messages.
"""
import json
import re
from collections import Counter

from config import (DIFFICULTY_MAX, DIFFICULTY_MIN, SCENARIO_FILE, STAGES, TACTICS)

REQUIRED = {"id", "template_id", "channel", "sender", "subject", "message",
            "is_scam", "tactic", "difficulty", "explanation", "stage",
            "red_flags", "legit_cues"}

# Safety check: any domain-like text must use a reserved/fictional ".example" TLD.
REAL_TLD = re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(com|net|org|io|co|gov|edu|info|biz)\b", re.I)


def load_scenarios(path=SCENARIO_FILE):
    with open(path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Scenario file must contain a non-empty list.")
    ids = set()
    for s in scenarios:
        missing = REQUIRED - s.keys()
        if missing:
            raise ValueError(f"{s.get('id', 'unknown')} missing {sorted(missing)}")
        if s["id"] in ids:
            raise ValueError(f"Duplicate scenario id {s['id']}")
        ids.add(s["id"])
        if s["is_scam"]:
            if s["tactic"] not in TACTICS:
                raise ValueError(f"Invalid tactic in {s['id']}")
            if s["stage"] not in STAGES:
                raise ValueError(f"Invalid stage in {s['id']}")
            if not s["red_flags"]:
                raise ValueError(f"{s['id']}: every scam needs >= 1 visible red flag")
        else:
            if s["tactic"] != "none":
                raise ValueError(f"Legitimate scenario {s['id']} must use tactic='none'")
            if not s["legit_cues"]:
                raise ValueError(f"{s['id']}: legitimate message needs legit_cues")
        if s["difficulty"] not in range(DIFFICULTY_MIN, DIFFICULTY_MAX + 1):
            raise ValueError(f"Bad difficulty in {s['id']}")
        text = " ".join([s["sender"], s["subject"], s["message"]])
        if REAL_TLD.search(text):
            raise ValueError(f"{s['id']}: contains a real-looking domain (use .example)")
    return scenarios


class ScenarioBank:
    """Picks concrete scenarios that match what the attacker asked for."""

    def __init__(self, scenarios=None):
        self.scenarios = scenarios if scenarios is not None else load_scenarios()
        self.scams = [s for s in self.scenarios if s["is_scam"]]
        self.legits = [s for s in self.scenarios if not s["is_scam"]]

    def pick_scam(self, tactic, stage, difficulty, rng, template_use=None):
        """
        Rank candidates of the requested tactic by:
          1. freshness + stage match (unused & right stage > unused & other stage
             > reused & right stage > reused),
          2. closeness to the requested difficulty,
          3. a random tie-break (using the session's seeded rng).
        """
        template_use = template_use if template_use is not None else Counter()
        pool = [s for s in self.scams if s["tactic"] == tactic]
        if not pool:
            raise ValueError(f"No scam scenarios for tactic {tactic}")

        def key(s):
            fresh = template_use[s["template_id"]] == 0
            same_stage = s["stage"] == stage
            tier = (0 if fresh else 2) + (0 if same_stage else 1)
            return (tier, abs(s["difficulty"] - difficulty), rng.random())

        return min(pool, key=key)

    def pick_legit(self, rng, template_use=None):
        template_use = template_use if template_use is not None else Counter()
        return min(self.legits, key=lambda s: (template_use[s["template_id"]], rng.random()))
