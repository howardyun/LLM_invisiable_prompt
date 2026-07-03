"""Formula-specialized intent-only helpers.

This is the conservative compromise mode: formula regions are not compared with
normal OCR token gaps, and we do not require a LaTeX OCR backend.  For now we
only ask whether the PDF text layer inside a formula region contains a
control-like instruction that the visible OCR did not verify.
"""

from __future__ import annotations

import json
from typing import Any

from detector_models import LayoutRegion, RegionalResult
from detector_text import (
    compute_length_ratio,
    compute_similarity,
    detect_control_intent,
    extract_control_snippets,
)


def analyze_formula_region(
    region: LayoutRegion,
    ocr_text: str,
    ocr_error: str | None,
    formula_recognizer: Any | None = None,
) -> tuple[RegionalResult, dict[str, Any]]:
    """Classify one formula region in intent-only mode.

    Formula OCR / TeX semantic comparison is intentionally disabled in this
    compromise version.  A formula region becomes suspicious only when PyMuPDF
    sees control-like text and normal OCR does not visibly verify it.
    """

    parser_text = region.pymupdf_text or region.docling_text
    similarity = compute_similarity(parser_text, ocr_text)
    length_ratio = compute_length_ratio(parser_text, ocr_text)

    parser_snippets = extract_control_snippets(parser_text)
    docling_snippets = extract_control_snippets(region.docling_text)
    ocr_snippets = extract_control_snippets(ocr_text)
    has_parser_control = bool(parser_snippets or docling_snippets)
    has_visible_control = bool(ocr_snippets)
    intent_score = max(
        detect_control_intent(parser_text),
        detect_control_intent(region.docling_text),
        detect_control_intent(ocr_text),
    )

    if ocr_error:
        risk_type = "formula_ambiguous"
        risk_score = 0.35
        reason = f"Formula region OCR failed; intent-only formula scan is ambiguous. {ocr_error}"
    elif has_parser_control and not has_visible_control:
        risk_type = "control_intent"
        risk_score = 0.98
        reason = "Formula region contains control-like PyMuPDF text that OCR did not visibly verify."
    elif has_parser_control and has_visible_control:
        risk_type = "trusted"
        risk_score = 0.08
        reason = "Formula region contains control-like wording, but OCR also sees it; not a hidden parser-only finding."
    else:
        risk_type = "trusted"
        risk_score = 0.05
        reason = "Formula semantic comparison is disabled; no control-like instruction was found in the formula region."

    debug = {
        "region_id": region.region_id,
        "page_no": region.page_no,
        "label": region.label,
        "formula_mode": "intent_only_no_tex_comparison",
        "patch_path": region.patch_path,
        "pymupdf_text": parser_text,
        "docling_text": region.docling_text,
        "docling_ocr_text": ocr_text,
        "parser_control_snippets": parser_snippets,
        "docling_control_snippets": docling_snippets,
        "ocr_control_snippets": ocr_snippets,
        "similarity_debug_only": round(similarity, 4),
        "length_ratio_debug_only": round(length_ratio, 4),
        "risk_type": risk_type,
        "risk_score": risk_score,
        "reason": reason,
    }

    result = RegionalResult(
        region_id=region.region_id,
        source=region.source,
        page_no=region.page_no,
        label=region.label,
        bbox=region.bbox,
        docling_text=region.docling_text,
        pymupdf_text=parser_text,
        ocr_text=ocr_text,
        similarity=round(similarity, 4),
        length_ratio=round(length_ratio, 4),
        intent_score=intent_score,
        risk_type=risk_type,
        risk_score=risk_score,
        reason=reason,
        patch_path=region.patch_path,
        ocr_error=ocr_error,
        formula_visual_latex="",
        formula_parser_latex="",
        formula_similarity=None,
        formula_error=None,
        debug_note=json.dumps(debug, ensure_ascii=False),
    )
    return result, debug
