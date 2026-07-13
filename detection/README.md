# Phase 2 — YOLOv8 Vehicle Detection Module

Detects and classifies vehicles (car, bus, truck, bike, best-effort
ambulance) per intersection approach ("route") from a camera feed, video
file, or single image, and estimates per-route queue length by tracking
which vehicles have stopped near the stop line. Outputs one JSON object per
frame to stdout or a file (JSON Lines).

This module is standalone — it doesn't depend on `simulation/`. In the SUMO
simulation, later phases get ground-truth counts directly via TraCI; this
detector's purpose is real camera input (and eventual edge deployment in
Phase 6).

## Status / limitations

- **Validated so far**: classification + counting on a single bundled sample
  image only (no real intersection footage available in this environment).
- **Not yet validated end-to-end**: multi-frame tracking, queue-length
  estimation, and ROI calibration all require real video/webcam footage of an
  actual intersection, which wasn't available when this was built. The code
  supports all of it — point it at real footage and it should work — but
  treat that path as untested until you've run it yourself.
- **Ambulance detection is a heuristic, not a real classifier.** YOLOv8's
  pretrained COCO weights have no "ambulance" class. `VehicleDetector`
  flags a car/bus/truck detection as a likely ambulance if its crop is mostly
  white with a meaningful patch of red (typical ambulance livery). Expect
  false positives (e.g. white vans, red cars) and false negatives (ambulances
  with different liveries). Replacing this with a fine-tuned classifier or a
  dedicated logo detector is future work — the spec itself marks full
  emergency-vehicle handling as a bonus feature.

## Setup

Uses the same shared venv as Phase 1:

```
.venv\Scripts\pip install -r detection\requirements.txt
```

This pulls in `ultralytics` (and its `torch` dependency — a large, one-time
download). The `yolov8n.pt` weights (~6MB, chosen for CPU/edge latency) are
downloaded automatically on first use via Ultralytics' own mechanism.

## Smoke test (no real footage needed)

```
.venv\Scripts\python detection\scripts\detect.py --source <path-to-bus.jpg> --output detection\outputs\smoke.json
```

Ultralytics ships a sample image containing a bus at
`<venv>\Lib\site-packages\ultralytics\assets\bus.jpg`. With no `--rois`
passed, the whole image is treated as a single unnamed route
(`"full_frame"`) — this only exercises detection + classification, not
routing/tracking/queue-length (those need multiple frames of real footage).

Note: the printed latency on a single invocation includes a one-time ~5s
PyTorch warmup on the first inference call in a fresh process — not
representative of steady-state performance. Measured on this dev machine
(CPU), steady-state inference after warmup is ~260ms/frame, comfortably
within the spec's 2s detection-to-decision budget for the video/webcam path,
where the process stays warm across frames.

## Running against real video or a webcam

1. Calibrate the 4 approach ROIs once against your footage:
   ```
   .venv\Scripts\python detection\scripts\calibrate_rois.py --source path\to\intersection.mp4 --output detection\config\rois.json --with-queue-zones
   ```
   Click 4 points per route polygon (and, with `--with-queue-zones`, 4 more
   for a smaller zone near the stop line used for queue-length estimation).
   See `config/rois.example.json` for the file format.

2. Run detection:
   ```
   .venv\Scripts\python detection\scripts\detect.py --source path\to\intersection.mp4 --rois detection\config\rois.json --output detection\outputs\run.jsonl
   ```
   Use `--source 0` for a webcam. `--stride N` processes every Nth frame if
   you need to trade latency for throughput.

## Output format

One JSON object per line:

```json
{"timestamp": 12.3, "frame": 369, "routes": {
  "route_1_north": {"counts": {"car": 3, "bus": 0, "truck": 1, "bike": 0, "ambulance": 0}, "total": 4, "queue_length": 2},
  "...": "..."
}}
```

`queue_length` is `null` for a route with no calibrated queue zone (including
the `full_frame` fallback used in the smoke test), and for single-image input
in general (queue estimation needs multiple frames of tracking).
