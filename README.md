# AI-Based Adaptive Traffic Signal Control System

Building this in phases per `ai-traffic-signal-project.md`, checking in before
each new phase.

## Phase status

- [x] **Phase 1 — Simulation baseline**: 3x3 SUMO grid, fixed 30s/4s/2s
      signal timing, wait-time/queue/throughput metrics across low/medium/rush
      demand. See [simulation/README.md](simulation/README.md) for setup and
      run instructions, and `simulation/results/phase1_report.md` for results.
- [x] **Phase 2 — YOLOv8 vehicle detection module**: detects/classifies
      vehicles (car, bus, truck, bike, heuristic ambulance) per route and
      estimates queue length via tracking. See
      [detection/README.md](detection/README.md). Validated so far only on a
      bundled sample image — full video/tracking/queue-length/ROI-calibration
      needs real intersection footage, not available in this environment yet.
- [x] **Phase 3 — Single-intersection rule-based adaptive control**: center
      intersection (B1) driven adaptively via TraCI — demand-proportional
      green allocation (15–60s), 90–180s cycles, 120s max-red fairness cap,
      fixed-time fallback on detection failure. Beats fixed timing where it
      matters (directional overload: +14% throughput, −11% network wait);
      slightly worse under symmetric demand until Phase 4 adds coordination.
      See `simulation/results/phase3_report.md`.
- [x] **Phase 4 — Multi-signal MQTT coordination + green-wave behavior**:
      signals publish per-route queues + outflow every 5s and predict incoming
      platoons from upstream neighbours, folding it into the demand term so the
      corridor green pre-extends (green wave). Transport-agnostic over an
      in-process bus (deterministic metric runs) or real MQTT/QoS-1 (validated
      against a Mosquitto broker). On a heavy corridor, coordination cuts
      eastbound travel time −27% and stops −32% vs uncoordinated adaptive.
      See `simulation/results/phase4_report.md`.
- [x] **Phase 5 — RL optimization (DQN via Stable-Baselines3)**: a Gymnasium
      SUMO env (extend/switch action, queue+incoming+phase state, waiting-time
      reward, env-enforced yellow/all-red safety) trains a DQN per scenario to
      control B1, compared against fixed and the rule-based controller. On
      directional (`asymmetric`) demand RL cuts B1 stopped time ~58% and
      network wait ~48% vs fixed, beating the rule-based controller; it's
      weaker on balanced demand and trades away the strict 120s fairness cap.
      See `simulation/results/phase5_report.md`.
- [x] **Phase 6 — Dashboard + backend + deployment packaging**: a FastAPI
      backend aggregates live signal state (from the Phase 4 MQTT stream, or a
      built-in synthetic demo feed) and streams it over a WebSocket to a React
      + Tailwind + Recharts dashboard — grid map coloured by congestion,
      per-signal phase/countdown/queues, network-wait chart, and a manual
      override per approach. One-command `docker compose up`. Live state is
      in-memory (documented Redis/TimescaleDB swap-in). See
      [dashboard/README.md](dashboard/README.md).

## Layout

```
ai-traffic-signal-project.md   Original spec (master prompt, tech stack, roadmap)
simulation/                    Phases 1+3+4+5: SUMO network, demand, baseline + adaptive + coordinated + RL controllers, reports
detection/                     Phase 2: YOLOv8 vehicle detection, tracking, queue estimation
dashboard/                     Phase 6: FastAPI backend + React dashboard + docker-compose
```

All six phases are complete. See each subdirectory's README for setup and the
`simulation/results/*.md` reports for the fixed vs adaptive vs coordinated vs
RL comparisons.
