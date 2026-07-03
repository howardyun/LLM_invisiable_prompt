"""Geometry helpers for PDF-point bboxes."""

from __future__ import annotations

from typing import Iterable


def rect_area(bbox: list[float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def intersection_area(a: list[float], b: list[float]) -> float:
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[2], b[2])
    bottom = min(a[3], b[3])
    return max(0.0, right - left) * max(0.0, bottom - top)


def bbox_union(boxes: Iterable[list[float]]) -> list[float] | None:
    boxes = list(boxes)
    if not boxes:
        return None
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def expand_bbox(
    bbox: list[float],
    padding: float,
    page_width: float,
    page_height: float,
) -> list[float]:
    """Expand a PDF-point bbox and clip it to a page rectangle."""

    return [
        max(0.0, bbox[0] - padding),
        max(0.0, bbox[1] - padding),
        min(page_width, bbox[2] + padding),
        min(page_height, bbox[3] + padding),
    ]


def best_region_match(bbox: list[float], regions, page_no: int) -> dict:
    """Best single Docling region match for debug only."""

    area = rect_area(bbox)
    best = {"region_id": None, "label": None, "coverage": 0.0, "intersection_area": 0.0}
    if area <= 0:
        return best
    for region in regions:
        if region.page_no != page_no or region.source != "docling_region":
            continue
        overlap = intersection_area(bbox, region.bbox)
        coverage = overlap / area
        if coverage > best["coverage"]:
            best = {
                "region_id": region.region_id,
                "label": region.label,
                "coverage": round(coverage, 4),
                "intersection_area": round(overlap, 4),
            }
    return best


def cumulative_region_coverage(bbox: list[float], regions, page_no: int) -> float:
    """Approximate how much a bbox is covered by all Docling regions.

    This fixes the previous "best single region" issue where a large PyMuPDF
    block spanning many list_items was incorrectly treated as PyMuPDF-only.
    """

    area = rect_area(bbox)
    if area <= 0:
        return 0.0
    overlap_sum = 0.0
    for region in regions:
        if region.page_no == page_no and region.source == "docling_region":
            overlap_sum += intersection_area(bbox, region.bbox)
    return min(1.0, overlap_sum / area)
