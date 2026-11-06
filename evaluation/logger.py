"""Append one row per game round to a CSV file."""
import csv
from pathlib import Path

from config import LOG_FILE, TACTICS

FIELDS = [
    "session_id", "agent_type", "player_id", "round", "scenario_id", "template_id",
    "channel", "tactic", "stage", "requested_stage", "difficulty", "is_scam",
    "player_action", "correct", "fell_for", "false_alarm", "points",
    "response_time_seconds", "top_belief", "p_fall_before", "attacker_value",
] + [f"belief_{t}" for t in TACTICS]


class GameLogger:
    def __init__(self, path=LOG_FILE):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log_round(self, record, beliefs):
        row = {field: record.get(field, "") for field in FIELDS}
        for tactic in TACTICS:
            row[f"belief_{tactic}"] = beliefs.get(tactic, 0.5)
        write_header = not self.path.exists() or self.path.stat().st_size == 0
        with self.path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
