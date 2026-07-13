"""Interactive ROI calibration: click 4 points per route (and optionally 4
more for a queue zone) on the first frame of a video/webcam/image, then save
to a rois.json usable by detect.py.

NOTE: requires a real display and real footage of the target intersection --
it can't be exercised in this environment (no camera, no GUI session
available here). Verify manually once you have footage:

    python calibrate_rois.py --source path/to/intersection.mp4 --output ../config/rois.json

Controls: click 4 points to trace each polygon (in order), then press any key
to continue to the next one. Press 'r' before the 4th click to restart the
current polygon. Press 'q' to abort without saving.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from detector.roi import Route  # noqa: E402  (after sys.path setup)

WINDOW_NAME = "ROI calibration"


def grab_first_frame(source: str):
    if os.path.splitext(source)[1].lower() in (".jpg", ".jpeg", ".png", ".bmp"):
        frame = cv2.imread(source)
        if frame is None:
            sys.exit(f"Could not read image: {source}")
        return frame

    cap_source = int(source) if source.isdigit() else source
    cap = cv2.VideoCapture(cap_source)
    if not cap.isOpened():
        sys.exit(f"Could not open video source: {source}")
    ret, frame = cap.read()
    cap.release()
    if not ret:
        sys.exit(f"Could not read a frame from source: {source}")
    return frame


def click_polygon(base_frame, label: str) -> list[list[int]]:
    points: list[list[int]] = []
    display = base_frame.copy()

    def on_mouse(event, x, y, flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
            points.append([x, y])

    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse)

    print(f"[calibrate] Click 4 points for: {label}  (r=restart, q=abort)")
    while True:
        display = base_frame.copy()
        for i, p in enumerate(points):
            cv2.circle(display, tuple(p), 5, (0, 0, 255), -1)
            if i > 0:
                cv2.line(display, tuple(points[i - 1]), tuple(p), (0, 255, 0), 2)
        if len(points) == 4:
            cv2.line(display, tuple(points[3]), tuple(points[0]), (0, 255, 0), 2)
        cv2.putText(display, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.imshow(WINDOW_NAME, display)

        key = cv2.waitKey(30) & 0xFF
        if key == ord("q"):
            cv2.destroyAllWindows()
            sys.exit("Aborted by user.")
        if key == ord("r"):
            points.clear()
        elif len(points) == 4 and key != 0xFF:
            # any other keypress once the 4th point is placed confirms the polygon
            break
    return points


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="video/webcam/image to calibrate against")
    parser.add_argument("--output", default="../config/rois.json")
    parser.add_argument(
        "--routes", default="route_1,route_2,route_3,route_4", help="comma-separated route names"
    )
    parser.add_argument(
        "--with-queue-zones",
        action="store_true",
        help="also calibrate a smaller queue-zone polygon per route",
    )
    args = parser.parse_args()

    frame = grab_first_frame(args.source)
    route_names = [n.strip() for n in args.routes.split(",") if n.strip()]

    routes = []
    for name in route_names:
        polygon = click_polygon(frame, f"{name}: approach polygon")
        queue_zone = None
        if args.with_queue_zones:
            queue_zone = click_polygon(frame, f"{name}: queue zone (near stop line)")
        routes.append(Route(name=name, polygon=polygon, queue_zone=queue_zone))

    cv2.destroyAllWindows()

    data = {
        "routes": [
            {
                "name": r.name,
                "polygon": r.polygon,
                "queue_zone": r.queue_zone,
            }
            for r in routes
        ]
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[calibrate] Wrote {args.output}")


if __name__ == "__main__":
    main()
