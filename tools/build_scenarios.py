"""
tools/build_scenarios.py -- builds data/scenarios.json from data/templates/*.json

WHY THIS EXISTS
The original game had only 12 hand-written messages, which meant a 12-round
session showed ALL of them (the "adaptive" agent could only reorder them) and
each tactic had 1-2 examples, so the player model had nothing to learn from.

Now there are 24 scam templates (6 tactics x 4 campaign stages). Each template
has several red flags ("tells") of different obviousness. We render every
template at three difficulty levels:

    difficulty 1 (easy)   -> all tells visible (strength 5)
    difficulty 2 (medium) -> mid-level tells   (strength 3)
    difficulty 3 (hard)   -> only the subtle built-in tell (strength 1)

Every scam keeps at least one real red flag at EVERY difficulty (fairness
floor), and all domains use the reserved ".example" TLD.

Run:  python tools/build_scenarios.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "data" / "templates"
OUT = ROOT / "data" / "scenarios.json"

STRENGTH_FOR_DIFFICULTY = {1: 5, 2: 3, 3: 1}
MARKER = re.compile(r"\[\[(\w+)\]\]")
DEFAULT_SUBJECT = {"chat": "Chat message", "sms": "Text message", "call": "Call transcript"}


def strip_name(text):
    """Messages are written for 'you'; remove the {player_name} placeholder."""
    text = re.sub(r",\s*\{player_name\}", "", text)
    return re.sub(r"\s*\{player_name\}", "", text)


def render_scam(t, difficulty):
    strength = STRENGTH_FOR_DIFFICULTY[difficulty]
    tells = {x["id"]: x for x in t["tells"]}

    def splice(m):
        tell = tells[m.group(1)]
        return tell["text"] if tell["obviousness"] <= strength else ""

    body = strip_name(MARKER.sub(splice, t["body"]))
    flags = [x["flag"] for x in t["tells"] if x["obviousness"] <= strength]
    return {
        "id": f"{t['id']}-D{difficulty}",
        "template_id": t["id"],
        "channel": t["channel"],
        "sender": strip_name(t["sender"]),
        "subject": strip_name(t["subject"]) or DEFAULT_SUBJECT.get(t["channel"], "Message"),
        "message": body,
        "is_scam": True,
        "tactic": t["tactic"],
        "difficulty": difficulty,
        "explanation": t["explanation"],
        "stage": t["stage"],
        "red_flags": flags,
        "legit_cues": [],
        "lookalike_of": "none",
    }


def render_legit(t):
    return {
        "id": t["id"],
        "template_id": t["id"],
        "channel": t["channel"],
        "sender": strip_name(t["sender"]),
        "subject": strip_name(t["subject"]) or DEFAULT_SUBJECT.get(t["channel"], "Message"),
        "message": strip_name(t["body"]),
        "is_scam": False,
        "tactic": "none",
        "difficulty": 1,
        "explanation": t["explanation"],
        "stage": "none",
        "red_flags": [],
        "legit_cues": t["legit_cues"],
        "lookalike_of": t.get("lookalike_of", "none"),
    }


def main():
    scenarios = []
    for path in sorted(TEMPLATE_DIR.glob("*.json")):
        for t in json.loads(path.read_text(encoding="utf-8")):
            if t["is_scam"]:
                scenarios.extend(render_scam(t, d) for d in (1, 2, 3))
            else:
                scenarios.append(render_legit(t))
    OUT.write_text(json.dumps(scenarios, indent=1, ensure_ascii=False), encoding="utf-8")
    n_scam = sum(s["is_scam"] for s in scenarios)
    print(f"Wrote {len(scenarios)} scenarios ({n_scam} scam variants, "
          f"{len(scenarios) - n_scam} legitimate) to {OUT}")


if __name__ == "__main__":
    main()
