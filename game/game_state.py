"""Session state."""
from dataclasses import dataclass, field

@dataclass
class GameState:
    total_rounds: int
    current_round: int = 0
    score: int = 0
    correct_decisions: int = 0
    incorrect_decisions: int = 0
    history: list = field(default_factory=list)

    @property
    def is_finished(self):
        return self.current_round >= self.total_rounds

    @property
    def accuracy(self):
        n = self.correct_decisions + self.incorrect_decisions
        return 100.0 * self.correct_decisions / n if n else 0.0

    def record_result(self, result):
        self.history.append(result)
        self.current_round += 1
        self.score += result["points"]
        if result["is_correct"]:
            self.correct_decisions += 1
        else:
            self.incorrect_decisions += 1
