from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from statistics import median
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..config import DetectionConfig
from ..models import BBox, BlockDescriptor, RegionDescriptor
from .geometry import bbox_area, union_bbox
from .normalization import normalize_text


WORD_RE = re.compile(r"[A-Za-z]{2,}|[\u4e00-\u9fff]+")
CAPTION_RE = re.compile(r"^\s*(fig(?:ure)?|table)\s*[\d.:：-]", re.IGNORECASE)
MATH_FONT_RE = re.compile(
    r"(math|symbol|cmmi|cmsy|cmex|msam|msbm|stix|mtmi|cambria|esint|eufm)",
    re.IGNORECASE,
)
MATH_CHARS = set(
    "=+-*/^_<>[]{}()|\\"
    "±×÷≈≠≤≥∑∏∫√∞∂∇∆∈∉∋⊂⊃⊆⊇∪∩∧∨¬∀∃∴∵→←↔⇒⇔"
    "αβγδεζηθικλμνξοπρστυφχψω"
    "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
)
SERIOUS_VISIBILITY_REASONS = {
    "low_alpha",
    "render_mode_invisible",
    "off_page",
    "partially_off_page",
    "hidden_layer",
    "occluded",
}


@dataclass(slots=True)
class _LineItem:
    page: int
    bbox: BBox
    regions: List[RegionDescriptor]
    text: str
    parser_text: str
    rendered_text: str
    normalized_text: str
    cluster_count: int
    font_size: Optional[float]
    visibility_score: float
    visibility_reasons: List[str]
    semantic_drift: bool


def _region_text(region: RegionDescriptor) -> str:
    return region.rendered_text_estimate or region.text or ""


def _region_parser_text(region: RegionDescriptor) -> str:
    return region.parser_text or region.text or ""


def _source_region_ids(region: RegionDescriptor) -> List[str]:
    ids = [region.region_id]
    flags = region.font_flags or {}
    for item in flags.get("source_regions", []) if isinstance(flags, dict) else []:
        if isinstance(item, str):
            ids.append(item)
    return list(dict.fromkeys(ids))


def _is_semantic_drift(region: RegionDescriptor) -> bool:
    flags = region.font_flags or {}
    return (
        region.text_semantic_source == "glyph_shape_line"
        or bool(isinstance(flags, dict) and flags.get("semantic_drift"))
        or (
            region.parser_text is not None
            and region.rendered_text_estimate is not None
            and region.parser_text != region.rendered_text_estimate
        )
    )


def _usable_text_regions(regions: Sequence[RegionDescriptor]) -> List[RegionDescriptor]:
    aggregated_sources = set()
    for region in regions:
        if region.text_semantic_source != "glyph_shape_line":
            continue
        flags = region.font_flags or {}
        for source_id in flags.get("source_regions", []) if isinstance(flags, dict) else []:
            if isinstance(source_id, str):
                aggregated_sources.add(source_id)

    out: List[RegionDescriptor] = []
    for region in regions:
        if region.region_type != "text":
            continue
        if not _region_text(region).strip():
            continue
        if region.region_id in aggregated_sources:
            continue
        out.append(region)
    return out


def _char_width(region: RegionDescriptor) -> float:
    text = _region_text(region)
    width = max(0.0, region.bbox[2] - region.bbox[0])
    return width / max(len(text), 1)


def _join_regions(regions: Sequence[RegionDescriptor], parser: bool = False) -> str:
    parts: List[str] = []
    prev: Optional[RegionDescriptor] = None
    widths = [_char_width(region) for region in regions if _char_width(region) > 0]
    median_width = median(widths) if widths else 4.0
    for region in regions:
        if prev is not None:
            gap = region.bbox[0] - prev.bbox[2]
            threshold = max(2.0, median_width * 0.70)
            if gap > threshold:
                parts.append(" ")
        parts.append(_region_parser_text(region) if parser else _region_text(region))
        prev = region
    return "".join(parts).strip()


def _cluster_regions(regions: Sequence[RegionDescriptor]) -> List[List[RegionDescriptor]]:
    if not regions:
        return []
    ordered = sorted(regions, key=lambda region: region.bbox[0])
    widths = [_char_width(region) for region in ordered if _char_width(region) > 0]
    median_width = median(widths) if widths else 4.0
    threshold = max(18.0, median_width * 3.5)
    clusters: List[List[RegionDescriptor]] = [[ordered[0]]]
    for region in ordered[1:]:
        prev = clusters[-1][-1]
        gap = region.bbox[0] - prev.bbox[2]
        if gap > threshold:
            clusters.append([region])
        else:
            clusters[-1].append(region)
    return clusters


def _prose_words(text: str) -> int:
    return len(WORD_RE.findall(text or ""))


def _should_split_columns(clusters: Sequence[Sequence[RegionDescriptor]]) -> bool:
    if len(clusters) < 2:
        return False
    wide_prose = 0
    for cluster in clusters:
        bbox = union_bbox(region.bbox for region in cluster)
        if bbox is None:
            continue
        text = _join_regions(cluster)
        if bbox[2] - bbox[0] >= 90.0 and _prose_words(text) >= 4:
            wide_prose += 1
    return wide_prose >= 2


def _line_from_regions(page: int, regions: Sequence[RegionDescriptor]) -> Optional[_LineItem]:
    ordered = sorted(regions, key=lambda region: region.bbox[0])
    bbox = union_bbox(region.bbox for region in ordered)
    if bbox is None:
        return None
    text = _join_regions(ordered)
    if not text:
        return None
    parser_text = _join_regions(ordered, parser=True)
    font_sizes = [region.font_size for region in ordered if region.font_size is not None]
    visibility_score = min((region.visibility_score for region in ordered), default=1.0)
    reasons: List[str] = []
    for region in ordered:
        reasons.extend(region.visibility_reasons)
    return _LineItem(
        page=page,
        bbox=bbox,
        regions=list(ordered),
        text=text,
        parser_text=parser_text,
        rendered_text=text,
        normalized_text=normalize_text(text),
        cluster_count=len(_cluster_regions(ordered)),
        font_size=median(font_sizes) if font_sizes else None,
        visibility_score=visibility_score,
        visibility_reasons=list(dict.fromkeys(reasons)),
        semantic_drift=any(_is_semantic_drift(region) for region in ordered),
    )


def _group_regions_into_lines(regions: Sequence[RegionDescriptor], config: DetectionConfig) -> List[_LineItem]:
    sorted_regions = sorted(regions, key=lambda region: ((region.bbox[1] + region.bbox[3]) / 2.0, region.bbox[0]))
    y_groups: List[List[RegionDescriptor]] = []
    for region in sorted_regions:
        cy = (region.bbox[1] + region.bbox[3]) / 2.0
        placed = False
        for group in y_groups:
            ref = group[0]
            ref_cy = (ref.bbox[1] + ref.bbox[3]) / 2.0
            ref_size = ref.font_size or max(1.0, ref.bbox[3] - ref.bbox[1])
            size = region.font_size or max(1.0, region.bbox[3] - region.bbox[1])
            tolerance = max(2.5, min(ref_size, size) * config.block_line_y_tolerance_factor)
            if abs(cy - ref_cy) <= tolerance:
                group.append(region)
                placed = True
                break
        if not placed:
            y_groups.append([region])

    lines: List[_LineItem] = []
    for group in y_groups:
        clusters = _cluster_regions(group)
        if _should_split_columns(clusters):
            for cluster in clusters:
                line = _line_from_regions(group[0].page, cluster)
                if line is not None:
                    lines.append(line)
            continue
        line = _line_from_regions(group[0].page, group)
        if line is not None:
            lines.append(line)
    return sorted(lines, key=lambda line: (line.page, line.bbox[1], line.bbox[0]))


def _horizontal_overlap_ratio(a: BBox, b: BBox) -> float:
    overlap = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    denom = max(1.0, min(a[2] - a[0], b[2] - b[0]))
    return overlap / denom


def _visibility_class(line: _LineItem) -> str:
    if line.visibility_score < 0.60 or line.visibility_reasons:
        return "low_visibility"
    if line.semantic_drift:
        return "drift"
    return "visible"


def _can_follow(prev: _LineItem, line: _LineItem, config: DetectionConfig) -> bool:
    if prev.page != line.page:
        return False
    if _visibility_class(prev) != _visibility_class(line):
        return False

    gap = line.bbox[1] - prev.bbox[3]
    prev_height = max(1.0, prev.bbox[3] - prev.bbox[1])
    line_height = max(1.0, line.bbox[3] - line.bbox[1])
    font_size = prev.font_size or line.font_size or max(prev_height, line_height)
    if gap > max(8.0, font_size * config.block_max_line_gap_factor):
        return False

    overlap = _horizontal_overlap_ratio(prev.bbox, line.bbox)
    left_delta = abs(prev.bbox[0] - line.bbox[0])
    indent_delta = line.bbox[0] - prev.bbox[0]
    both_multicol = prev.cluster_count >= 2 and line.cluster_count >= 2
    if both_multicol:
        return overlap >= 0.25 or left_delta <= config.block_x_alignment_tolerance * 1.5
    if overlap >= 0.45:
        return True
    if left_delta <= config.block_x_alignment_tolerance:
        return True
    if 0.0 <= indent_delta <= config.block_x_alignment_tolerance * 2.0 and overlap >= 0.25:
        return True
    return False


def _group_lines_into_blocks(lines: Sequence[_LineItem], config: DetectionConfig) -> List[List[_LineItem]]:
    blocks: List[List[_LineItem]] = []
    for line in lines:
        if not blocks or not _can_follow(blocks[-1][-1], line, config):
            blocks.append([line])
        else:
            blocks[-1].append(line)
    return blocks


def _math_symbol_ratio(text: str) -> float:
    chars = [char for char in text if not char.isspace()]
    if not chars:
        return 0.0
    return sum(1 for char in chars if char in MATH_CHARS) / len(chars)


def _natural_ratio(text: str) -> float:
    chars = [char for char in text if not char.isspace()]
    if not chars:
        return 0.0
    natural = sum(1 for char in chars if char.isalnum() or char in ".,;:!?'-")
    return natural / len(chars)


def _compact_normalized(text: str) -> str:
    return re.sub(r"\s+", "", normalize_text(text or ""))


def _parser_render_similarity(parser_text: str, rendered_text: str) -> float:
    parser_compact = _compact_normalized(parser_text)
    rendered_compact = _compact_normalized(rendered_text)
    if not parser_compact or not rendered_compact:
        return 1.0 if parser_compact == rendered_compact else 0.0
    return SequenceMatcher(None, parser_compact, rendered_compact).ratio()


def _font_char_counts(lines: Sequence[_LineItem]) -> Tuple[List[str], Optional[float], float]:
    font_names: List[str] = []
    font_sizes: List[float] = []
    symbol_chars = 0
    total_chars = 0
    for line in lines:
        for region in line.regions:
            text_len = len(_region_text(region))
            total_chars += text_len
            if region.font_name:
                font_names.append(str(region.font_name))
                if MATH_FONT_RE.search(str(region.font_name)):
                    symbol_chars += text_len
            if region.font_size is not None:
                font_sizes.append(region.font_size)
    symbol_ratio = symbol_chars / max(total_chars, 1)
    return sorted(set(font_names)), (median(font_sizes) if font_sizes else None), symbol_ratio


def _page_text_bounds(page_lines: Sequence[_LineItem]) -> Optional[BBox]:
    return union_bbox(line.bbox for line in page_lines)


def _features(lines: Sequence[_LineItem], page_bounds: Optional[BBox]) -> Dict[str, object]:
    text = "\n".join(line.text for line in lines)
    parser_text = "\n".join(line.parser_text for line in lines)
    line_count = len(lines)
    multi_cluster_lines = sum(1 for line in lines if line.cluster_count >= 2)
    word_count = _prose_words(text)
    math_ratio = _math_symbol_ratio(text)
    font_names, font_size_median, symbol_font_ratio = _font_char_counts(lines)
    bbox = union_bbox(line.bbox for line in lines)
    vertical_band = "middle"
    if page_bounds and bbox:
        page_height = max(1.0, page_bounds[3] - page_bounds[1])
        y_mid = ((bbox[1] + bbox[3]) / 2.0 - page_bounds[1]) / page_height
        if y_mid <= 0.12:
            vertical_band = "top"
        elif y_mid >= 0.88:
            vertical_band = "bottom"
    return {
        "line_count": line_count,
        "word_count": word_count,
        "char_count": len([char for char in text if not char.isspace()]),
        "math_symbol_ratio": round(math_ratio, 6),
        "inline_math_ratio": round(math_ratio if word_count > 8 else 0.0, 6),
        "natural_text_ratio": round(_natural_ratio(text), 6),
        "symbol_font_ratio": round(symbol_font_ratio, 6),
        "multi_cluster_line_ratio": round(multi_cluster_lines / max(line_count, 1), 6),
        "avg_clusters_per_line": round(sum(line.cluster_count for line in lines) / max(line_count, 1), 6),
        "semantic_drift_line_ratio": round(sum(1 for line in lines if line.semantic_drift) / max(line_count, 1), 6),
        "glyph_shape_line_ratio": round(
            sum(
                1
                for line in lines
                if any(region.text_semantic_source == "glyph_shape_line" for region in line.regions)
            )
            / max(line_count, 1),
            6,
        ),
        "parser_render_similarity": round(_parser_render_similarity(parser_text, text), 6),
        "low_visibility_line_ratio": round(
            sum(1 for line in lines if line.visibility_score < 0.60 or line.visibility_reasons) / max(line_count, 1),
            6,
        ),
        "font_names": font_names,
        "font_size_median": font_size_median,
        "vertical_band": vertical_band,
        "caption_like": bool(CAPTION_RE.match(text)),
    }


def _classify_block(
    lines: Sequence[_LineItem],
    feature_map: Dict[str, object],
    config: DetectionConfig,
) -> Tuple[str, float]:
    text = "\n".join(line.text for line in lines)
    word_count = int(feature_map["word_count"])
    math_ratio = float(feature_map["math_symbol_ratio"])
    symbol_font_ratio = float(feature_map["symbol_font_ratio"])
    multi_cluster_ratio = float(feature_map["multi_cluster_line_ratio"])
    natural_ratio = float(feature_map["natural_text_ratio"])
    semantic_drift_ratio = float(feature_map["semantic_drift_line_ratio"])
    glyph_shape_line_ratio = float(feature_map["glyph_shape_line_ratio"])
    parser_render_similarity = float(feature_map["parser_render_similarity"])
    low_visibility_ratio = float(feature_map["low_visibility_line_ratio"])
    line_count = int(feature_map["line_count"])
    vertical_band = str(feature_map["vertical_band"])

    if (
        semantic_drift_ratio > 0
        and glyph_shape_line_ratio > 0
        and parser_render_similarity < config.block_glyph_drift_max_similarity
    ):
        return "glyph_drift_text", 0.96
    block_reasons = set()
    for line in lines:
        block_reasons.update(line.visibility_reasons)
    serious_visibility = bool(block_reasons & SERIOUS_VISIBILITY_REASONS)

    if serious_visibility or low_visibility_ratio >= 0.50:
        return "hidden_or_overlay_text", 0.90
    if bool(feature_map["caption_like"]):
        return "caption", 0.86
    if vertical_band in {"top", "bottom"} and line_count <= 2 and word_count <= 10:
        return "header_footer", 0.72

    inline_math_in_prose = word_count >= 12 and math_ratio < max(0.28, config.block_formula_math_ratio * 1.5)
    table_like = (
        line_count >= config.block_min_table_rows
        and multi_cluster_ratio >= config.block_table_min_multicol_ratio
        and natural_ratio >= 0.45
        and not inline_math_in_prose
    )
    if table_like:
        return "table", 0.82

    formula_like = (
        math_ratio >= config.block_formula_math_ratio
        and not inline_math_in_prose
        and (word_count <= config.block_formula_max_prose_words or symbol_font_ratio >= config.block_formula_symbol_font_ratio)
    ) or (
        symbol_font_ratio >= config.block_formula_symbol_font_ratio
        and math_ratio >= 0.08
        and word_count <= config.block_formula_max_prose_words * 2
        and not inline_math_in_prose
    )
    if formula_like:
        return "formula", 0.84

    if line_count <= 2 and word_count <= 10 and text[:1].isupper() and not text.rstrip().endswith((".", "?", "!")):
        return "heading", 0.62
    return "paragraph", 0.78


def _block_text(lines: Sequence[_LineItem], parser: bool = False) -> str:
    if parser:
        return "\n".join(line.parser_text for line in lines if line.parser_text).strip()
    return "\n".join(line.rendered_text or line.text for line in lines if line.text).strip()


def _block_region_ids(lines: Sequence[_LineItem]) -> List[str]:
    ids: List[str] = []
    for line in lines:
        for region in line.regions:
            ids.extend(_source_region_ids(region))
    return list(dict.fromkeys(ids))


def _visibility_for_lines(lines: Sequence[_LineItem]) -> Tuple[float, str, List[str]]:
    low_lines = [line for line in lines if line.visibility_score < 0.60 or line.visibility_reasons]
    low_line_ratio = len(low_lines) / max(len(lines), 1)
    reasons: List[str] = []
    for line in lines:
        reasons.extend(line.visibility_reasons)
    reasons = list(dict.fromkeys(reasons))
    serious_visibility = bool(set(reasons) & SERIOUS_VISIBILITY_REASONS)
    if low_lines and (serious_visibility or low_line_ratio >= 0.50):
        score = min((line.visibility_score for line in low_lines), default=1.0)
    else:
        score = 1.0
        if not serious_visibility:
            reasons = []
    if score < 0.10:
        status = "invisible"
    elif score < 0.60 or reasons:
        status = "low_visible"
    else:
        status = "visible"
    return score, status, reasons


def _make_block(
    page: int,
    index: int,
    lines: Sequence[_LineItem],
    page_bounds: Optional[BBox],
    config: DetectionConfig,
) -> Optional[BlockDescriptor]:
    bbox = union_bbox(line.bbox for line in lines)
    if bbox is None or bbox_area(bbox) <= 0:
        return None
    text = _block_text(lines)
    if not text.strip():
        return None
    features = _features(lines, page_bounds)
    role, confidence = _classify_block(lines, features, config)
    font_names, font_size_median, _symbol_ratio = _font_char_counts(lines)
    visibility_score, visibility_status, visibility_reasons = _visibility_for_lines(lines)
    region_ids = _block_region_ids(lines)
    representative_region_id = region_ids[0] if region_ids else None
    return BlockDescriptor(
        block_id=f"p{page}_b{index:05d}",
        page=page,
        block_role=role,
        block_role_confidence=round(confidence, 6),
        bbox=bbox,
        region_ids=region_ids,
        text=text,
        normalized_text=normalize_text(text),
        parser_text=_block_text(lines, parser=True),
        rendered_text_estimate=text,
        text_semantic_source="line_block_aggregation",
        line_count=len(lines),
        font_names=font_names,
        font_size_median=font_size_median,
        visibility_score=visibility_score,
        visibility_status=visibility_status,
        visibility_reasons=visibility_reasons,
        representative_region_id=representative_region_id,
        features=features,
    )


def _annotate_regions(regions: Sequence[RegionDescriptor], blocks: Sequence[BlockDescriptor]) -> None:
    by_id = {region.region_id: region for region in regions}
    for block in blocks:
        for region_id in block.region_ids:
            region = by_id.get(region_id)
            if region is None:
                continue
            region.block_id = block.block_id
            region.block_role = block.block_role
            region.block_role_confidence = block.block_role_confidence


def build_structure_blocks(
    regions: List[RegionDescriptor],
    config: Optional[DetectionConfig] = None,
) -> List[BlockDescriptor]:
    config = config or DetectionConfig()
    if not config.enable_block_mapping:
        return []

    text_regions = _usable_text_regions(regions)
    regions_by_page: Dict[int, List[RegionDescriptor]] = {}
    for region in text_regions:
        regions_by_page.setdefault(region.page, []).append(region)

    blocks: List[BlockDescriptor] = []
    for page in sorted(regions_by_page):
        page_regions = regions_by_page[page]
        lines = _group_regions_into_lines(page_regions, config)
        page_bounds = _page_text_bounds(lines)
        line_groups = _group_lines_into_blocks(lines, config)
        for local_index, group in enumerate(line_groups, start=1):
            block = _make_block(page, local_index, group, page_bounds, config)
            if block is not None:
                blocks.append(block)

    _annotate_regions(regions, blocks)
    return blocks
