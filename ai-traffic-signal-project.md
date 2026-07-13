# AI-Based Adaptive Traffic Signal Control System
## Master Prompt + Tech Stack + Architecture

---

## 1. The Master Prompt (copy-paste this to build the project)

> **Role:** You are a senior full-stack + ML engineer. Build an AI-based adaptive traffic signal control system as described below. Work phase by phase, producing runnable code at each phase.
>
> **Project goal:** Build a smart traffic signal system for a network of connected intersections. Each intersection has 4 approach routes. Instead of fixed 30-second green phases, the system dynamically allocates green time per route (between a minimum of 15s and a maximum of 60s, default 30s) based on (a) real-time traffic density detected on each route at this intersection, and (b) predicted incoming traffic reported by neighboring upstream intersections.
>
> **Functional requirements:**
> 1. **Vehicle detection:** Use YOLOv8 on camera feeds (or on pre-recorded traffic videos for the demo) to count vehicles per lane/route, classify them (car, bus, truck, bike, ambulance), and estimate queue length for each of the 4 routes.
> 2. **Dynamic green-time allocation:** Every cycle, compute green time for each route i as:
>    `green_i = clamp(G_min, G_max, G_base × (q_i + α·incoming_i) / mean_queue)`
>    where `q_i` = current queue length on route i, `incoming_i` = vehicles predicted to arrive from upstream signals within the next cycle, `α` = weighting factor (start with 0.5), `G_base` = 30s, `G_min` = 15s, `G_max` = 60s. Renormalize so the total cycle length stays within 90–180s.
> 3. **Fairness / anti-starvation:** No route may wait more than 120 seconds for a green phase, regardless of traffic. Include a max-red-time override.
> 4. **Inter-signal coordination:** Each signal publishes, every 5 seconds, a message containing: its ID, per-route queue lengths, current phase, and estimated outflow per direction (vehicles/minute heading toward each neighbor). Each signal subscribes to its upstream neighbors' topics and uses their outflow + travel time between intersections to compute `incoming_i`. Support "green wave" coordination: if heavy traffic is flowing along a corridor, downstream signals should pre-extend green on that corridor's route.
> 5. **Emergency vehicle priority (bonus):** If an ambulance/fire truck is detected, immediately preempt to give green to its route and notify downstream signals along its predicted path.
> 6. **Safety constraints:** Fixed yellow (4s) and all-red clearance (2s) between phases, never skipped. If detection fails or the network drops, the signal must automatically fall back to the fixed 30s-per-route schedule.
> 7. **Simulation first:** Before any hardware, simulate a grid of 3×3 intersections in SUMO (Simulation of Urban Mobility) controlled via the TraCI Python API. Compare average vehicle waiting time, average queue length, and throughput of (a) fixed-time baseline vs (b) the adaptive algorithm vs (c) an optional RL agent.
> 8. **Reinforcement learning (advanced phase):** Train a DQN or PPO agent per intersection (state = queue lengths + incoming predictions + current phase + time in phase; action = extend current phase or switch; reward = negative sum of waiting times). Use Stable-Baselines3 with the SUMO environment.
> 9. **Dashboard:** A React web dashboard showing a live map of intersections, per-route queue lengths, current phase and countdown for each signal, historical charts of wait times, and a manual override button per signal.
>
> **Non-functional requirements:** detection-to-decision latency under 2 seconds; each intersection controller must run standalone on edge hardware (Raspberry Pi / Jetson class); all signal-to-signal messages over MQTT with QoS 1; log all decisions to a time-series database for auditing.
>
> **Deliverables:** (1) SUMO simulation package with baseline + adaptive controller, (2) YOLO-based detection module that outputs per-route counts as JSON, (3) MQTT-based coordination service, (4) FastAPI backend + React dashboard, (5) evaluation report comparing wait times across the three strategies, (6) README with setup instructions.
>
> Start with Phase 1 (SUMO simulation with a fixed-time baseline) and ask me before moving to each next phase.

---

## 2. Recommended Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Vehicle detection | Python, OpenCV, YOLOv8 (Ultralytics) | Real-time, pre-trained on vehicles, runs on edge GPUs |
| Traffic simulation | SUMO + TraCI Python API | Industry-standard, lets you test without real roads |
| Adaptive logic / RL | Python; Stable-Baselines3 (DQN/PPO), Gymnasium | Well-documented RL on top of SUMO |
| Signal-to-signal messaging | MQTT (Eclipse Mosquitto broker) | Lightweight pub/sub, ideal for IoT/edge devices |
| Backend API | FastAPI (Python) | Async, easy WebSocket support, same language as ML code |
| Real-time state | Redis | Fast per-intersection state cache |
| Historical data | PostgreSQL + TimescaleDB | Time-series logging of queues, decisions, wait times |
| Dashboard | React + Tailwind, Leaflet (map), Recharts, WebSockets | Live intersection map and metrics |
| Edge hardware (real deployment) | Raspberry Pi 5 or NVIDIA Jetson Nano/Orin + IP camera | Runs YOLO + controller at the intersection |
| Deployment | Docker + docker-compose | One-command startup of broker, backend, DB, simulator |

---

## 3. System Architecture

**Layer 1 — Edge node (one per intersection):**
Camera → YOLOv8 detection → vehicle counter (per route) → local adaptive controller → signal driver (relays/LEDs in real life, TraCI in simulation). The controller works even if the network is down (falls back to local-only adaptation, then to fixed timing if detection also fails).

**Layer 2 — Communication:**
Each edge node publishes to MQTT topics like `signals/{signal_id}/state` every 5s: `{queues: [12, 3, 7, 5], phase: 2, outflow: {north: 14, east: 6, ...}}`. Each node subscribes to its upstream neighbors' topics. Travel time between intersections converts a neighbor's outflow into "vehicles arriving at my route i in the next N seconds."

**Layer 3 — Central coordinator (optional but recommended):**
Subscribes to all signals, detects corridor-level patterns (e.g., rush-hour flow east→west), and pushes coordination hints (green-wave offsets) back to signals. Signals treat hints as advice, not commands — local safety logic always wins.

**Layer 4 — Dashboard & storage:**
FastAPI aggregates state from Redis, streams to the React dashboard via WebSockets, and logs everything to TimescaleDB for the evaluation report.

### The core adaptive algorithm (rule-based, Phase 3)

```
every cycle:
    for each route i in [1..4]:
        demand_i = q_i + 0.5 * incoming_i        # local queue + predicted arrivals
    total = sum(demand_i)
    for each route i:
        green_i = 30 * (4 * demand_i / total)     # proportional share of base cycle
        green_i = clamp(15, 60, green_i)
    if any route red-time > 120s: force it next   # anti-starvation
    insert 4s yellow + 2s all-red between phases  # never skipped
```

This directly implements your example: if route 1 has heavy traffic and the others are light, its share grows from 30s toward 50–60s while the others shrink toward 15–20s — and if the upstream signal reports a platoon of vehicles heading your way, the extension happens *before* the queue even forms.

---

## 4. Development Roadmap (6 phases)

1. **Phase 1 – Simulation baseline (1–2 weeks):** Build a 3×3 grid in SUMO with fixed 30s timing. Record average wait time and queue length. This is your benchmark.
2. **Phase 2 – Detection module (1–2 weeks):** YOLOv8 counting vehicles per route from traffic videos; output JSON counts. (In simulation, TraCI gives you counts directly — build this in parallel.)
3. **Phase 3 – Single-intersection adaptation (1 week):** Implement the rule-based algorithm above on one intersection in SUMO. Show wait-time improvement vs baseline.
4. **Phase 4 – Multi-signal coordination (2 weeks):** Add MQTT messaging between intersections, incoming-traffic prediction, and green-wave behavior. Measure corridor-level improvement.
5. **Phase 5 – RL optimization (2–4 weeks, advanced):** Train DQN/PPO agents in SUMO; compare against the rule-based version. Expect ~20–40% wait-time reduction over fixed timing in published literature.
6. **Phase 6 – Dashboard + edge deployment (2 weeks):** React dashboard, Docker packaging, and (optionally) a Raspberry Pi demo with a real camera and LED signal model.

---

## 5. Evaluation Metrics (for your report/demo)

- Average vehicle waiting time per intersection (primary metric)
- Average and max queue length per route
- Network throughput (vehicles completing trips per hour)
- Fairness: max red-wait experienced by any route
- Fallback correctness: behavior when detection/network fails

Compare: **fixed 30s baseline vs adaptive rule-based vs RL** under low, medium, and rush-hour traffic patterns.
