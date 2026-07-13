"""Per-route queue-length estimation from tracked detections.

A tracked vehicle counts toward a route's queue if its centroid falls inside
that route's queue-zone polygon and it has been "stopped" (per
VehicleTracker.is_stopped) for the tracker's history window. Routes without a
queue zone configured report queue_length=None (undefined, not zero).
"""
from __future__ import annotations

from .roi import RoiConfig
from .tracker import VehicleTracker
from .vehicle_detector import Detection


def estimate_queue_lengths(
    detections: list[Detection],
    roi_config: RoiConfig,
    tracker: VehicleTracker,
) -> dict[str, int | None]:
    queue_lengths: dict[str, int | None] = {}
    for route in roi_config.routes:
        if route.queue_zone is None:
            queue_lengths[route.name] = None
            continue
        count = 0
        for det in detections:
            if det.track_id is None:
                continue
            x, y = det.centroid
            if route.in_queue_zone(x, y) and tracker.is_stopped(det.track_id):
                count += 1
        queue_lengths[route.name] = count
    return queue_lengths
