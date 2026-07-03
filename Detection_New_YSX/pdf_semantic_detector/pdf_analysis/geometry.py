from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence, Tuple

from ..models import BBox


def normalize_bbox(bbox: object) -> Optional[BBox]:
    if bbox is None:
        return None
    if hasattr(bbox, "x0") and hasattr(bbox, "y0") and hasattr(bbox, "x1") and hasattr(bbox, "y1"):
        return (float(bbox.x0), float(bbox.y0), float(bbox.x1), float(bbox.y1))
    if isinstance(bbox, dict):
        keys = {str(k).lower(): v for k, v in bbox.items()}
        if {"x0", "y0", "x1", "y1"}.issubset(keys):
            return (float(keys["x0"]), float(keys["y0"]), float(keys["x1"]), float(keys["y1"]))
        if {"x1", "y1", "x2", "y2"}.issubset(keys):
            return (float(keys["x1"]), float(keys["y1"]), float(keys["x2"]), float(keys["y2"]))
    if isinstance(bbox, (list, tuple)):
        if len(bbox) == 4 and all(isinstance(v, (int, float)) for v in bbox):
            x0, y0, x1, y1 = bbox
            return (float(x0), float(y0), float(x1), float(y1))
        if len(bbox) >= 2 and all(isinstance(p, (list, tuple)) and len(p) >= 2 for p in bbox):
            xs = [float(p[0]) for p in bbox]
            ys = [float(p[1]) for p in bbox]
            return (min(xs), min(ys), max(xs), max(ys))
    return None


def bbox_area(bbox: BBox) -> float:
    x0, y0, x1, y1 = bbox
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def bbox_intersection(a: BBox, b: BBox) -> Optional[BBox]:
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def bbox_iou(a: BBox, b: BBox) -> float:
    inter = bbox_intersection(a, b)
    if inter is None:
        return 0.0
    inter_area = bbox_area(inter)
    denom = bbox_area(a) + bbox_area(b) - inter_area
    return inter_area / denom if denom > 0 else 0.0


def overlap_ratio(inner: BBox, cover: BBox) -> float:
    inter = bbox_intersection(inner, cover)
    if inter is None:
        return 0.0
    area = bbox_area(inner)
    return bbox_area(inter) / area if area > 0 else 0.0


def union_bbox(boxes: Iterable[BBox]) -> Optional[BBox]:
    boxes = list(boxes)
    if not boxes:
        return None
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def bbox_center_distance(a: BBox, b: BBox) -> float:
    acx = (a[0] + a[2]) / 2.0
    acy = (a[1] + a[3]) / 2.0
    bcx = (b[0] + b[2]) / 2.0
    bcy = (b[1] + b[3]) / 2.0
    return math.hypot(acx - bcx, acy - bcy)


def page_overlap_status(bbox: BBox, page_bbox: BBox) -> str:
    if bbox_area(bbox) <= 0:
        return "zero_area"
    inter = bbox_intersection(bbox, page_bbox)
    if inter is None:
        return "outside"
    ratio = bbox_area(inter) / max(bbox_area(bbox), 1e-9)
    if ratio < 0.98:
        return "partial"
    return "inside"
