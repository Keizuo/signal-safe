"""Terminal version of the game (standard library only)."""
import time

from agents.factory import make_attacker
from config import COMPANY_NAME, DEFAULT_ROUNDS, GAME_TITLE
from evaluation.logger import GameLogger
from game.session import Session


def ask_action(input_fn=input):
    choices = {"1": "trust", "2": "verify", "3": "report", "4": "ignore"}
    print("\n1) Trust / Comply  2) Verify  3) Report  4) Ignore")
    while True:
        answer = input_fn("Your decision (1-4): ").strip()
        if answer in choices:
            return choices[answer]
        print("Please choose 1, 2, 3, or 4.")


def play_cli(rounds=DEFAULT_ROUNDS, agent_type="full", seed=None, player_id="human",
             input_fn=input):
    session = Session(make_attacker(agent_type, seed), rounds=rounds, seed=seed,
                      logger=GameLogger(), agent_type=agent_type, player_id=player_id)
    print(f"\n{GAME_TITLE}\n{COMPANY_NAME}")
    print("All messages and organizations are fictional training scenarios.")

    while True:
        scenario = session.next_scenario()
        if scenario is None:
            break
        print("\n" + "=" * 58)
        print(f"ROUND {session.state.current_round + 1}/{rounds} | {scenario['channel'].upper()}")
        print(f"From: {scenario['sender']}\nSubject: {scenario['subject']}")
        print("-" * 58)
        print(scenario["message"])

        start = time.perf_counter()
        action = ask_action(input_fn)
        elapsed = time.perf_counter() - start

        outcome = session.submit(action, elapsed)
        print(f"\n{outcome['feedback_label']} ({outcome['points']:+} points)")
        print(outcome["feedback_text"])
        print(f"Score: {session.state.score}")

    s = session.summary()
    print("\nSESSION SUMMARY")
    print(f"Score: {s['score']} | Accuracy: {s['accuracy']:.1f}%")
    print(f"CSV log: {session.logger.path}")
    print("Tactic you were most susceptible to (estimated):", s["most_challenging_tactic"])
