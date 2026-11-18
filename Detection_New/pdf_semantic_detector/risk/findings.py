from __future__ import annotations

import re
from typing import Dict, List, Optional

from ..config import DetectionConfig
from ..models import BlockDescriptor, MappingResult, ParserSpan, RegionDescriptor, RiskFinding
from .instructionality import compute_instructionality
from .scorer import categories_for, risk_level, risk_score


WORD_RE = re.compile(r"[A-Za-z0-9]{2,}")


def _short(text: str, limit: int = 300) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


def _region_evidence(
    region: Optional[RegionDescriptor],
    instruction_matches: List[str],
    block: Optional[BlockDescriptor] = None,
    regions_by_id: Optional[Dict[str, RegionDescriptor]] = None,
) -> Dict[str, object]:
    evidence: Dict[str, object] = {"instruction_patterns": instruction_matches}
    if block is not None:
        child_regions = []
        if regions_by_id is not None:
            for region_id in block.region_ids[:20]:
                child = regions_by_id.get(region_id)
                if child is None:
                    continue
                if child.visibility_reasons or child.text_semantic_source in {"glyph_shape", "glyph_shape_line"}:
                    child_regions.append(
                        {
                            "region_id": child.region_id,
                            "bbox": child.bbox,
                            "text_semantic_source": child.text_semantic_source,
                            "visibility_score": child.visibility_score,
                            "visibility_reasons": child.visibility_reasons,
                            "parser_text_preview": _short(child.parser_text or child.text or "", 120),
                            "rendered_text_preview": _short(child.rendered_text_estimate or child.text or "", 120),
                        }
                    )
        evidence.update(
            {
                "block_id": block.block_id,
                "block_role": block.block_role,
                "block_role_confidence": block.block_role_confidence,
                "block_bbox": block.bbox,
                "block_region_ids": block.region_ids,
                "block_text_preview": _short(block.text),
                "block_rendered_text_preview": _short(block.rendered_text_estimate or block.text),
                "block_parser_text_preview": _short(block.parser_text or ""),
                "block_features": block.features,
                "child_region_evidence": child_regions,
            }
        )
    if region is None:
        return evidence
    evidence.update(
        {
            "region_id": region.region_id,
            "bbox": region.bbox,
            "font_name": region.font_name,
            "font_size": region.font_size,
            "color": region.color,
            "background_color": region.background_color,
            "alpha": region.alpha,
            "z_order": region.z_order,
            "source_object": region.source_object,
            "source_stream": region.source_stream,
            "operator": region.operator,
            "operator_offset": region.operator_offset,
            "layer": region.layer,
            "visibility_reasons": region.visibility_reasons,
            "occluded_by": region.occluded_by,
        }
    )
    return evidence


def _should_report_mapping(
    mapping: MappingResult,
    region: Optional[RegionDescriptor],
    block: Optional[BlockDescriptor],
    instr_score: float,
    score: float,
    config: DetectionConfig,
) -> bool:
    if mapping.support_status == "render_supported":
        return False

    if mapping.support_status == "render_unsupported":
        if block is not None and block.block_role in {"formula", "table", "caption", "header_footer"} and instr_score <= 0:
            return False
        if instr_score > 0:
            return True
        return config.report_parser_only_without_instruction and score >= config.risk_threshold

    if mapping.support_status == "low_visibility_supported":
        if region is None and block is None:
            return instr_score > 0
        reason_set = set(mapping.reasons)
        if region is not None:
            reason_set |= set(region.visibility_reasons)
        if block is not None:
            reason_set |= set(block.visibility_reasons)
        tiny_only = bool(reason_set & {"small_font_size", "zero_font_size", "zero_area_bbox"}) and not (
            reason_set
            & {
                "low_alpha",
                "render_mode_invisible",
                "low_color_contrast",
                "off_page",
                "partially_off_page",
                "hidden_layer",
                "occluded",
            }
        )
        if tiny_only and instr_score <= 0:
            text = ""
            if block is not None:
                text = block.parser_text or block.text or ""
            elif region is not None:
                text = region.parser_text or region.text or ""
            word_count = len(WORD_RE.findall(text))
            if (
                len(text.strip()) < config.tiny_text_min_chars_without_instruction
                or word_count < config.tiny_text_min_words_without_instruction
            ):
                return False
        visibility_score = block.visibility_score if block is not None else (region.visibility_score if region else 1.0)
        return visibility_score < 0.60 or instr_score > 0

    if mapping.support_status == "ambiguous":
        return instr_score > 0 and score >= config.risk_threshold

    return score >= config.risk_threshold and instr_score > 0


def build_findings(
    spans: List[ParserSpan],
    mappings: List[MappingResult],
    regions: List[RegionDescriptor],
    config: DetectionConfig,
    blocks: Optional[List[BlockDescriptor]] = None,
) -> List[RiskFinding]:
    region_by_id = {r.region_id: r for r in regions}
    block_by_id = {b.block_id: b for b in (blocks or [])}
    span_by_id = {s.span_id: s for s in spans}
    findings: List[RiskFinding] = []

    for mapping in mappings:
        span = span_by_id[mapping.span_id]
        region = region_by_id.get(mapping.matched_region_id or "")
        block = block_by_id.get(mapping.matched_block_id or "")
        instr = compute_instructionality(span.text)
        score = risk_score(mapping, instr)
        categories = categories_for(mapping, region, instr, block)

        should_report = _should_report_mapping(mapping, region, block, instr.score, score, config)
        if not should_report:
            continue

        findings.append(
            RiskFinding(
                finding_id=f"f{len(findings) + 1:05d}",
                page=span.page if span.page is not None else (region.page if region else None),
                parser_span=span,
                mapping=mapping,
                risk_level=risk_level(mapping, score, instr),
                risk_score=score,
                categories=categories,
                evidence=_region_evidence(region, instr.matches, block, region_by_id),
            )
        )
    return findings
