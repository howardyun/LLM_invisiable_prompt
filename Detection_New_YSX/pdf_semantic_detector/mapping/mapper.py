from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..config import DetectionConfig
from ..models import BlockDescriptor, MappingResult, ParserSpan, RegionDescriptor
from ..pdf_analysis.geometry import bbox_iou
from .text_matcher import block_text_match_score, text_match_score


@dataclass(slots=True)
class _Candidate:
    region: Optional[RegionDescriptor]
    block: Optional[BlockDescriptor]
    text_score: float
    geo_score: Optional[float]
    support_score: float
    scope: str


def _visibility_score(region: Optional[RegionDescriptor], block: Optional[BlockDescriptor]) -> float:
    if block is not None:
        return block.visibility_score
    if region is not None:
        return region.visibility_score
    return 1.0


def _support_score(
    span: ParserSpan,
    region: Optional[RegionDescriptor],
    block: Optional[BlockDescriptor],
    text_score: float,
    geo_score: Optional[float],
) -> float:
    visibility = _visibility_score(region, block)
    if span.bbox is None or geo_score is None:
        return 0.75 * text_score + 0.25 * visibility
    return 0.55 * text_score + 0.25 * geo_score + 0.20 * visibility


def _candidate_regions(span: ParserSpan, regions: List[RegionDescriptor]) -> List[RegionDescriptor]:
    text_regions = [r for r in regions if r.region_type == "text" and r.normalized_text]
    if span.page is None:
        return text_regions
    same_page = [r for r in text_regions if r.page == span.page]
    return same_page or text_regions


def _candidate_blocks(span: ParserSpan, blocks: List[BlockDescriptor]) -> List[BlockDescriptor]:
    if span.page is None:
        return blocks
    same_page = [block for block in blocks if block.page == span.page]
    return same_page or blocks


def _block_status(best: _Candidate, config: DetectionConfig) -> Tuple[str, List[str]]:
    reasons: List[str] = []
    block = best.block
    if block is None:
        return "render_unsupported", ["missing_block_candidate"]

    if best.text_score < config.match_threshold:
        if (
            block.block_role in {"formula", "table"}
            and best.text_score >= config.block_special_weak_match_threshold
            and block.visibility_status == "visible"
        ):
            return "render_supported", [f"structure_tolerated_{block.block_role}"]
        reasons.append("below_match_threshold")
        reasons.append(f"block_role:{block.block_role}")
        return "render_unsupported", reasons
    if block.visibility_status != "visible" or block.visibility_score < 0.60:
        reasons.extend(block.visibility_reasons)
        return "low_visibility_supported", list(dict.fromkeys(reasons))
    return "render_supported", reasons


def map_one_span(
    span: ParserSpan,
    regions: List[RegionDescriptor],
    config: DetectionConfig,
    blocks: Optional[List[BlockDescriptor]] = None,
) -> MappingResult:
    candidates: List[_Candidate] = []
    if blocks:
        for block in _candidate_blocks(span, blocks):
            score = block_text_match_score(span.normalized_text or span.text, block.normalized_text or block.text or "")
            if score <= 0:
                continue
            geo = bbox_iou(span.bbox, block.bbox) if span.bbox is not None else None
            candidates.append(_Candidate(None, block, score, geo, _support_score(span, None, block, score, geo), "block"))
    else:
        for region in _candidate_regions(span, regions):
            score = text_match_score(span.normalized_text or span.text, region.normalized_text or region.text or "")
            if score <= 0:
                continue
            geo = bbox_iou(span.bbox, region.bbox) if span.bbox is not None else None
            candidates.append(_Candidate(region, None, score, geo, _support_score(span, region, None, score, geo), "region"))

    candidates.sort(key=lambda c: (c.text_score, c.support_score), reverse=True)
    if not candidates or candidates[0].text_score < config.weak_match_threshold:
        return MappingResult(
            span_id=span.span_id,
            matched_region_id=None,
            match_score=0.0,
            text_score=0.0 if not candidates else candidates[0].text_score,
            geo_score=None,
            source_score=None,
            visibility_score=None,
            support_status="render_unsupported",
            matched_block_id=None,
            mapping_scope="block" if blocks else "region",
            reasons=["no_text_block_match" if blocks else "no_text_region_match"],
        )

    best = candidates[0]
    best_id = best.block.block_id if best.block is not None else (best.region.region_id if best.region else None)
    ambiguous = (
        len(candidates) > 1
        and best.text_score >= config.match_threshold
        and candidates[1].text_score >= config.match_threshold
        and abs(best.text_score - candidates[1].text_score) <= config.ambiguous_margin
        and (
            candidates[1].block.block_id
            if candidates[1].block is not None
            else (candidates[1].region.region_id if candidates[1].region else None)
        )
        != best_id
    )

    reasons: List[str] = []
    if best.scope == "block":
        status, reasons = _block_status(best, config)
    elif best.text_score < config.match_threshold:
        status = "render_unsupported"
        reasons.append("below_match_threshold")
    elif best.region is not None and (best.region.visibility_status != "visible" or best.region.visibility_score < 0.60):
        status = "low_visibility_supported"
        reasons.extend(best.region.visibility_reasons)
    else:
        status = "render_supported"

    if ambiguous and status == "render_supported":
        status = "ambiguous"
        reasons.append("multiple_similar_regions")

    visibility = _visibility_score(best.region, best.block)

    return MappingResult(
        span_id=span.span_id,
        matched_region_id=best.region.region_id if best.region is not None else (
            best.block.representative_region_id if best.block is not None else None
        ),
        match_score=round(best.support_score, 6),
        text_score=round(best.text_score, 6),
        geo_score=round(best.geo_score, 6) if best.geo_score is not None else None,
        source_score=None,
        visibility_score=round(visibility, 6),
        support_status=status,
        matched_block_id=best.block.block_id if best.block is not None else None,
        mapping_scope=best.scope,
        reasons=list(dict.fromkeys(reasons)),
    )


def map_parser_spans(
    spans: List[ParserSpan],
    regions: List[RegionDescriptor],
    config: Optional[DetectionConfig] = None,
    blocks: Optional[List[BlockDescriptor]] = None,
) -> List[MappingResult]:
    config = config or DetectionConfig()
    return [map_one_span(span, regions, config, blocks) for span in spans]
