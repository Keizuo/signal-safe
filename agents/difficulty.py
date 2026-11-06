"""
Adaptive difficulty that stays fair.

level 1 = obvious red flags ... level 3 = subtle red flags (never zero flags).
Rules that keep it fair:
  * Moves at most ONE level at a time.
  * Needs at least 3 recent decisions before it reacts.
  * After a change it clears its window, so the next change needs fresh
    evidence (prevents flip-flopping).
  * Raise only when recent accuracy >= RAISE_AT; lower when <= LOWER_AT.
  * Level 3 still shows at least one genuine red flag (checked in the tests).
"""
from collections import deque

from config import DIFFICULTY_MAX, DIFFICULTY_MIN, DIFFICULTY_WINDOW, LOWER_AT, RAISE_AT


class DifficultyController:
    def __init__(self, window=DIFFICULTY_WINDOW, start=DIFFICULTY_MIN):
        self.recent = deque(maxlen=window)
        self.level = start

    def observe(self, is_correct):
        self.recent.append(bool(is_correct))
        if len(self.recent) < 3:
            return
        rate = sum(self.recent) / len(self.recent)
        if rate >= RAISE_AT and self.level < DIFFICULTY_MAX:
            self.level += 1
            self.recent.clear()
        elif rate <= LOWER_AT and self.level > DIFFICULTY_MIN:
            self.level -= 1
            self.recent.clear()

    def recommended_level(self):
        return self.level
