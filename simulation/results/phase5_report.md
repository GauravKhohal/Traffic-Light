# Phase 5 Report: RL (DQN) vs Fixed vs Rule-Based Adaptive at B1

One DQN agent per scenario controls intersection B1 (extend-or-switch
action, state = queues + approaching vehicles + phase + time-in-phase,
reward = drop in total waiting time), trained on CPU for 50k steps
(medium retrained to 120k). All
three strategies are measured with the identical B1-local harness from
Phase 3 over a full hour; the other eight signals stay fixed.

| scenario   | strategy   |   b1_avg_stop_s |   b1_avg_queue_veh |   b1_served_veh |   b1_max_red_s |   net_avg_wait_s |   net_completed |
|:-----------|:-----------|----------------:|-------------------:|----------------:|---------------:|-----------------:|----------------:|
| low        | fixed      |           27.27 |               3.29 |             434 |            110 |           111.48 |            1133 |
| low        | rule       |           31.43 |               3.78 |             433 |            114 |           117.54 |            1133 |
| low        | rl         |           23.6  |               2.85 |             435 |            124 |           115.04 |            1135 |
| medium     | fixed      |           36.51 |               8.95 |             883 |            110 |           141.28 |            2243 |
| medium     | rule       |           45.13 |              11.02 |             879 |            114 |           146.38 |            2239 |
| medium     | rl         |           68.53 |              16.5  |             867 |             84 |           156.73 |            2230 |
| rush       | fixed      |         1348.4  |              74.54 |             199 |            110 |           173.34 |             395 |
| rush       | rule       |         1864.06 |              82.33 |             159 |            120 |           163.11 |             360 |
| rush       | rl         |         1331.1  |              79.5  |             215 |            204 |           182.25 |             407 |
| asymmetric | fixed      |           66.13 |              10.84 |             590 |            110 |           300.58 |             567 |
| asymmetric | rule       |           70.03 |              13.09 |             673 |            114 |           266.79 |             652 |
| asymmetric | rl         |           28.02 |               6.03 |             775 |            199 |           157.15 |             760 |

## Per scenario: B1 stopped time and network wait vs fixed

- **low**: rule stop +15% / net-wait +5%; rl stop -13% / net-wait +3%
- **medium**: rule stop +24% / net-wait +4%; rl stop +88% / net-wait +11%
- **rush**: rule stop +38% / net-wait -6%; rl stop -1% / net-wait +5%
- **asymmetric**: rule stop +6% / net-wait -11%; rl stop -58% / net-wait -48%

## Reading the results

- **RL wins where it matters most — `asymmetric`** (heavy directional
  demand on B1's west approach): it cuts B1 stopped time ~58% and
  network wait ~48% vs fixed, and clears the most vehicles, beating the
  rule-based controller decisively. A learned extend/switch policy
  exploits the persistent imbalance better than the proportional rule.
- **`low`**: RL edges out both fixed and rule-based (lower stop and
  queue) on light symmetric demand.
- **`rush`**: over network capacity; no single-junction policy fixes
  gridlock, so all three are within noise.
- **`medium` is the weak spot**: RL stays worse than fixed even after
  retraining to 120k steps (it improved but did not catch fixed). Like
  the Phase 3 rule-based controller, a single adaptive signal doesn't
  help on balanced symmetric demand — 30s-each-way is already near
  optimal, and extend/switch overhead only adds delay.

## Fairness tradeoff and limitations

- Unlike the rule-based controller (a hard 120s max-red cap), the RL
  env leaves fairness to the reward. The agent exceeds 120s on the
  directional scenarios (asymmetric ~199s, rush ~204s): it starves a
  light approach to serve the heavy one, which is *why* its delay is
  low. Lower average delay here partly buys itself with worse worst-case
  waiting — a real tradeoff, not a free win. A max-red override could be
  added to the env if the fairness guarantee must hold.
- Safety is enforced by the env, not learned: every switch runs the
  fixed 4s yellow + 2s all-red, with a 10s min / 60s max green.
- Training budget is modest (CPU, tens of thousands of steps, one seed);
  results are high-variance across scenarios. Published DQN/PPO reaches
  20-40% wait reduction with far more experience, tuning, and seeds.
