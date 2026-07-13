"""Per-route region-of-interest (ROI) configuration.

Each route (an intersection approach) is defined by a pixel-space polygon in
the camera frame, plus an optional smaller "queue zone" polygon near the stop
line used for queue-length estimation. A detection is assigned to whichever
route's polygon contains its bounding-box centroid.

Real coordinates require calibration against real footage (see
scripts/calibrate_rois.py). When no config is supplied, `RoiConfig.full_frame`
is used: a single unnamed route covering the whole image and no queue zone
(so queue_length is always None) -- this is what the bundled-image smoke test
uses, since it isn't a photo of an intersection.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class Route:
    name: str
    polygon: list[tuple[float, float]]
    queue_zone: list[tuple[float, float]] | None = None

    def _contains(self, polygon: list[tuple[float, float]], x: float, y: float) -> bool:
        pts = np.array(polygon, dtype=np.float32)
        return cv2.pointPolygonTest(pts, (float(x), float(y)), False) >= 0

    def contains(self, x: float, y: float) -> bool:
        return self._contains(self.polygon, x, y)

    def in_queue_zone(self, x: float, y: float) -> bool:
        if self.queue_zone is None:
            return False
        return self._contains(self.queue_zone, x, y)


@dataclass
class RoiConfig:
    routes: list[Route] = field(default_factory=list)

    @classmethod
    def load(cls, path: str) -> "RoiConfig":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        routes = [
            Route(
                name=r["name"],
                polygon=[tuple(p) for p in r["polygon"]],
                queue_zone=[tuple(p) for p in r["queue_zone"]] if r.get("queue_zone") else None,
            )
            for r in data["routes"]
        ]
        return cls(routes=routes)

    @classmethod
    def full_frame(cls, width: int, height: int) -> "RoiConfig":
        polygon = [(0, 0), (width, 0), (width, height), (0, height)]
        return cls(routes=[Route(name="full_frame", polygon=polygon, queue_zone=None)])

    def route_for_point(self, x: float, y: float) -> str | None:
        for route in self.routes:
            if route.contains(x, y):
                return route.name
        return None

    def route_by_name(self, name: str) -> Route | None:
        for route in self.routes:
            if route.name == name:
                return route
        return None
