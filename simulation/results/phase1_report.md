# Phase 1 Report: Fixed-Time Baseline (3x3 grid, 30s green / 4s yellow / 2s all-red)

One-hour (3600s) simulation per demand scenario. Queue length is a network-wide aggregate (avg/max across all lanes and 10s samples); per-route breakdowns come in later phases alongside the adaptive controller.

| scenario   |   vehicles_completed |   avg_wait_s |   max_wait_s |   avg_queue_m |   max_queue_m |   throughput_veh_per_hour |
|:-----------|---------------------:|-------------:|-------------:|--------------:|--------------:|--------------------------:|
| low        |                 1133 |       111.48 |          373 |         14.54 |         66.35 |                      1133 |
| medium     |                 2243 |       141.28 |          417 |         29.39 |        141.25 |                      2243 |
| rush       |                  547 |       553.6  |         3075 |        105.84 |        149.57 |                       547 |

Average waiting time and average queue length both increase monotonically from low to medium to rush demand, as expected.
