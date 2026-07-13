"""CLI entry point: run YOLOv8 vehicle detection (+ tracking/queue-length for
video/webcam sources) and emit one JSON object per frame/image to stdout or a
file.

Examples:
    # single-image smoke test (no ROI config -> whole frame treated as one route)
    python detect.py --source path/to/bus.jpg --output outputs/smoke.json

    # video file, with calibrated per-route ROIs
    python detect.py --source path/to/intersection.mp4 --rois ../config/rois.json --output outputs/run.jsonl

    # webcam
    python detect.py --source 0 --rois ../config/rois.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from detector.queue_estimator import estimate_queue_lengths
from detector.roi import RoiConfig
from detector.tracker import VehicleTracker
from detector.vehicle_detector import COCO_VEHICLE_CLASSES, Detection, VehicleDetector

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}
LATENCY_BUDGET_S = 2.0  # spec's detection-to-decision latency requirement
DETECTION_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DEFAULT_MODEL_PATH = os.path.join(DETECTION_ROOT, "models", "yolov8n.pt")


def is_image_source(source: str) -> bool:
    return os.path.splitext(source)[1].lower() in IMAGE_EXTENSIONS


def aggregate_routes(
    detections: list[Detection],
    roi_config: RoiConfig,
    queue_lengths: dict[str, int | None] | None,
) -> dict:
    vehicle_categories = list(COCO_VEHICLE_CLASSES.values()) + ["ambulance"]
    routes = {
        route.name: {"counts": {c: 0 for c in vehicle_categories}, "total": 0}
        for route in roi_config.routes
    }
    for det in detections:
        x, y = det.centroid
        route_name = roi_config.route_for_point(x, y)
        if route_name is None:
            continue
        entry = routes[route_name]
        entry["counts"][det.cls_name] = entry["counts"].get(det.cls_name, 0) + 1
        entry["total"] += 1

    for name in routes:
        routes[name]["queue_length"] = queue_lengths.get(name) if queue_lengths else None
    return routes


def run_image(args, out) -> None:
    frame = cv2.imread(args.source)
    if frame is None:
        sys.exit(f"Could not read image: {args.source}")
    h, w = frame.shape[:2]
    roi_config = RoiConfig.load(args.rois) if args.rois else RoiConfig.full_frame(w, h)
    detector = VehicleDetector(
        args.model, conf=args.conf, ambulance_heuristic=not args.no_ambulance_heuristic
    )

    t0 = time.perf_counter()
    detections = detector.detect(frame)
    latency = time.perf_counter() - t0

    routes = aggregate_routes(detections, roi_config, queue_lengths=None)
    record = {"timestamp": 0.0, "frame": 0, "routes": routes}
    out.write(json.dumps(record) + "\n")
    out.flush()
    print(
        f"[detect] {len(detections)} detections, inference latency={latency * 1000:.1f}ms "
        "(includes one-time process warmup; steady-state per-frame latency in video mode is much lower)",
        file=sys.stderr,
    )


def run_video(args, out) -> None:
    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        sys.exit(f"Could not open video source: {args.source}")

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    roi_config = RoiConfig.load(args.rois) if args.rois else RoiConfig.full_frame(w, h)
    detector = VehicleDetector(
        args.model, conf=args.conf, ambulance_heuristic=not args.no_ambulance_heuristic
    )
    tracker = VehicleTracker(detector)

    frame_idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % args.stride == 0:
                t0 = time.perf_counter()
                detections = tracker.track(frame)
                latency = time.perf_counter() - t0

                queue_lengths = estimate_queue_lengths(detections, roi_config, tracker)
                routes = aggregate_routes(detections, roi_config, queue_lengths)
                timestamp = frame_idx / fps if fps > 0 else time.time()
                record = {"timestamp": round(timestamp, 3), "frame": frame_idx, "routes": routes}
                out.write(json.dumps(record) + "\n")
                out.flush()

                if latency > LATENCY_BUDGET_S:
                    print(
                        f"[detect] WARNING frame {frame_idx}: latency {latency:.2f}s "
                        f"exceeds {LATENCY_BUDGET_S}s budget",
                        file=sys.stderr,
                    )
            frame_idx += 1
    finally:
        cap.release()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="image/video file path, or integer webcam index")
    parser.add_argument("--rois", default=None, help="path to a rois.json; default: whole frame as one route")
    parser.add_argument("--output", default=None, help="JSONL output path; default: stdout")
    parser.add_argument("--model", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--stride", type=int, default=1, help="process every Nth frame (video/webcam only)")
    parser.add_argument("--no-ambulance-heuristic", action="store_true")
    args = parser.parse_args()

    out = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
    try:
        if is_image_source(args.source):
            run_image(args, out)
        else:
            run_video(args, out)
    finally:
        if out is not sys.stdout:
            out.close()


if __name__ == "__main__":
    main()
