from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence, Tuple

from ..config import DetectionConfig
from ..models import RGB, RegionDescriptor
from .geometry import bbox_area, page_overlap_status


def normalize_color(value: object) -> Optional[RGB]:
    if value is None:
        return None
    if isinstance(value, int):
        return ((value >> 16) & 255, (value >> 8) & 255, value & 255)
    if isinstance(value, (list, tuple)):
        vals = list(value)
        if len(vals) >= 3 and all(isinstance(v, (int, float)) for v in vals[:3]):
            if all(0.0 <= float(v) <= 1.0 for v in vals[:3]):
                return tuple(int(round(float(v) * 255.0)) for v in vals[:3])  # type: ignore[return-value]
            return tuple(int(max(0, min(255, round(float(v))))) for v in vals[:3])  # type: ignore[return-value]
    return None


def rgb_distance(c1: RGB, c2: RGB) -> float:
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(c1, c2)))


def _add_reason(region: RegionDescriptor, reason: str) -> None:
    if reason not in region.visibility_reasons:
        region.visibility_reasons.append(reason)


def estimate_visibility(
    region: RegionDescriptor,
    page_bbox: Tuple[float, float, float, float],
    config: DetectionConfig,
) -> RegionDescriptor:
    """Assign an MVP visibility score and reason list to one region."""

    score = 1.0
    flags = region.font_flags or {}

    if region.region_type == "text":
        render_type = flags.get("texttrace_type")
        bboxlog_type = str(flags.get("bboxlog_type") or "")
        if render_type == 3 or bboxlog_type == "ignore-text":
            _add_reason(region, "render_mode_invisible")
            score = min(score, 0.02)

        alpha = 1.0 if region.alpha is None else float(region.alpha)
        if alpha <= config.low_alpha_threshold:
            _add_reason(region, "low_alpha")
            score = min(score, 0.02)
        elif alpha < 0.30:
            _add_reason(region, "low_alpha")
            score = min(score, 0.25)

        if region.font_size is not None:
            if region.font_size <= 0.01:
                _add_reason(region, "zero_font_size")
                score = min(score, 0.01)
            elif region.font_size < config.tiny_font_size:
                _add_reason(region, "small_font_size")
                score = min(score, 0.10)
            elif region.font_size < config.min_font_size:
                _add_reason(region, "small_font_size")
                score = min(score, 0.45)

        if region.color is not None and region.background_color is not None:
            distance = rgb_distance(region.color, region.background_color)
            if distance < config.low_contrast_threshold:
                _add_reason(region, "low_color_contrast")
                score = min(score, 0.08 if distance < 5 else 0.20)

    status = page_overlap_status(region.bbox, page_bbox)
    if status == "zero_area" or bbox_area(region.bbox) <= 0:
        _add_reason(region, "zero_area_bbox")
        score = min(score, 0.05)
    elif status == "outside":
        _add_reason(region, "off_page")
        score = min(score, 0.01)
    elif status == "partial":
        _add_reason(region, "partially_off_page")
        score = min(score, 0.55)

    if region.layer and str(region.layer).lower() in {"hidden", "off", "disabled"}:
        _add_reason(region, "hidden_layer")
        score = min(score, 0.05)

    region.visibility_score = max(0.0, min(1.0, score))
    if region.visibility_score <= 0.05:
        region.visibility_status = "invisible"
    elif region.visibility_score < 0.60:
        region.visibility_status = "low_visible"
    else:
        region.visibility_status = "visible"
    return region
