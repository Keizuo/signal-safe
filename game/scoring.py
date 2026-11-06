"""
Scoring rules and the definitions used in the paper.

  fell_for    = TRUST on a scam
  detected    = VERIFY or REPORT on a scam      (signal-detection "hit")
  false_alarm = REPORT on a legitimate message  (signal-detection "false alarm")
  correct     = scam  -> VERIFY or REPORT
                legit -> TRUST or VERIFY

IGNORE is deliberately NOT counted as correct (or as detection): ignoring a
scam is safe but teaches nothing and nobody gets warned. (The first version
counted it as detection, which inflated the detection rate.)
"""
from config import ACTIONS, LEGIT_POINTS, SCAM_POINTS


def score_action(scenario, action):
    if action not in ACTIONS:
        raise ValueError(f"Unknown action: {action}")

    if scenario["is_scam"]:
        correct = action in ("verify", "report")
        return {
            "points": SCAM_POINTS[action],
            "is_correct": correct,
            "fell_for": action == "trust",
            "detected": correct,
            "false_alarm": False,
            "feedback_label": "Good decision" if correct else "Review this decision",
            "explanation_type": "suspicious",
        }

    correct = action in ("trust", "verify")
    return {
        "points": LEGIT_POINTS[action],
        "is_correct": correct,
        "fell_for": False,
        "detected": False,
        "false_alarm": action == "report",
        "feedback_label": "Good decision" if correct else "Review this decision",
        "explanation_type": "legitimate",
    }
