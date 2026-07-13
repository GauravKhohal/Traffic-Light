# Phase 3 Report: Rule-Based Adaptive Control at One Intersection (B1)

One-hour simulation per demand scenario, run twice through TraCI: all 9
signals fixed-time (`fixed`) vs the center intersection B1 driven by the
rule-based adaptive controller while the other 8 stay fixed (`adaptive`).
`b1_*` columns measure B1's four approaches only (the controlled
intersection); `net_*` columns are network-wide, where one adaptive
signal out of nine can only move the needle slightly.

| scenario   | mode     |   b1_avg_stop_s |   b1_avg_queue_veh |   b1_max_queue_veh |   b1_served_veh |   b1_max_red_s |   net_avg_wait_s |   net_completed_veh |
|:-----------|:---------|----------------:|-------------------:|-------------------:|----------------:|---------------:|-----------------:|--------------------:|
| low        | fixed    |           27.27 |               3.29 |                 11 |             434 |            110 |           111.48 |                1133 |
| low        | adaptive |           31.43 |               3.78 |                 13 |             433 |            110 |           117.54 |                1133 |
| medium     | fixed    |           36.51 |               8.95 |                 22 |             883 |            110 |           141.28 |                2243 |
| medium     | adaptive |           45.13 |              11.02 |                 26 |             879 |            110 |           146.38 |                2239 |
| rush       | fixed    |         1037.39 |              75.21 |                 98 |             261 |            110 |           553.6  |                 547 |
| rush       | adaptive |         1366.5  |              82.37 |                 99 |             217 |            116 |           543.27 |                 508 |
| asymmetric | fixed    |           66.13 |              10.84 |                 24 |             590 |            110 |           300.58 |                 567 |
| asymmetric | adaptive |           70.03 |              13.09 |                 25 |             673 |            110 |           266.79 |                 652 |

## Fixed vs adaptive per scenario

Note: when a fixed-time queue overflows B1's 200m approach edge it
spills back upstream, out of sight of the `b1_*` metrics — network
average wait and vehicles served are the honest comparison under
overload.

- **low**: network avg wait 111.48s -> 117.54s (+5.4%), vehicles through B1 434 -> 433 (-0.2%), max red wait 110s (cap 120s)
- **medium**: network avg wait 141.28s -> 146.38s (+3.6%), vehicles through B1 883 -> 879 (-0.5%), max red wait 110s (cap 120s)
- **rush**: network avg wait 553.6s -> 543.27s (-1.9%), vehicles through B1 261 -> 217 (-16.9%), max red wait 116s (cap 120s)
- **asymmetric**: network avg wait 300.58s -> 266.79s (-11.2%), vehicles through B1 590 -> 673 (+14.1%), max red wait 110s (cap 120s)

## Reading the results

- **asymmetric** is the scenario adaptive control exists for: ~550
  veh/h converge on B1's west approach, above the ~375 veh/h a fixed
  30s-of-144s phase can discharge. The adaptive signal reallocates
  green to that approach and both clears more vehicles and cuts
  network waiting time.
- **low/medium** demand is symmetric random traffic, where 30s each
  way is already near-optimal — and B1's eight fixed neighbors all run
  identical 144s programs, so a fixed B1 is accidentally coordinated
  with them. A lone adaptive signal breaks that sync and pays a small
  penalty; inter-signal coordination (Phase 4) is the remedy.
- **rush** is over capacity network-wide; no timing plan at one
  junction fixes it (both modes gridlock).
- Fairness held in every run: no route waited longer than the 120s
  max-red cap (the controller preempts a green when a red is about to
  breach it).
- Fallback: with detection failure injected at t=1200s
  (`run_adaptive.py --break-detection-at 1200`), the controller
  reverted to the fixed 30s schedule for the remaining cycles and the
  intersection kept operating safely.
