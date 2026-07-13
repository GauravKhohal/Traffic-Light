"""Multi-frame vehicle tracking via Ultralytics' built-in ByteTrack, used to
estimate per-route queue length (a vehicle that hasn't moved much over the
last ~1s of frames is considered "stopped").
"""
from __future__ import annotations

from collections import deque

import numpy as np

from .vehicle_detector import Detection, VehicleDetector


class VehicleTracker:
    def __init__(self, detector: VehicleDetector, history_len: int = 15):
        self.detector = detector
        self.history_len = history_len
        self._history: dict[int, deque[tuple[float, float]]] = {}

    def track(self, frame: np.ndarray) -> list[Detection]:
        results = self.detector.model.track(
            frame,
            classes=self.detector.class_ids,
            conf=self.detector.conf,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
        )[0]
        detections = self.detector.results_to_detections(results)
        if self.detector.ambulance_heuristic:
            self.detector.apply_ambulance_heuristic(frame, detections)

        seen_ids = set()
        for det in detections:
            if det.track_id is None:
                continue
            seen_ids.add(det.track_id)
            history = self._history.setdefault(det.track_id, deque(maxlen=self.history_len))
            history.append(det.centroid)

        # drop history for tracks that disappeared this frame
        for track_id in list(self._history.keys()):
            if track_id not in seen_ids:
                del self._history[track_id]

        return detections

    def is_stopped(self, track_id: int, pixel_threshold: float = 6.0) -> bool:
        """A track is "stopped" if we have a full history window and its
        centroid hasn't moved more than `pixel_threshold` px within it."""
        history = self._history.get(track_id)
        if history is None or len(history) < self.history_len:
            return False
        xs = [p[0] for p in history]
        ys = [p[1] for p in history]
        spread = max(max(xs) - min(xs), max(ys) - min(ys))
        return spread <= pixel_threshold
