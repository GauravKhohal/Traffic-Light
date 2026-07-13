# AI-Based Adaptive Traffic Signal Control System

Building this in phases per `ai-traffic-signal-project.md`, checking in before
each new phase.

## Phase status

- [x] **Phase 1 — Simulation baseline**: 3x3 SUMO grid, fixed 30s/4s/2s
      signal timing, wait-time/queue/throughput metrics across low/medium/rush
      demand. See [simulation/README.md](simulation/README.md) for setup and
      run instructions, and `simulation/results/phase1_report.md` for results.
- [ ] Phase 2 — YOLOv8 vehicle detection module
- [ ] Phase 3 — Single-intersection rule-based adaptive control
- [ ] Phase 4 — Multi-signal MQTT coordination + green-wave behavior
- [ ] Phase 5 — RL optimization (DQN/PPO via Stable-Baselines3)
- [ ] Phase 6 — Dashboard (React) + edge deployment packaging

## Layout

```
ai-traffic-signal-project.md   Original spec (master prompt, tech stack, roadmap)
simulation/                    Phase 1: SUMO network, demand, baseline runner, report
```
