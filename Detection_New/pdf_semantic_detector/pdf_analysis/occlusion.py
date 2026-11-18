from __future__ import annotations

from typing import Iterable, List

from ..config import DetectionConfig
from ..models import RegionDescriptor
from .geometry import overlap_ratio


def apply_occlusion_estimate(
    regions: List[RegionDescriptor],
    config: DetectionConfig,
) -> List[RegionDescriptor]:
    """Rectangle-level occlusion heuristic based on later non-text objects."""

    if not config.enable_occlusion:
        return regions

    paint_regions = [
        r
        for r in regions
        if r.region_type in {"path", "image", "xobject"} and r.z_order is not None
    ]
    text_regions = [r for r in regions if r.region_type == "text" and r.z_order is not None]

    for text in text_regions:
        for paint in paint_regions:
            if paint.page != text.page or paint.z_order is None or text.z_order is None:
                continue
            if paint.z_order <= text.z_order:
                continue
            ratio = overlap_ratio(text.bbox, paint.bbox)
            if ratio < config.occlusion_overlap_threshold:
                continue
            if paint.region_id not in text.occluded_by:
                text.occluded_by.append(paint.region_id)
            if "occluded" not in text.visibility_reasons:
                text.visibility_reasons.append("occluded")
            text.visibility_score = min(text.visibility_score, 0.10)
            text.visibility_status = "low_visible"
    return regions
