"""YOLOv8-based vehicle detection: runs Ultralytics YOLO inference, maps COCO
class ids to the traffic-relevant vehicle categories, and applies a
best-effort color heuristic to flag likely ambulances.

NOTE on the ambulance heuristic: YOLOv8's pretrained COCO weights have no
"ambulance" class. This heuristic (looks for a car/bus/truck detection whose
crop is mostly white with a meaningful patch of red, typical of ambulance
livery) is a rough placeholder, not a real classifier -- expect false
positives/negatives. A production system needs a custom-trained head or a
dedicated logo/livery detector.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from ultralytics import YOLO

# COCO class id -> our vehicle category name
COCO_VEHICLE_CLASSES = {
    2: "car",
    3: "bike",  # motorcycle
    5: "bus",
    7: "truck",
}


@dataclass
class Detection:
    cls_name: str
    conf: float
    xyxy: tuple[float, float, float, float]
    track_id: int | None = None
    is_ambulance: bool = False

    @property
    def centroid(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.xyxy
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


class VehicleDetector:
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf: float = 0.35,
        ambulance_heuristic: bool = True,
    ):
        self.model = YOLO(model_path)
        self.conf = conf
        self.ambulance_heuristic = ambulance_heuristic
        self.class_ids = list(COCO_VEHICLE_CLASSES.keys())

    def detect(self, frame: np.ndarray) -> list[Detection]:
        results = self.model.predict(
            frame, classes=self.class_ids, conf=self.conf, verbose=False
        )[0]
        detections = self.results_to_detections(results)
        if self.ambulance_heuristic:
            self.apply_ambulance_heuristic(frame, detections)
        return detections

    def results_to_detections(self, results) -> list[Detection]:
        detections = []
        boxes = results.boxes
        if boxes is None:
            return detections
        ids = boxes.id.cpu().numpy() if boxes.id is not None else [None] * len(boxes)
        for box, cls_id, conf, track_id in zip(
            boxes.xyxy.cpu().numpy(), boxes.cls.cpu().numpy(), boxes.conf.cpu().numpy(), ids
        ):
            cls_name = COCO_VEHICLE_CLASSES.get(int(cls_id))
            if cls_name is None:
                continue
            detections.append(
                Detection(
                    cls_name=cls_name,
                    conf=float(conf),
                    xyxy=tuple(float(v) for v in box),
                    track_id=int(track_id) if track_id is not None else None,
                )
            )
        return detections

    def apply_ambulance_heuristic(self, frame: np.ndarray, detections: list[Detection]) -> None:
        h, w = frame.shape[:2]
        for det in detections:
            if det.cls_name not in ("car", "bus", "truck"):
                continue
            x1, y1, x2, y2 = (int(max(0, v)) for v in det.xyxy)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                continue
            crop = frame[y1:y2, x1:x2]
            if self.is_ambulance_crop(crop):
                det.is_ambulance = True
                det.cls_name = "ambulance"

    @staticmethod
    def is_ambulance_crop(
        bgr_crop: np.ndarray,
        white_frac_threshold: float = 0.35,
        red_frac_threshold: float = 0.03,
    ) -> bool:
        """Best-effort heuristic: a vehicle crop that's mostly white with a
        meaningful patch of red is flagged as a likely ambulance. Placeholder
        only -- see module docstring."""
        if bgr_crop.size == 0:
            return False
        hsv = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2HSV)
        total = hsv.shape[0] * hsv.shape[1]

        white_mask = cv2.inRange(hsv, (0, 0, 150), (180, 60, 255))
        white_frac = float(np.count_nonzero(white_mask)) / total

        red_mask_low = cv2.inRange(hsv, (0, 70, 60), (10, 255, 255))
        red_mask_high = cv2.inRange(hsv, (170, 70, 60), (180, 255, 255))
        red_frac = float(np.count_nonzero(red_mask_low) + np.count_nonzero(red_mask_high)) / total

        return white_frac >= white_frac_threshold and red_frac >= red_frac_threshold
