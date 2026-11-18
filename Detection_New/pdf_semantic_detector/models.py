from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BBox = Tuple[float, float, float, float]
RGB = Tuple[int, int, int]


@dataclass(slots=True)
class RegionDescriptor:
    region_id: str
    page: int
    region_type: str
    bbox: BBox
    text: Optional[str] = None
    normalized_text: Optional[str] = None
    parser_text: Optional[str] = None
    rendered_text_estimate: Optional[str] = None
    rendered_text_confidence: Optional[float] = None
    text_semantic_source: str = "texttrace_unicode"
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    font_flags: Optional[Dict[str, Any]] = None
    color: Optional[RGB] = None
    background_color: Optional[RGB] = None
    alpha: Optional[float] = None
    z_order: Optional[int] = None
    clipping: Optional[Dict[str, Any]] = None
    layer: Optional[str] = None
    source_object: Optional[str] = None
    source_stream: Optional[str] = None
    operator: Optional[str] = None
    operator_offset: Optional[int] = None
    visibility_score: float = 1.0
    visibility_status: str = "visible"
    visibility_reasons: List[str] = field(default_factory=list)
    occluded_by: List[str] = field(default_factory=list)
    overlaps_with: List[str] = field(default_factory=list)
    block_id: Optional[str] = None
    block_role: Optional[str] = None
    block_role_confidence: Optional[float] = None


@dataclass(slots=True)
class BlockDescriptor:
    block_id: str
    page: int
    block_role: str
    block_role_confidence: float
    bbox: BBox
    region_ids: List[str]
    text: str
    normalized_text: str
    parser_text: Optional[str] = None
    rendered_text_estimate: Optional[str] = None
    text_semantic_source: str = "region_aggregation"
    line_count: int = 1
    font_names: List[str] = field(default_factory=list)
    font_size_median: Optional[float] = None
    visibility_score: float = 1.0
    visibility_status: str = "visible"
    visibility_reasons: List[str] = field(default_factory=list)
    representative_region_id: Optional[str] = None
    features: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParserSpan:
    span_id: str
    parser_name: str
    page: Optional[int]
    text: str
    normalized_text: str
    order: int
    bbox: Optional[BBox] = None
    source_hint: Optional[str] = None
    raw_span_ids: List[str] = field(default_factory=list)
    aggregation_level: str = "raw"


@dataclass(slots=True)
class MappingResult:
    span_id: str
    matched_region_id: Optional[str]
    match_score: float
    text_score: float
    geo_score: Optional[float]
    source_score: Optional[float]
    visibility_score: Optional[float]
    support_status: str
    matched_block_id: Optional[str] = None
    mapping_scope: str = "region"
    reasons: List[str] = field(default_factory=list)


@dataclass(slots=True)
class RiskFinding:
    finding_id: str
    page: Optional[int]
    parser_span: ParserSpan
    mapping: MappingResult
    risk_level: str
    risk_score: float
    categories: List[str]
    evidence: Dict[str, Any]


def to_serializable(value: Any) -> Any:
    if is_dataclass(value):
        return {k: to_serializable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): to_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_serializable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value
