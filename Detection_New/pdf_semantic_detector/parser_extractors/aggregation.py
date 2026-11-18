from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from ..config import DetectionConfig
from ..mapping.text_matcher import block_text_match_score
from ..models import BBox, BlockDescriptor, ParserSpan
from ..pdf_analysis.geometry import union_bbox
from ..pdf_analysis.normalization import compact_text, normalize_text
from ..risk.instructionality import compute_instructionality


HEADING_RE = re.compile(r"^\s*(abstract|references|acknowledg(?:e)?ments?)\s*$", re.IGNORECASE)
SECTION_RE = re.compile(r"^\s*(\d+(\.\d+)*|[IVX]+)\s+[A-Z][A-Za-z0-9 -]{2,}$")
CAPTION_RE = re.compile(r"^\s*(fig(?:ure)?|table)\s*[\d.:：-]", re.IGNORECASE)


@dataclass(slots=True)
class _WindowCandidate:
    end: int
    block: Optional[BlockDescriptor]
    text_score: float
    coverage: float
    alignment_score: float


def _span_text(spans: Sequence[ParserSpan]) -> str:
    return "\n".join(span.text for span in spans if span.text).strip()


def _span_bbox(spans: Sequence[ParserSpan]) -> Optional[BBox]:
    boxes = [span.bbox for span in spans if span.bbox is not None]
    return union_bbox(boxes) if boxes else None


def _raw_ids(spans: Sequence[ParserSpan]) -> List[str]:
    out: List[str] = []
    for span in spans:
        out.extend(span.raw_span_ids or [span.span_id])
    return out


def _compact_len(text: str) -> int:
    return len(compact_text(text or ""))


def _length_coverage(a: str, b: str) -> float:
    a_len = _compact_len(a)
    b_len = _compact_len(b)
    if a_len <= 0 or b_len <= 0:
        return 0.0
    return min(a_len, b_len) / max(a_len, b_len)


def _looks_like_boundary(span: ParserSpan) -> bool:
    text = span.text.strip()
    if not text:
        return True
    if HEADING_RE.match(text) or SECTION_RE.match(text) or CAPTION_RE.match(text):
        return True
    if len(text) <= 3 and not any(ch.isalpha() for ch in text):
        return True
    return False


def _has_instruction(span: ParserSpan) -> bool:
    return compute_instructionality(span.text).score > 0


def _page_blocks(page: Optional[int], blocks: Sequence[BlockDescriptor]) -> List[BlockDescriptor]:
    if page is None:
        return list(blocks)
    same_page = [block for block in blocks if block.page == page]
    return same_page or list(blocks)


def _best_window(
    spans: Sequence[ParserSpan],
    start: int,
    blocks: Sequence[BlockDescriptor],
    config: DetectionConfig,
) -> _WindowCandidate:
    best = _WindowCandidate(end=start + 1, block=None, text_score=0.0, coverage=0.0, alignment_score=0.0)
    first = spans[start]
    candidates = _page_blocks(first.page, blocks)
    if not candidates:
        return best

    max_end = min(len(spans), start + max(1, config.parser_aggregation_max_spans))
    for end in range(start + 1, max_end + 1):
        window = spans[start:end]
        if end > start + 1 and any(_has_instruction(span) for span in window[1:]):
            break
        if end > start + 1 and _looks_like_boundary(window[-1]) and not _looks_like_boundary(window[0]):
            break

        text = _span_text(window)
        if not text:
            continue
        for block in candidates:
            block_text = block.rendered_text_estimate or block.text
            text_score = block_text_match_score(text, block_text)
            coverage = _length_coverage(text, block_text)
            alignment_score = 0.65 * text_score + 0.35 * coverage
            if block.block_role in {"formula", "table"}:
                alignment_score += 0.03 * min(1.0, coverage)
            if (
                alignment_score > best.alignment_score + 1e-9
                or (
                    abs(alignment_score - best.alignment_score) <= 1e-9
                    and coverage > best.coverage
                )
            ):
                best = _WindowCandidate(end=end, block=block, text_score=text_score, coverage=coverage, alignment_score=alignment_score)
    return best


def _make_aggregated_span(index: int, spans: Sequence[ParserSpan], candidate: _WindowCandidate) -> ParserSpan:
    text = _span_text(spans)
    source_hint = f"aggregated_from:{','.join(_raw_ids(spans))}"
    if candidate.block is not None:
        source_hint += (
            f"; visual_hint:{candidate.block.block_id}; "
            f"text_score:{candidate.text_score:.6f}; coverage:{candidate.coverage:.6f}"
        )
    return ParserSpan(
        span_id=f"psg{index:05d}",
        parser_name=spans[0].parser_name,
        page=spans[0].page,
        text=text,
        normalized_text=normalize_text(text),
        order=spans[0].order,
        bbox=_span_bbox(spans),
        source_hint=source_hint,
        raw_span_ids=_raw_ids(spans),
        aggregation_level="parser_block",
    )


def _clone_raw_as_aggregate(index: int, span: ParserSpan, reason: str) -> ParserSpan:
    return ParserSpan(
        span_id=f"psg{index:05d}",
        parser_name=span.parser_name,
        page=span.page,
        text=span.text,
        normalized_text=span.normalized_text,
        order=span.order,
        bbox=span.bbox,
        source_hint=f"{reason}:{span.span_id}",
        raw_span_ids=span.raw_span_ids or [span.span_id],
        aggregation_level="parser_block",
    )


def _aggregate_page_spans(
    page_spans: Sequence[ParserSpan],
    blocks: Sequence[BlockDescriptor],
    config: DetectionConfig,
    start_index: int,
) -> List[ParserSpan]:
    out: List[ParserSpan] = []
    index = start_index
    i = 0
    while i < len(page_spans):
        span = page_spans[i]
        if _has_instruction(span):
            out.append(_clone_raw_as_aggregate(index, span, "instruction_boundary"))
            index += 1
            i += 1
            continue
        if _looks_like_boundary(span):
            out.append(_clone_raw_as_aggregate(index, span, "parser_boundary"))
            index += 1
            i += 1
            continue

        candidate = _best_window(page_spans, i, blocks, config)
        can_group = (
            candidate.end > i + 1
            and candidate.text_score >= config.parser_aggregation_match_threshold
            and candidate.coverage >= config.parser_aggregation_min_coverage
        )
        if can_group:
            group = page_spans[i : candidate.end]
            out.append(_make_aggregated_span(index, group, candidate))
            index += 1
            i = candidate.end
            continue

        out.append(_clone_raw_as_aggregate(index, span, "single_span"))
        index += 1
        i += 1
    return out


def aggregate_parser_spans(
    spans: List[ParserSpan],
    blocks: Sequence[BlockDescriptor],
    config: Optional[DetectionConfig] = None,
) -> List[ParserSpan]:
    config = config or DetectionConfig()
    if not config.enable_parser_aggregation or not spans:
        return spans

    by_page: Dict[Optional[int], List[ParserSpan]] = {}
    for span in spans:
        by_page.setdefault(span.page, []).append(span)

    out: List[ParserSpan] = []
    next_index = 1
    for page in sorted(by_page, key=lambda item: (-1 if item is None else item)):
        page_spans = sorted(by_page[page], key=lambda span: span.order)
        page_out = _aggregate_page_spans(page_spans, blocks, config, next_index)
        out.extend(page_out)
        next_index += len(page_out)
    return out
