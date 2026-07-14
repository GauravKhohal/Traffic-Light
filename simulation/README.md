# SUMO Simulation — Phase 1 (fixed-time baseline) + Phase 3 (adaptive control)

A 3x3 grid of signalized intersections (9 junctions, each with 4 approaches)
simulated in [SUMO](https://sumo.dlr.de/). Phase 1 runs a fixed-time signal
schedule everywhere: 30s green per approach, 4s yellow, 2s all-red clearance
(144s cycle) — the benchmark. Phase 3 adds a rule-based adaptive controller
on the center intersection (B1) via TraCI and compares it against that
baseline.

## Setup

From the project root (`d:\Traffic light`):

```
python -m venv .venv
.venv\Scripts\pip install -r simulation\requirements.txt
```

Verify the install:

```
.venv\Scripts\python -c "import sumo, traci, sumolib; print('ok')"
```

## Build the network and demand (one-time, already committed)

```
.venv\Scripts\python simulation\network\build_network.py
.venv\Scripts\python simulation\demand\generate_routes.py
```

`build_network.py` generates a 3x3 grid via `netgenerate`, then a `netconvert`
pass that assigns traffic lights to the 9 interior junctions, groups each
phase to a single incoming approach (`--tls.layout incoming`), and bakes in
the fixed 30/4/2s durations natively — no TraCI control needed for this
baseline.

`generate_routes.py` uses SUMO's bundled `randomTrips.py` to create three
demand scenarios over a simulated hour (0-3600s): `low` (period 3.0s,
~1200 vehicles), `medium` (period 1.5s, ~2400 vehicles), `rush` (period 0.7s,
~5100 vehicles).

## Run the baseline and generate the report

```
.venv\Scripts\python simulation\scripts\run_baseline.py
.venv\Scripts\python simulation\scripts\report.py
```

This runs headless SUMO for each scenario, writing raw output (`tripinfo`,
`queue`, `stats`, `summary` XML) to `simulation/outputs/<scenario>/`
(gitignored), then parses those into `simulation/results/metrics_summary.csv`
and `simulation/results/phase1_report.md`.

## Optional: visual sanity check

```
.venv\Scripts\sumo-gui -c simulation\config\baseline.sumocfg
```

Confirms visually that each of the 9 signals cycles 4x(30s green -> 4s yellow
-> 2s all-red) and that traffic flows/queues as expected. Not required for
the automated metrics pipeline above.

## Phase 1 results

Full table in `results/phase1_report.md`. Under heavy (`rush`) demand the
fixed-time baseline saturates — throughput collapses and wait times spike
into the thousands of seconds. That's expected and is exactly the problem
the adaptive controller (Phase 3) and RL agent (Phase 5) are meant to solve.

## Phase 3 — rule-based adaptive control at B1

`controller/adaptive.py` implements the spec's algorithm for one
intersection: per cycle, each route's green is its demand-proportional share
of the base cycle (`green_i = 30 * 4 * demand_i / total_demand`), clamped to
15–60s, capped at the queue's clearance time (~2s/vehicle + startup loss),
and renormalized so the cycle stays within 90–180s. Demand is each route's
halting-vehicle count averaged over the previous cycle (an instantaneous
snapshot systematically under-counts whichever route was served last).
Safety and fairness rules: 4s yellow + 2s all-red between phases, never
skipped; no route waits more than 120s of red — a green is preempted early
if another route is about to breach the cap; and if queue detection fails,
the controller falls back to the fixed 30s schedule for the next cycle.
`incoming_i` (upstream predictions) is plumbed through but zero until the
MQTT coordination of Phase 4.

```
.venv\Scripts\python simulation\controller\test_adaptive.py   # unit tests
.venv\Scripts\python simulation\scripts\run_adaptive.py       # 4 scenarios x fixed/adaptive
.venv\Scripts\python simulation\scripts\report_phase3.py      # comparison report
```

`run_adaptive.py` replays each demand scenario twice through TraCI — all
signals fixed vs B1 adaptive (the other 8 stay fixed) — writing outputs to
`outputs/phase3/` and B1-local metrics (stopped time, queues, max red wait,
vehicles served) alongside. `--break-detection-at 1200` injects a detection
failure mid-run to demonstrate the fixed-time fallback. The `asymmetric`
scenario (`demand/asymmetric.rou.xml`, hand-written flows) converges ~550
veh/h on B1's west approach — beyond fixed timing's ~375 veh/h per-phase
capacity — which is the directional-overload case adaptive control targets.

## Phase 3 results

Full table and interpretation in `results/phase3_report.md`. Headline:
on the `asymmetric` scenario the adaptive signal moves +14% more vehicles
through B1 and cuts network average waiting time by 11% vs fixed timing.
On symmetric random demand (`low`/`medium`) a lone adaptive signal is
slightly worse than fixed — 30s-each-way is already near-optimal there, and
B1's eight fixed neighbors all share identical 144s programs, so a fixed B1
is accidentally coordinated with them; Phase 4's inter-signal coordination
is the remedy. `rush` is over network capacity and gridlocks in both modes.
The 120s max-red fairness cap held in every run.

## Phase 4 — inter-signal coordination and green wave

Adds messaging between signals so each predicts incoming platoons and
pre-extends the corridor green. Every 5s a signal publishes
`{id, queues, phase, outflow}` — `outflow` being veh/min heading toward each
neighbour, measured on its outgoing edges. A downstream signal reads its
upstream neighbours' outflow *toward itself* and predicts arrivals over the
next horizon (`predict_incoming`), feeding the spec's `incoming_i` term into
the same Phase 3 allocation. A heavy upstream platoon raises `incoming_i` on
the corridor approach, so its green grows before the queue forms — the green
wave emerges from the demand formula, no separate offset logic.

`coordination/` holds the transport-agnostic pieces: `topology.py` (each
signal's neighbours, connecting edges, and free-flow travel times from the
net), `predictor.py` (the pure outflow→arrivals prediction), and
`transport.py` with two interchangeable buses — `InProcessBus` (deterministic,
used for metric runs) and `MqttBus` (paho, QoS 1, retained; the real
edge-deployment path). `controller/coordinated.py` subclasses the Phase 3
controller, adding outflow measurement, publishing, and the prediction hook.

```
.venv\Scripts\python simulation\coordination\test_coordination.py  # unit tests
.venv\Scripts\python simulation\scripts\run_coordinated.py         # fixed/independent/coordinated
.venv\Scripts\python simulation\scripts\report_phase4.py           # corridor comparison
```

`run_coordinated.py` runs the corridor scenario (`demand/corridor.rou.xml`:
heavy eastbound flow along row 1 A1→B1→C1 with cross traffic) under three
strategies — all-fixed, the three corridor signals adaptive-but-independent,
and adaptive-and-coordinated — writing to `outputs/phase4/`. `independent`
and `coordinated` share one controller with messaging toggled off/on, so the
difference is purely the coordination term.

### MQTT

The coordination messages run over real MQTT for edge deployment. Start a
broker (Docker) and validate the path:

```
docker run -d --rm --name tl-mosquitto -p 1883:1883 eclipse-mosquitto:2 \
  sh -c "printf 'listener 1883\nallow_anonymous true\n' > /m.conf && exec mosquitto -c /m.conf"
.venv\Scripts\python simulation\scripts\mqtt_smoke.py                        # QoS-1 round-trip + retained
.venv\Scripts\python simulation\scripts\run_coordinated.py --modes coordinated --transport mqtt
```

The metric runs use `InProcessBus` for reproducibility; `--transport mqtt`
proves the identical controller runs over a live broker.

## Phase 4 results

Full table and interpretation in `results/phase4_report.md`. Isolating the
coordination term (coordinated vs independent, same controller): eastbound
corridor travel time −27%, stops per vehicle −32%, network wait −11%.
Independent adaptation alone is actually *worse* than fixed on stops —
platoons cleared at one signal catch a fresh red at the next — which sharing
outflow fixes. Coordinated also clears +33% more eastbound vehicles than
fixed timing, which can't discharge the 500 veh/h corridor demand. The 120s
max-red cap held and no fallback cycles occurred.
