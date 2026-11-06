"""Shared data type returned by every attacker."""
from dataclasses import dataclass, field


@dataclass
class AttackChoice:
    tactic: str
    stage: str
    difficulty: int
    value: float = 0.0            # attacker's estimated utility (for logging)
    planned_tactic: str = None    # what the A* plan suggested for this stage
    info: dict = field(default_factory=dict)
