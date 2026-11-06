"""
game/session.py -- ONE place that runs a session, shared by the terminal game,
the Pygame UI and the simulator. (Before, each had its own copy of the logic.)

Who decides what:
  * The ENVIRONMENT (this class) decides whether round k is a scam or a
    legitimate message, using an exact, shuffled schedule. The attacker cannot
    influence the legit/scam mix, so it cannot "game" the false-alarm side.
  * The ATTACKER only chooses the scam's tactic / stage / difficulty.
  * The PLAYER MODEL is owned by the session and updated for EVERY attacker
    type, so beliefs are logged even for baselines (needed for comparison).
"""
import random
import uuid
from collections import Counter

from agents.player_model import PlayerModel
from config import DEFAULT_ROUNDS, LEGIT_FRACTION
from game.game_state import GameState
from game.scenarios import ScenarioBank
from game.scoring import score_action


class Session:
    def __init__(self, attacker, rounds=DEFAULT_ROUNDS, seed=None, bank=None, logger=None,
                 agent_type=None, player_id="human", session_id=None,
                 legit_fraction=LEGIT_FRACTION):
        self.attacker = attacker
        self.bank = bank or ScenarioBank()
        self.logger = logger
        self.agent_type = agent_type or getattr(attacker, "name", "unknown")
        self.player_id = player_id
        self.session_id = session_id or uuid.uuid4().hex[:8]
        self.rng = random.Random(seed)
        self.model = PlayerModel()
        self.state = GameState(rounds)
        self.records = []
        self.template_use = Counter()
        self._current = None

        # Exact number of legit rounds (shuffled) => identical base rate everywhere.
        n_legit = round(rounds * legit_fraction)
        self.schedule = [False] * n_legit + [True] * (rounds - n_legit)   # True = scam
        self.rng.shuffle(self.schedule)

    @property
    def finished(self):
        return self.state.current_round >= self.state.total_rounds

    def next_scenario(self):
        """Return the next message (a dict), or None when the session is over."""
        if self.finished:
            self._current = None
            return None
        is_scam = self.schedule[self.state.current_round]
        choice = None
        if is_scam:
            choice = self.attacker.choose_attack(self.model, self.state)
            scenario = self.bank.pick_scam(choice.tactic, choice.stage, choice.difficulty,
                                           self.rng, self.template_use)
        else:
            scenario = self.bank.pick_legit(self.rng, self.template_use)
        self.template_use[scenario["template_id"]] += 1
        self._current = (scenario, choice)
        return scenario

    def submit(self, action, response_time=0.0):
        """Score the player's action, update beliefs, log, and return the outcome."""
        if self._current is None:
            raise RuntimeError("Call next_scenario() before submit().")
        scenario, choice = self._current
        scored = score_action(scenario, action)

        p_before = self.model.vulnerability(scenario["tactic"]) if scenario["is_scam"] else ""
        if scenario["is_scam"]:
            self.model.update(scenario["tactic"], scored["fell_for"])
        else:
            self.model.update_legit(scored["false_alarm"])

        record = {
            "session_id": self.session_id, "agent_type": self.agent_type,
            "player_id": self.player_id, "round": self.state.current_round + 1,
            "scenario_id": scenario["id"], "template_id": scenario["template_id"],
            "channel": scenario["channel"], "tactic": scenario["tactic"],
            "stage": scenario["stage"],
            "requested_stage": choice.stage if choice else "",
            "difficulty": scenario["difficulty"], "is_scam": scenario["is_scam"],
            "player_action": action, "correct": scored["is_correct"],
            "fell_for": scored["fell_for"], "false_alarm": scored["false_alarm"],
            "points": scored["points"], "response_time_seconds": round(response_time, 3),
            "top_belief": self.model.top_belief() or "",
            "p_fall_before": p_before if p_before == "" else round(p_before, 4),
            "attacker_value": round(choice.value, 4) if choice else "",
        }
        self.attacker.observe(record)
        self.state.record_result({**scored, **record})
        self.records.append({**record, **{f"belief_{t}": b for t, b in self.model.beliefs().items()}})
        if self.logger:
            self.logger.log_round(record, self.model.beliefs())

        return {**scored, "record": record, "feedback_text": feedback_text(scenario)}

    def summary(self):
        s = self.state
        return {"session_id": self.session_id, "agent_type": self.agent_type,
                "score": s.score, "accuracy": s.accuracy,
                "most_challenging_tactic": self.model.most_challenging_tactic()}


def feedback_text(scenario):
    """Plain-language feedback shown after every decision."""
    if scenario["is_scam"]:
        flags = "; ".join(scenario["red_flags"])
        return f"Red flags: {flags}. {scenario['explanation']}"
    cues = "; ".join(scenario["legit_cues"])
    return f"Why this one is legitimate: {cues}. {scenario['explanation']}"
