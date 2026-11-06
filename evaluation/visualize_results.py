"""
Plots for the paper (needs matplotlib). Run after evaluation.run_experiments.

  results/fig_identification.png  : how fast each attacker's model locks on to the
                                    weak tactic (experiment B).
  results/fig_fall_rate.png       : fall rate per round (experiment A).
  results/fig_weak_share.png      : share of scam messages aimed at the weak tactic.
"""
import csv
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import RESULTS_DIR

ORDER = ["random", "scripted", "greedy", "expectimax", "expectimax_astar", "full", "full_phi0"]


def smooth(vals, k=3):
    out = []
    for i in range(len(vals)):
        window = [v for v in vals[max(0, i - k + 1): i + 1] if v is not None]
        out.append(sum(window) / len(window) if window else None)
    return out


def curve_plot(curves, exp, field, ylabel, title, filename):
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for cond in ORDER:
        pts = sorted((int(r["round"]), float(r[field])) for r in curves
                     if r["experiment"] == exp and r["condition"] == cond and r[field] != "")
        if not pts:
            continue
        xs, ys = zip(*pts)
        style = "-" if cond in ("full", "scripted", "random") else "--"
        ax.plot(xs, smooth(list(ys)), style, label=cond, linewidth=2 if cond == "full" else 1.3)
    ax.set_xlabel("Round")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / filename, dpi=150)
    plt.close(fig)
    print(f"Saved {RESULTS_DIR / filename}")


def main():
    curves_path = RESULTS_DIR / "simulation_curves.csv"
    sessions_path = RESULTS_DIR / "simulation_sessions.csv"
    if not curves_path.exists():
        raise SystemExit("Run python -m evaluation.run_experiments first.")
    curves = list(csv.DictReader(curves_path.open(encoding="utf-8")))
    curve_plot(curves, "B_static", "identified_fraction", "Fraction of sessions",
               "Weak tactic = model's top belief (static bots)", "fig_identification.png")
    curve_plot(curves, "A_learning", "fall_rate", "Fall rate on scams",
               "Fall rate per round (learning bots; smoothed)", "fig_fall_rate.png")

    sessions = list(csv.DictReader(sessions_path.open(encoding="utf-8")))
    share = defaultdict(list)
    for r in sessions:
        if r["experiment"] == "B_static" and r.get("weak_share"):
            share[r["condition"]].append(float(r["weak_share"]))
    fig, ax = plt.subplots(figsize=(7, 4.2))
    names = [c for c in ORDER if c in share]
    ax.bar(names, [sum(share[c]) / len(share[c]) for c in names])
    ax.axhline(1 / 6, color="grey", linestyle=":", label="uniform (1/6)")
    ax.set_ylabel("Share of scam messages using the weak tactic")
    ax.set_title("Practice concentration (static bots)")
    ax.tick_params(axis="x", rotation=30)
    ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "fig_weak_share.png", dpi=150)
    print(f"Saved {RESULTS_DIR / 'fig_weak_share.png'}")


if __name__ == "__main__":
    main()
