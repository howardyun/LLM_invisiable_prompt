"""Picture-like region handling.

Most picture-like Docling regions are outside the detector's normal text
comparison scope. One exception matters for prompt-injection detection:
sometimes a PDF has a real text layer placed over an image-like region. In
that case PyMuPDF can read the hidden/control text while OCR of the rendered
image cannot. This module keeps the picture logic isolated so it can remain
conservative instead of turning every chart/figure into a noisy finding.
"""

from __future__ import annotations

import json
from typing import Any

from detector_models import LayoutRegion, RegionalResult
from detector_text import (
    compute_length_ratio,
    compute_similarity,
    extract_control_snippets,
)


def analyze_picture_region(
    region: LayoutRegion,
    ocr_text: str,
    ocr_error: str | None,
) -> tuple[RegionalResult, dict[str, Any]]:
    """Analyze a picture-like region.

    Default behavior is still trusted/debug-only. The narrow scoring rule is:
    if PyMuPDF/Docling sees control-like text over the picture but OCR does not,
    emit a suspicious ``control_intent`` result. This catches hidden text-layer
    prompts inside image regions without reopening generic picture differences.
    """

    similarity = compute_similarity(region.pymupdf_text, ocr_text)
    length_ratio = compute_length_ratio(region.pymupdf_text, ocr_text)
    parser_text = "\n".join(part for part in (region.docling_text, region.pymupdf_text) if part)
    parser_control_snippets = extract_control_snippets(parser_text)
    ocr_control_snippets = extract_control_snippets(ocr_text)
    parser_intent = 1.0 if parser_control_snippets else 0.0
    ocr_intent = 1.0 if ocr_control_snippets else 0.0
    intent_score = max(parser_intent, ocr_intent)

    has_overlaid_parser_text = bool((region.pymupdf_text or region.docling_text or "").strip())
    hidden_control_in_picture = bool(
        has_overlaid_parser_text and parser_control_snippets and not ocr_control_snippets
    )

    if hidden_control_in_picture:
        picture_mode = "scored_control_text_overlay"
        risk_type = "control_intent"
        risk_score = 0.96
        reason = (
            "Picture-like region contains overlaid PyMuPDF/Docling control-like text, "
            "but OCR of the rendered picture did not recover that control text."
        )
    else:
        picture_mode = "trusted_debug_only"
        risk_type = "trusted"
        risk_score = 0.05
        reason = (
            "Picture-like Docling region is outside the current generic detection scope; "
            "PyMuPDF/OCR differences are recorded for debug only unless overlaid "
            "control-like text is visible to the parser but not to OCR."
        )
    if ocr_error:
        reason += f" OCR error recorded as debug only: {ocr_error}"

    record = {
        "region_id": region.region_id,
        "page_no": region.page_no,
        "label": region.label,
        "picture_mode": picture_mode,
        "has_overlaid_parser_text": has_overlaid_parser_text,
        "patch_path": region.patch_path,
        "pymupdf_text": region.pymupdf_text,
        "docling_text": region.docling_text,
        "docling_ocr_text": ocr_text,
        "ocr_error": ocr_error,
        "similarity_debug_only": round(similarity, 4),
        "length_ratio_debug_only": round(length_ratio, 4),
        "intent_score_debug_only": intent_score,
        "parser_control_snippets": parser_control_snippets,
        "ocr_control_snippets": ocr_control_snippets,
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
