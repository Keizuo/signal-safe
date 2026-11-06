"""Launch the game. Use --cli for terminal mode or --pygame for the graphical UI."""
import argparse

from agents.factory import ATTACKER_TYPES


def main():
    parser = argparse.ArgumentParser(description="Signal Safe awareness game")
    parser.add_argument("--cli", action="store_true", help="Run terminal version (default)")
    parser.add_argument("--pygame", action="store_true", help="Run graphical version")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--agent", choices=ATTACKER_TYPES, default="full",
                        help="attacker to play against (use a baseline for the control group)")
    parser.add_argument("--seed", type=int, default=None, help="fix the seed for a repeatable session")
    parser.add_argument("--player-id", default="human", help="participant id written to the log")
    args = parser.parse_args()

    if args.pygame:
        from interface.pygame_ui import run_pygame      # imported lazily: pygame is optional
        run_pygame(args.rounds, args.agent, args.seed, args.player_id)
    else:
        from game.round_manager import play_cli
        play_cli(args.rounds, args.agent, args.seed, args.player_id)


if __name__ == "__main__":
    main()
