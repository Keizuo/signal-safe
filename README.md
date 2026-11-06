# Signal Safe: Adaptive Phishing Awareness Game

An educational prototype for an Intelligent Agents course. The player is an employee of a **fictional** company
(Northstar Creative Labs) who triages emails, texts, chats and call transcripts. An adaptive AI "attacker" picks
which fictional scam to send next; the inbox is mixed with legitimate messages so over-reporting is penalised too.

**Safety scope.** All companies, people and domains are fictional (every domain ends in the reserved `.example`
TLD; the loader rejects anything that looks like a real domain). No payloads, no working links, no real brands.
The agent *selects* from pre-written messages; it never generates operational phishing text. Every scam keeps at
least one genuine red flag at every difficulty level.

## Quick start

```bash
python main.py --cli                       # terminal game (standard library only)
pip install -r requirements.txt            # optional: pygame + matplotlib
python main.py --pygame                    # graphical game
python main.py --cli --agent scripted      # control-group attacker (for a human study)
python -m unittest discover -s tests -v    # 32 tests
python -m evaluation.run_experiments       # simulated-player experiments (~45 s)
python -m evaluation.sweep_rounds          # effect of session length (~1 min)
python -m evaluation.visualize_results     # figures in results/
python -m evaluation.metrics               # summarise human play logs
python tools/build_scenarios.py            # rebuild data/scenarios.json from data/templates/
```

## How it works

```
                 PlayerModel  (Beta(alpha,beta) per tactic; updated after EVERY response)
                  |        |
     A* campaign planner   Expectimax tactic chooser  <-- utility incl. fairness term
     "which STAGE next?"   "which TACTIC now?" (looks 3 moves ahead)
                  \        /
               Difficulty controller  -> how visible the red flags are (1 easy .. 3 hard)
                        |
                 ScenarioBank  -> concrete message  -> Session -> player -> scored, logged
```

| File | Role |
|---|---|
| `game/session.py` | **One** round loop shared by CLI, Pygame and simulator. The *environment* (not the attacker) fixes the exact legit/scam schedule. |
| `game/scenarios.py`, `data/` | 24 scam templates (6 tactics x 4 stages) x 3 difficulties = 72 scam variants, plus 11 legitimate messages |
| `agents/player_model.py` | Beta-Bernoulli belief per tactic + false-alarm tracking, Thompson sampling |
| `agents/expectimax.py` | Real depth-3 expectimax tree (see below) |
| `agents/astar_planner.py` | A* over (stage, tactic) nodes with belief-dependent costs |
| `agents/difficulty.py` | Fair adaptive difficulty |
| `agents/attacker_agent.py`, `baselines.py`, `factory.py` | Adaptive attacker, 3 baselines, 3 ablations |
| `evaluation/` | Logger, learning bots, metrics (d', identification time), experiments, sweep, plots |

### PEAS
- **Performance measure:** expected utility of the attacker's message sequence: chance the player falls for the chosen tactic, plus a curiosity bonus for uncertain tactics, minus repetition, minus a *fairness* penalty for straying from a teachable fall rate.
- **Environment:** simulated workplace inbox (email/SMS/chat/call); partially observable (true vulnerabilities hidden), stochastic, sequential, multi-agent, dynamic (the player learns).
- **Actuators:** choose tactic, campaign stage and difficulty; emit a pre-written message.
- **Sensors:** the player's action (trust/verify/report/ignore), correctness, response time, history.
- **Agent type:** utility-based agent with learning (belief updates = learning; expectimax = utility maximisation; A* = goal-directed planning).

### Utility function (defend this one)
For a message with tactic *a* and belief Beta(alpha, beta), `p` = posterior mean, `sd` = posterior std. dev.:

```
U(a) = R * p  +  E * sd  -  RHO * (uses of a in last 2 msgs)  -  PHI * |p - TARGET|  +  KAPPA * [a == A* planned tactic]
```
`R*p` attacker's goal; `E*sd` explore uncertain tactics; `RHO` stops spamming; **`PHI*|p-TARGET|` is the fairness /
"teaching" term** (target fall rate 0.35; set `PHI=0` for a pure adversary, available as `--agent full_phi0`);
`KAPPA` links expectimax to the A* plan. Hard rule: never the same tactic 3 times in a row.

### Expectimax
MAX nodes = attacker picks a tactic; CHANCE nodes = player falls (prob `p`) or resists (`1-p`); after each outcome the
Beta belief is updated, so deeper levels use the beliefs the attacker *would* hold. `V = max_a [U(a) + gamma * sum_o P(o) V(next)]`,
depth 3, gamma 0.9, ~900 evaluations per decision.

### A* campaign planner
Nodes `(stage, tactic)`; edges go to the next stage or skip one; goal = escalation stage. Cost of entering a node =
`-ln P(fall)` (= -ln(1 - detection risk)) `- ln fit(stage, tactic)` `+ SWITCH` (tactic change) `+ SKIP` (skipped stage).
Heuristic `ceil(stages_left/2) * cheapest_node_cost` is admissible and consistent, so the path is optimal (the tests
compare A* with brute force on random player models). Against a gullible player it plans a long rapport-building
campaign; against a vigilant one it plans a short, blunt one. A detected campaign (player **Reports**) triggers a re-plan.

### Adaptive difficulty (kept fair)
Level 1-3 = how many red flags are visible. Changes by at most one level, needs >= 3 recent decisions, clears its window
after each change (no flip-flopping), and level 3 still always contains a genuine red flag.

### Scoring and definitions
| | Trust | Verify | Report | Ignore |
|---|---:|---:|---:|---:|
| Scam | -10 | +8 | +10 | +3 |
| Legitimate | +10 | +7 | -5 | -2 |

`fell_for` = Trust on a scam. `detected` = Verify/Report on a scam. `false_alarm` = Report on a legit message.
`correct` = scam: Verify/Report; legit: Trust/Verify. **Ignore is not "correct"** (the first version counted it as
detection, which inflated detection rates). Sensitivity is reported as **d'** (log-linear corrected).

## Evaluation

**Conditions** (also ablations): `random`, `scripted` (round-robin), `greedy` (Thompson sampling, no lookahead),
`expectimax` (lookahead only), `expectimax_astar` (+ planner), `full` (+ adaptive difficulty), `full_phi0` (no fairness term).
All use the same seeds, so comparisons are paired. Baselines also maintain a passive player model, so beliefs are logged for every condition.

**Simulated players** (`evaluation/simulated_players.py`): 6 "sensitive" bots (one weak tactic: P(trust)=0.80, others 0.30),
a balanced bot and a "paranoid" bot (reports too much). Visible red flags lower P(trust) (x0.45 / 0.75 / 1.0 for easy / medium / hard).
*Experiment A* bots **learn** from feedback (12% less vulnerable to a practised tactic per exposure; 20% of that transfers to others).
*Experiment B* bots never learn, so the true weak tactic stays fixed and "how fast is it found?" is well defined.
40 rounds, 20 sessions per condition x profile (1,960 sessions).

**Results (seed-paired, Welch t, normal-approx. p; uncorrected).**

*H2 - finding the weak tactic.* Round at which the player model's top belief is the true weak tactic and stays so (lower = faster):

| Session length | scripted | random | greedy | expectimax | exp.+A* | full | full (phi=0) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 20 rounds | 16.97 | 17.86 | 16.84 | 17.23 | 18.02 | 17.74 | 16.48 |
| 40 rounds | 28.93 | 29.50 | 26.28 | 26.45 | 27.69 | **25.58** (p=.046) | **25.42** (p=.032) |
| 80 rounds | 45.11 | 45.31 | 37.63 (p=.024) | 36.38 (p=.007) | 36.99 (p=.016) | 35.23 (p=.003) | 32.01 (p=.0001) |

At 40 rounds the adaptive agents aim 31-38% of scam messages at the weak tactic (baselines: 17%, the uniform rate).

*H1 - player improvement:* **not supported by the simulation.** The learning bots' real post-test improvement is ~0.18 in
*every* condition (all p > 0.69). *H3 - fairness:* false-alarm rate does not change (all p > 0.76); d' is ~2.0 everywhere;
with adaptive difficulty the mean difficulty rises to 2.37 (bots improve) while the fall rate stays ~0.15.

**How to read this honestly (put this in the paper):**
1. The belief-based attackers do find a hidden weakness faster and focus practice on it, but only once a session has enough
   evidence: with ~14 scam messages spread over 6 tactics (a 20-round human session) *no* attacker, adaptive or not, can reliably tell which tactic is weak.
2. The simulated bots learn by a rule *we* wrote that depends only weakly on *which* tactic is practised, so H1 **cannot** be tested with bots.
   It needs human participants: assign `--agent full` vs `--agent scripted`, with a pre-test and post-test.
3. The fairness term costs some identification speed (phi=0 is fastest at 80 rounds): a real accuracy-vs-teachability trade-off worth discussing.
4. Several conditions are compared per metric without multiple-comparison correction. Only the 80-round results survive a Bonferroni threshold (~0.008) for the three strongest conditions.
5. `improvement` (first-half minus second-half fall rate) is confounded by adaptive difficulty (it raises difficulty as players improve), which is why the clean measure is the bot's true post-test vulnerability.

Files in `results/`: `simulation_sessions.csv`, `simulation_summary.csv`, `simulation_curves.csv`, `sensitivity_identification.csv`,
`fig_identification.png`, `fig_fall_rate.png`, `fig_weak_share.png` (add `--save-rounds` for every round). Human play appends to `results/game_logs.csv`.

## Why a game? (for the paper)
Active practice with immediate, specific feedback (the red flags are listed after every decision) rather than passive viewing;
personalised practice (the attacker concentrates on each player's weak tactics); base-rate calibration (the false-alarm penalty teaches
"don't report everything", which a one-sided quiz cannot); repeated exposure under time pressure. Related work to look up and verify yourself:
*Anti-Phishing Phil* (Sheng et al., SOUPS 2007) and *PhishGuru* embedded training (Kumaraguru et al.).

## Known limitations
- Each tactic has 4 scam templates (one per stage), so a tactic used more than 4 times in a session repeats a message (at a different difficulty). Adding more templates per tactic is the best next content step.
- A* costs use hand-set "fit" priors (`STAGE_FIT`) - modelling assumptions, not measured data.
- Simulated results validate the pipeline and the inference speed; they say nothing about human learning.
- Response time is only meaningful for human play (bots use a placeholder).
- For human studies obtain instructor / ethics approval and informed consent; use between-subjects assignment with a pre/post test.
