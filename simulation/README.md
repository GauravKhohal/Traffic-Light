# Phase 1 — SUMO Fixed-Time Baseline

A 3x3 grid of signalized intersections (9 junctions, each with 4 approaches)
simulated in [SUMO](https://sumo.dlr.de/), running a fixed-time signal
schedule: 30s green per approach, 4s yellow, 2s all-red clearance (144s cycle).
This is the benchmark that later phases (rule-based adaptive control, then
RL) will be compared against.

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

## Results (medium demand shown; full table in `results/phase1_report.md`)

Under heavy (`rush`) demand the fixed-time baseline saturates — throughput
collapses and wait times spike into the thousands of seconds. That's expected
and is exactly the problem the adaptive controller (Phase 3) and RL agent
(Phase 5) are meant to solve.
