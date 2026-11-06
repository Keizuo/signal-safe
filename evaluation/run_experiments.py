"""
Run simulated-player experiments and write CSVs for the paper.

Two experiments (same seeds across conditions => paired comparison):
  A_learning : bots that LEARN from feedback (learn_rate 0.12), 8 profiles.
               Measures player improvement. True improvement is the drop in the
               bot's real vulnerability on a fixed-difficulty post-test.
  B_static   : bots that never learn, 6 profiles with one weak tactic.
               Measures how fast each attacker's model finds the weak tactic.

Usage:  python -m evaluation.run_experiments [--sessions 20] [--rounds 40] [--quick] [--save-rounds]
Outputs (results/): simulation_sessions.csv (one row per session), simulation_summary.csv
(means/sd per condition), simulation_curves.csv (per-round curves for plots) and,
with --save-rounds, simulation_rounds.csv (every round, large).

Why 40 rounds by default? With ~14 scam messages spread over 6 tactics (a 20-round
human session) there is simply too little evidence to tell which tactic is the weak
one, for ANY attacker. See evaluation/sweep_rounds.py for the session-length sweep.
"""
import argparse
import csv
import time
from pathlib import Path
from collections import defaultdict
from statistics import mean, stdev

from agents.factory import ATTACKER_TYPES, make_attacker
from config import RESULTS_DIR, TACTICS
from evaluation.metrics import session_metrics, welch
from evaluation.simulated_players import PROFILES, SENSITIVE_PROFILES, SimulatedPlayer
from game.scenarios import ScenarioBank
import random

EXPERIMENTS = {
    "A_learning": {"learn_rate": 0.12, "profiles": list(PROFILES)},
    "B_static": {"learn_rate": 0.0, "profiles": list(SENSITIVE_PROFILES)},
}
BASELINE = "scripted"


def run_session(condition, profile, seed, rounds, learn_rate, bank):
    from game.session import Session
    attacker = make_attacker(condition, seed)
    bot = SimulatedPlayer(profile, random.Random(f"bot-{profile}-{seed}"), learn_rate)
    session = Session(attacker, rounds=rounds, seed=seed, bank=bank, agent_type=condition,
                      player_id=profile, session_id=f"{condition}-{profile}-{seed}")
    while True:
        scenario = session.next_scenario()
        if scenario is None:
            break
        action, rt = bot.respond(scenario)
        session.submit(action, rt)
        bot.learn(scenario, action)
    m = session_metrics(session.records, bot.weak_tactic, rounds)
    m["posttest_drop"] = bot.initial_posttest - bot.posttest()
    return session.records, m


def run_all(sessions, rounds, keep_rounds=False):
    bank = ScenarioBank()
    session_rows, round_rows = [], []
    curves = defaultdict(lambda: {"scams": 0, "falls": 0, "sessions": 0, "identified": 0,
                                  "weak_sessions": 0, "difficulty": 0.0})
    for exp, cfg in EXPERIMENTS.items():
        for profile in cfg["profiles"]:
            for condition in ATTACKER_TYPES:
                for k in range(sessions):
                    seed = 1000 * (k + 1) + hash_profile(profile)
                    records, m = run_session(condition, profile, seed, rounds,
                                             cfg["learn_rate"], bank)
                    session_rows.append({"experiment": exp, "condition": condition,
                                         "profile": profile, "seed": seed, **m})
                    weak = SENSITIVE_PROFILES.get(profile, {}).get("weak")
                    for r in records:
                        c = curves[(exp, condition, r["round"])]
                        c["sessions"] += 1
                        if r["is_scam"]:
                            c["scams"] += 1
                            c["falls"] += int(r["fell_for"])
                            c["difficulty"] += r["difficulty"]
                        if weak:
                            c["weak_sessions"] += 1
                            c["identified"] += int(r["top_belief"] == weak)
                        if keep_rounds:
                            round_rows.append({"experiment": exp, "condition": condition,
                                               "profile": profile, "seed": seed, **r})
    curve_rows = [{"experiment": e, "condition": c, "round": r,
                   "fall_rate": round(v["falls"] / v["scams"], 4) if v["scams"] else "",
                   "mean_difficulty": round(v["difficulty"] / v["scams"], 3) if v["scams"] else "",
                   "identified_fraction": round(v["identified"] / v["weak_sessions"], 4)
                   if v["weak_sessions"] else ""}
                  for (e, c, r), v in sorted(curves.items())]
    return session_rows, round_rows, curve_rows


def hash_profile(name):
    return sum(ord(c) for c in name) % 997    # stable small offset, same for all conditions


def write_csv(path, rows):
    if not rows:
        return
    keys = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def aggregate(session_rows):
    """Mean / sd / n per (experiment, condition, metric)."""
    groups = defaultdict(list)
    for r in session_rows:
        groups[(r["experiment"], r["condition"])].append(r)
    out = []
    metrics = ["fall_rate", "scam_detection_rate", "false_alarm_rate", "d_prime", "score",
               "improvement", "posttest_drop", "mean_difficulty", "weak_share",
               "stable_id_round", "first_id_round", "identified"]
    for (exp, cond), rows in groups.items():
        row = {"experiment": exp, "condition": cond, "n_sessions": len(rows)}
        for m in metrics:
            vals = [float(r[m]) for r in rows if m in r and r[m] not in ("", None)]
            if vals:
                row[f"{m}_mean"] = round(mean(vals), 4)
                row[f"{m}_sd"] = round(stdev(vals), 4) if len(vals) > 1 else 0.0
        out.append(row)
    return out


def print_report(session_rows, agg):
    def table(exp, cols):
        print(f"\n=== {exp} ===")
        print(f"{'condition':18}" + "".join(f"{c:>16}" for c in cols))
        for cond in ATTACKER_TYPES:
            row = next(r for r in agg if r["experiment"] == exp and r["condition"] == cond)
            print(f"{cond:18}" + "".join(f"{row.get(c + '_mean', float('nan')):16.3f}" for c in cols))

    table("A_learning", ["posttest_drop", "improvement", "fall_rate", "scam_detection_rate",
                         "false_alarm_rate", "d_prime"])
    table("B_static", ["stable_id_round", "identified", "weak_share", "fall_rate"])

    def col(exp, cond, metric):
        return [float(r[metric]) for r in session_rows
                if r["experiment"] == exp and r["condition"] == cond]

    print(f"\n=== Paired-seed comparisons vs '{BASELINE}' (Welch t, normal-approx p) ===")
    checks = [("A_learning", "posttest_drop", "higher = more real improvement"),
              ("A_learning", "false_alarm_rate", "should not rise"),
              ("B_static", "stable_id_round", "lower = faster identification")]
    for exp, metric, note in checks:
        print(f"-- {exp} / {metric}  ({note})")
        for cond in ATTACKER_TYPES:
            if cond == BASELINE:
                continue
            s = welch(col(exp, cond, metric), col(exp, BASELINE, metric))
            print(f"   {cond:18} diff={s['diff']:+.3f}  t={s['t']:+.2f}  p={s['p']:.4f}  d={s['d']:+.2f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=int, default=20, help="sessions per condition per profile")
    parser.add_argument("--rounds", type=int, default=40)
    parser.add_argument("--quick", action="store_true", help="3 sessions, for a fast check")
    parser.add_argument("--out", default=str(RESULTS_DIR), help="output folder")
    parser.add_argument("--save-rounds", action="store_true", help="also write every round (large file)")
    args = parser.parse_args()
    sessions = 3 if args.quick else args.sessions

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    session_rows, round_rows, curve_rows = run_all(sessions, args.rounds, args.save_rounds)
    agg = aggregate(session_rows)
    write_csv(out / "simulation_sessions.csv", session_rows)
    write_csv(out / "simulation_summary.csv", agg)
    write_csv(out / "simulation_curves.csv", curve_rows)
    if args.save_rounds:
        write_csv(out / "simulation_rounds.csv", round_rows)
    print(f"{len(session_rows)} sessions x {args.rounds} rounds in {time.time() - t0:.0f}s -> {out}")
    print_report(session_rows, agg)


if __name__ == "__main__":
    main()
