"""
How does session length affect how fast each attacker finds the weak tactic?

Runs experiment B (static bots, one hidden weak tactic) at several session
lengths and compares every attacker with the scripted baseline.

Usage:  python -m evaluation.sweep_rounds [--sessions 20]
Output: results/sensitivity_identification.csv
"""
import argparse
import csv
from statistics import mean

from agents.factory import ATTACKER_TYPES
from config import RESULTS_DIR
from evaluation.metrics import welch
from evaluation.run_experiments import BASELINE, EXPERIMENTS, hash_profile, run_session
from game.scenarios import ScenarioBank

LENGTHS = (20, 40, 80)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=int, default=20)
    args = parser.parse_args()
    bank = ScenarioBank()
    cfg = EXPERIMENTS["B_static"]
    rows = []
    for rounds in LENGTHS:
        by_cond = {}
        for cond in ATTACKER_TYPES:
            vals = []
            for profile in cfg["profiles"]:
                for k in range(args.sessions):
                    seed = 1000 * (k + 1) + hash_profile(profile)
                    _, m = run_session(cond, profile, seed, rounds, 0.0, bank)
                    vals.append(m)
            by_cond[cond] = vals
        base = [m["stable_id_round"] for m in by_cond[BASELINE]]
        print(f"\nsession length = {rounds} rounds")
        print(f"{'condition':18}{'stable_id':>10}{'identified':>12}{'weak_share':>12}{'diff':>8}{'p':>8}")
        for cond in ATTACKER_TYPES:
            ms = by_cond[cond]
            ids = [m["stable_id_round"] for m in ms]
            s = welch(ids, base)
            row = {"rounds": rounds, "condition": cond,
                   "stable_id_round": round(mean(ids), 2),
                   "identified_rate": round(mean(float(m["identified"]) for m in ms), 3),
                   "weak_share": round(mean(m["weak_share"] for m in ms), 3),
                   "diff_vs_scripted": round(s["diff"], 2) if cond != BASELINE else "",
                   "p_vs_scripted": round(s["p"], 4) if cond != BASELINE else ""}
            rows.append(row)
            print(f"{cond:18}{row['stable_id_round']:10.2f}{row['identified_rate']:12.3f}"
                  f"{row['weak_share']:12.3f}{row['diff_vs_scripted']!s:>8}{row['p_vs_scripted']!s:>8}")
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / "sensitivity_identification.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
