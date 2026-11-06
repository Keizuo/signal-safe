"""
Metrics shared by simulated sessions and real human CSV logs.

All functions take a list of round-record dicts (one session or many).
"""
import csv
import math
from pathlib import Path
from statistics import NormalDist, mean, stdev

from config import LOG_FILE


def _truthy(v):
    return v is True or str(v).lower() == "true"


def d_prime(hits, n_scam, false_alarms, n_legit):
    """Sensitivity d' with a log-linear correction (+0.5 / +1) to avoid infinities."""
    if n_scam == 0 or n_legit == 0:
        return float("nan")
    z = NormalDist().inv_cdf
    return z((hits + 0.5) / (n_scam + 1)) - z((false_alarms + 0.5) / (n_legit + 1))


def session_metrics(rows, weak_tactic=None, total_rounds=None):
    """Metrics for ONE session. `rows` are round dicts in order."""
    scams = [r for r in rows if _truthy(r["is_scam"])]
    legit = [r for r in rows if not _truthy(r["is_scam"])]
    detected = sum(1 for r in scams if r["player_action"] in ("verify", "report"))
    fell = sum(1 for r in scams if r["player_action"] == "trust")
    false_alarms = sum(1 for r in legit if r["player_action"] == "report")
    half = len(scams) // 2
    fall_first = (sum(1 for r in scams[:half] if r["player_action"] == "trust") / half) if half else 0.0
    fall_second = (sum(1 for r in scams[half:] if r["player_action"] == "trust")
                   / max(1, len(scams) - half))
    out = {
        "accuracy": sum(_truthy(r["correct"]) for r in rows) / len(rows),
        "score": sum(int(r["points"]) for r in rows),
        "scam_detection_rate": detected / len(scams) if scams else float("nan"),
        "fall_rate": fell / len(scams) if scams else float("nan"),
        "false_alarm_rate": false_alarms / len(legit) if legit else float("nan"),
        "d_prime": d_prime(detected, len(scams), false_alarms, len(legit)),
        "fall_rate_first_half": fall_first,
        "fall_rate_second_half": fall_second,
        "improvement": fall_first - fall_second,       # positive = fewer falls later
        "mean_difficulty": mean(int(r["difficulty"]) for r in scams) if scams else float("nan"),
        "mean_response_time": mean(float(r["response_time_seconds"] or 0) for r in rows),
    }
    if weak_tactic:
        out.update(identification(rows, weak_tactic, total_rounds or len(rows)))
        out["weak_share"] = (sum(1 for r in scams if r["tactic"] == weak_tactic) / len(scams)
                             if scams else float("nan"))
    return out


def identification(rows, weak_tactic, total_rounds):
    """
    How fast does the attacker's player model single out the true weak tactic?
      first_id  : first round whose belief argmax (strict, no ties) is the weak tactic.
      stable_id : first round from which it stays correct until the session ends.
    Rounds never reaching it are 'censored' and reported as total_rounds + 1.
    """
    scam_rows = [r for r in rows if _truthy(r["is_scam"])]
    tops = [(int(r["round"]), r["top_belief"]) for r in scam_rows]
    first = next((rnd for rnd, top in tops if top == weak_tactic), None)
    stable = None
    for rnd, top in reversed(tops):
        if top == weak_tactic:
            stable = rnd
        else:
            break
    return {
        "first_id_round": first if first is not None else total_rounds + 1,
        "stable_id_round": stable if stable is not None else total_rounds + 1,
        "identified": stable is not None,
    }


def welch(a, b):
    """Welch t-test (normal approximation for the p-value) + Cohen's d. a, b = lists."""
    a = [x for x in a if not math.isnan(x)]
    b = [x for x in b if not math.isnan(x)]
    if len(a) < 2 or len(b) < 2:
        return {"diff": float("nan"), "t": float("nan"), "p": float("nan"), "d": float("nan")}
    ma, mb, va, vb = mean(a), mean(b), stdev(a) ** 2, stdev(b) ** 2
    se = math.sqrt(va / len(a) + vb / len(b))
    t = (ma - mb) / se if se else 0.0
    p = 2 * (1 - NormalDist().cdf(abs(t)))
    pooled = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
    return {"diff": ma - mb, "t": t, "p": p, "d": (ma - mb) / pooled if pooled else 0.0}


def summarize(path=LOG_FILE):
    """Summarize a human-play CSV (one summary per session_id)."""
    path = Path(path)
    if not path.exists():
        print(f"No log found at {path}")
        return
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("Log is empty.")
        return
    by_session = {}
    for r in rows:
        by_session.setdefault((r["session_id"], r["agent_type"]), []).append(r)
    for (sid, agent), rs in by_session.items():
        rs.sort(key=lambda r: int(r["round"]))
        m = session_metrics(rs)
        print(f"session {sid} [{agent}] rounds={len(rs)} accuracy={m['accuracy']:.1%} "
              f"detection={m['scam_detection_rate']:.1%} false_alarms={m['false_alarm_rate']:.1%} "
              f"d'={m['d_prime']:.2f} fall_rate {m['fall_rate_first_half']:.0%}->"
              f"{m['fall_rate_second_half']:.0%} mean_rt={m['mean_response_time']:.1f}s")


if __name__ == "__main__":
    summarize()
