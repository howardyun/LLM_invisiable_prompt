"""Table-region handling.

Tables in papers are OCR-hostile: Docling often emits a large ``table`` bbox and
many tiny ``text`` cells for headers, checkmarks, dashes, arrows, and numbers.
This module keeps table-specific suppression separate from normal prose logic.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from detector_config import TABLE_LABELS
from detector_geometry import intersection_area, rect_area
from detector_models import LayoutRegion, RegionalResult
from detector_text import (
    compute_length_ratio,
    compute_similarity,
    detect_control_intent,
    extract_control_snippets,
    inline_math_gap_metrics,
    is_inline_math_gap,
)

TABLE_CHILD_COVERAGE = 0.70


def build_table_contexts(regions: list[LayoutRegion]) -> list[dict[str, Any]]:
    """Collect Docling table bboxes used to classify child cell regions."""

    contexts: list[dict[str, Any]] = []
    for region in regions:
        if region.source == "docling_region" and region.label.lower() in TABLE_LABELS:
            contexts.append(
                {
                    "table_region_id": region.region_id,
                    "page_no": region.page_no,
                    "bbox": region.bbox,
                    "patch_path": region.patch_path,
                    "label": region.label,
                }
            )
    return contexts


def table_context_for_region(
    region: LayoutRegion,
    table_contexts: list[dict[str, Any]],
    min_coverage: float = TABLE_CHILD_COVERAGE,
) -> dict[str, Any] | None:
    """Return the best table context containing this region, if any."""

    if region.label.lower() in TABLE_LABELS and region.source == "docling_region":
        for context in table_contexts:
            if context["table_region_id"] == region.region_id:
                return {**context, "table_child_coverage": 1.0, "table_context_kind": "table_region"}

    area = rect_area(region.bbox)
    if area <= 0:
        return None

    best: dict[str, Any] | None = None
    best_coverage = 0.0
    for context in table_contexts:
        if context["page_no"] != region.page_no:
            continue
        coverage = intersection_area(region.bbox, context["bbox"]) / area
        if coverage > best_coverage:
            best_coverage = coverage
            best = context

    if best and best_coverage >= min_coverage:
        return {
            **best,
            "table_child_coverage": round(best_coverage, 4),
            "table_context_kind": "table_child_region",
        }
    return None


def _natural_words(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text or "")
    return re.findall(r"[A-Za-z]{3,}", normalized)


def _is_symbol_or_number_cell(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    if not compact:
        return True
    number_symbol_pattern = (
        r"[\d.,%+\-\u2212\u2013\u2014*/()\[\]{}:;<>\u2264\u2265=|]+"
    )
    mark_arrow_pattern = (
        r"[\u2713\u2714\u2717\u00d7xX\-\u2212\u2013\u2014"
        r"\u2192\u2190\u2194\u2191\u2193|/\\]+"
    )
    if re.fullmatch(number_symbol_pattern, compact):
        return True
    if re.fullmatch(mark_arrow_pattern, compact):
        return True
    if re.fullmatch(r"[IVXLCDM]+", compact, flags=re.I):
        return True
    return False


def is_table_debug_only_text(text: str) -> tuple[bool, dict[str, Any]]:
    """Classify table text that should be debug-only, not suspicious.

    Control-like content is never suppressed here.  The suppression is meant for
    table cells such as checkmarks, dashes, ``Temporal``, ``RGB``, ``62.5`` and math
    fragments whose OCR frequently fails in papers.
    """

    compact = re.sub(r"\s+", " ", text or "").strip()
    control_snippets = extract_control_snippets(compact)
    words = _natural_words(compact)
    math_metrics = inline_math_gap_metrics(compact)
    symbol_or_number = _is_symbol_or_number_cell(compact)
    inline_math = is_inline_math_gap(compact)
    short_cell = len(compact) <= 32 and len(words) <= 3
    table_noise = not control_snippets and (symbol_or_number or inline_math or short_cell)
    return table_noise, {
        "text_length": len(compact),
        "natural_word_count": len(words),
        "natural_words": words,
        "symbol_or_number_cell": symbol_or_number,
        "inline_math_like": inline_math,
        "inline_math_metrics": math_metrics,
        "control_snippets": control_snippets,
        "short_cell": short_cell,
    }


def analyze_table_region(
    region: LayoutRegion,
    ocr_text: str,
    ocr_error: str | None,
    table_context: dict[str, Any],
) -> tuple[RegionalResult, dict[str, Any]]:
    """Analyze a table or table-child region.

    Current compromise: non-control table differences are debug-only because
    table OCR is noisy.  Hidden/control-like text in a table remains suspicious.
    """

    parser_text = region.pymupdf_text or region.docling_text
    similarity = compute_similarity(parser_text, ocr_text)
    length_ratio = compute_length_ratio(parser_text, ocr_text)
    parser_control = extract_control_snippets(parser_text)
    ocr_control = extract_control_snippets(ocr_text)
    intent_score = max(
        detect_control_intent(region.docling_text),
        detect_control_intent(region.pymupdf_text),
        detect_control_intent(ocr_text),
    )
    debug_only, table_text_metrics = is_table_debug_only_text(parser_text)

    risk_type = "trusted"
    risk_score = 0.05
    reason = (
        "Table-context region is handled by table mode; non-control OCR/PyMuPDF "
        "differences are recorded for debug only and are not emitted as suspicious."
    )

    if parser_control and not ocr_control:
        risk_type = "control_intent"
        risk_score = 0.98
        reason = "Control-like PyMuPDF text appears in a table context but is not visible to OCR."
    elif ocr_error:
        reason += f" OCR error recorded as debug only: {ocr_error}"
    elif debug_only:
        reason = "Table cell/header/symbol/math fragment suppressed as trusted debug-only table content."

    record = {
        "region_id": region.region_id,
        "page_no": region.page_no,
        "label": region.label,
        "source": region.source,
        "table_mode": "control_only_suspicious",
        "table_context": table_context,
        "patch_path": region.patch_path,
        "pymupdf_text": region.pymupdf_text,
        "docling_text": region.docling_text,
        "docling_ocr_text": ocr_text,
        "ocr_error": ocr_error,
        "similarity_debug_only": round(similarity, 4),
        "length_ratio_debug_only": round(length_ratio, 4),
        "intent_score": intent_score,
        "parser_control_snippets": parser_control,
        "ocr_control_snippets": ocr_control,
        "table_text_metrics": table_text_metrics,
        "risk_type": risk_type,
        "risk_score": risk_score,
        "reason": reason,
    }

    return (
        RegionalResult(
            region_id=region.region_id,
            source=region.source,
            page_no=region.page_no,
            label=region.label,
            bbox=region.bbox,
            docling_text=region.docling_text,
            pymupdf_text=region.pymupdf_text,
            ocr_text=ocr_text,
            similarity=round(similarity, 4),
            length_ratio=round(length_ratio, 4),
            intent_score=intent_score,
            risk_type=risk_type,
            risk_score=risk_score,
            reason=reason,
            patch_path=region.patch_path,
            ocr_error=ocr_error,
            debug_note=json.dumps(record, ensure_ascii=False),
        ),
        record,
    )
