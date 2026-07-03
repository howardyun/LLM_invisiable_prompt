from __future__ import annotations

from typing import Dict, List, Optional

from ..models import BlockDescriptor, MappingResult, RegionDescriptor
from .instructionality import InstructionalityResult


def categories_for(
    mapping: MappingResult,
    region: Optional[RegionDescriptor],
    instr: InstructionalityResult,
    block: Optional[BlockDescriptor] = None,
) -> List[str]:
    categories: List[str] = []
    reasons = set(mapping.reasons)
    if mapping.support_status == "render_unsupported":
        categories.append("parser_only_semantic")
    if instr.score > 0:
        categories.append("llm_control_intent")
    reason_set = reasons
    if block is not None:
        reason_set = reason_set | set(block.visibility_reasons)
        if block.block_role in {"formula", "table"}:
            categories.append(f"{block.block_role}_block")
        if block.block_role == "glyph_drift_text":
            categories.append("glyph_semantic_drift")
    if region is not None:
        reason_set = reason_set | set(region.visibility_reasons)
    if region is not None or block is not None:
        if reason_set & {"low_alpha", "render_mode_invisible"}:
            categories.append("invisible_text")
        if "low_color_contrast" in reason_set:
            categories.append("low_contrast_text")
        if reason_set & {"off_page", "partially_off_page"}:
            categories.append("off_page_text")
        if reason_set & {"small_font_size", "zero_font_size", "zero_area_bbox"}:
            categories.append("tiny_text")
        if "hidden_layer" in reason_set:
            categories.append("hidden_layer_text")
        if "occluded" in reason_set:
            categories.append("occluded_text")
    return list(dict.fromkeys(categories))


def risk_score(mapping: MappingResult, instr: InstructionalityResult) -> float:
    match_score = max(0.0, min(1.0, mapping.match_score))
    visibility = mapping.visibility_score
    if visibility is None:
        visibility = 0.0 if mapping.support_status == "render_unsupported" else 1.0
    score = 0.35 * (1.0 - match_score) + 0.35 * (1.0 - visibility) + 0.30 * instr.score
    if mapping.support_status == "low_visibility_supported":
        score = max(score, 0.50)
    if mapping.support_status == "render_unsupported" and instr.score > 0:
        score = max(score, 0.70)
    return round(max(0.0, min(1.0, score)), 6)


def risk_level(mapping: MappingResult, score: float, instr: InstructionalityResult) -> str:
    if mapping.support_status in {"low_visibility_supported", "render_unsupported"} and instr.score >= 0.75:
        return "critical"
    if mapping.support_status == "low_visibility_supported" and instr.score >= 0.35:
        return "high"
    if score >= 0.75:
        return "high"
    if mapping.support_status in {"low_visibility_supported", "render_unsupported"} or score >= 0.45:
        return "medium"
    return "low"
