# Phase 4 Report: Inter-Signal Coordination & Green Wave (row-1 corridor)

One-hour corridor scenario (`demand/corridor.rou.xml`): a heavy
eastbound stream along row 1 (A1->B1->C1, 500 veh/h) with lighter
reverse and north-south cross traffic. The three row-1 signals are
controlled; the other six stay fixed. `fixed` = all signals fixed;
`independent` = A1/B1/C1 adaptive with no messaging; `coordinated` =
A1/B1/C1 adaptive and exchanging state so each predicts incoming
platoons and pre-extends the corridor green. Corridor columns cover
the eastbound (`cor_eb`) vehicles only.

| mode        |   corridor_veh |   eb_travel_s |   eb_timeloss_s |   eb_stops |   net_avg_wait_s |   net_completed |   fallback_cycles |   max_red_s |
|:------------|---------------:|--------------:|----------------:|-----------:|-----------------:|----------------:|------------------:|------------:|
| fixed       |            349 |        396.95 |          339.38 |       3.01 |           186.6  |            1258 |                 0 |           0 |
| independent |            445 |        382.6  |          324.92 |       4.89 |           179.15 |            1358 |                 0 |         114 |
| coordinated |            463 |        278.74 |          220.95 |       3.34 |           159.66 |            1368 |                 0 |         114 |

## What coordination buys (green wave)

The clean measurement is **coordinated vs independent** — same adaptive
controller, only the inter-signal messaging differs:

- Eastbound travel time 382.6s -> 278.74s (-27.1%).
- Stops per eastbound vehicle 4.89 -> 3.34 (-31.7%) — the green wave: a platoon
  cleared at A1 now meets green at B1 and C1 instead of a fresh red.
- Time lost 324.92s -> 220.95s (-32.0%); network-wide average
  wait 179.15s -> 159.66s (-10.9%).

Note the failure mode coordination fixes: *independent* adaptation is
actually worse than fixed timing on stops (each signal green-extends on
its own schedule, so platoons repeatedly catch a fresh red downstream).
Sharing outflow re-aligns the greens.

## vs fixed timing, and a throughput caveat

- Coordinated cleared 463 eastbound vehicles vs fixed's
  349 (+33%) and 1368 network-wide vs 1258 (+9%): fixed timing can't
  discharge the 500 veh/h eastbound demand (a 30s-of-144s phase caps at
  ~375 veh/h) and spills back.
- Coordinated eastbound travel time is still lower than fixed (396.95s -> 278.74s, -29.8%). Fixed's *per-vehicle stop*
  average (3.01) looks low only because it strands ~25% more
  eastbound vehicles in spillback that never complete — its averages
  cover a smaller, luckier subset, so fixed-vs-coordinated stop counts
  aren't comparing the same population.

## Notes

- The green wave is emergent from the demand term: an upstream signal's
  published outflow raises `incoming_i` on the downstream corridor
  approach, so its green grows before the platoon's queue forms.
- Fairness held: cross-street routes stayed within the 120s max-red cap
  (max red seen 114s), and no fallback cycles occurred.
- The same controller and message schema run over MQTT (QoS 1) for edge
  deployment; `scripts/mqtt_smoke.py` validates that path against a live
  broker. Metric runs use the in-process bus for determinism.
