"""Classification, gap verification, and report generation."""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from detector_config import COMPLEX_LABELS
from detector_docling import DoclingRegionalOCR
from detector_images import crop_pdf_bbox_to_image
from detector_io import compact_csv_text
from detector_models import LayoutRegion, RegionalResult
from detector_pymupdf import locate_gap_bbox_from_words
from detector_text import (
    compute_length_ratio,
    compute_similarity,
    detect_control_intent,
    extract_control_snippets,
    ocr_verifies_gap,
)


def classify_region(
    source: str,
    label: str,
    pymupdf_text: str,
    ocr_text: str,
    similarity: float,
    length_ratio: float,
    intent_score: float,
) -> tuple[str, float, str]:
    """Classify one region-level PyMuPDF/OCR comparison.

    Intent is not a standalone finding. It only upgrades an existing parser/OCR
    discrepancy. If OCR and PyMuPDF agree, the region is trusted even when the
    text contains words like "prompt" or "tool".
    """

    has_parser = bool(pymupdf_text and pymupdf_text.strip())
    has_ocr = bool(ocr_text and ocr_text.strip())
    label_norm = label.lower()

    if has_parser and not has_ocr:
        if intent_score:
            return "control_intent", 0.98, "PyMuPDF found control-like text, but OCR found no visible text."
        return "parser_only", 0.75 if source == "pymupdf_only" else 0.65, "PyMuPDF found text, but OCR found no visible text."

    if not has_parser and has_ocr:
        return "ocr_only", 0.35, "OCR found visible text, but PyMuPDF extracted no text."

    if has_parser and has_ocr and similarity < 0.45 and length_ratio < 0.60:
        if intent_score:
            return "control_intent", 0.95, "PyMuPDF/OCR mismatch includes control-like text."
        return "visual_mismatch", 0.75 if source == "pymupdf_only" else 0.70, "PyMuPDF text differs substantially from OCR text."

    if label_norm in COMPLEX_LABELS and similarity < 0.5:
        return "ambiguous", 0.45, "Complex Docling region has low PyMuPDF/OCR similarity."

    return "trusted", 0.05 if source == "docling_region" else 0.10, "PyMuPDF text is consistent with OCR."


def make_region_result(
    region: LayoutRegion,
    ocr_text: str,
    ocr_error: str | None,
) -> RegionalResult:
    """Build the normal region-level result row."""

    similarity = compute_similarity(region.pymupdf_text, ocr_text)
    length_ratio = compute_length_ratio(region.pymupdf_text, ocr_text)
    intent_score = max(
        detect_control_intent(region.docling_text),
        detect_control_intent(region.pymupdf_text),
        detect_control_intent(ocr_text),
    )
    risk_type, risk_score, reason = classify_region(
        region.source,
        region.label,
        region.pymupdf_text,
        ocr_text,
        similarity,
        length_ratio,
        intent_score,
    )
    if ocr_error:
        risk_type, risk_score = "ambiguous", max(risk_score, 0.40)
        reason = f"OCR failed; region could not be compared reliably. {ocr_error}"

    return RegionalResult(
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
    )


def _summarize_verification(records: list[dict[str, Any]]) -> tuple[str, float | None, bool | None]:
    """Flatten second-pass OCR records into CSV-friendly values."""

    if not records:
        return "", None, None
    texts = [compact_csv_text(item.get("verify_ocr_text")) for item in records if item.get("verify_ocr_text")]
    similarities = [float(item.get("verify_similarity") or 0.0) for item in records]
    visible = any(bool(item.get("visible_after_second_pass")) for item in records)
    return " | ".join(texts), round(max(similarities), 4) if similarities else None, visible


def build_gap_result(
    region: LayoutRegion,
    gaps: list[dict[str, Any]],
    verification_records: list[dict[str, Any]],
) -> RegionalResult:
    """Build a PyMuPDF-only gap result after second-pass OCR verification."""

    gap_text = " | ".join(item["text"] for item in gaps) or region.pymupdf_text
    control_snippets = extract_control_snippets(gap_text)
    has_control = bool(control_snippets)
    verify_ocr_text, verify_similarity, visible_after_second_pass = _summarize_verification(verification_records)
    return RegionalResult(
        region_id=f"{region.region_id}_gap01",
        source="pymupdf_only",
        parent_region_id=region.region_id,
        page_no=region.page_no,
        label="pymupdf_only_ocr_gap",
        bbox=verification_records[0].get("verify_bbox", region.bbox) if verification_records else region.bbox,
        docling_text=region.docling_text,
        pymupdf_text=gap_text,
        ocr_text="",
        verify_ocr_text=verify_ocr_text,
        verify_similarity=verify_similarity,
        visible_after_second_pass=visible_after_second_pass,
        similarity=0.0,
        length_ratio=0.0,
        intent_score=1.0 if has_control else 0.0,
        risk_type="control_intent" if has_control else "parser_only",
        risk_score=0.98 if has_control else 0.80,
        reason=(
            "Control-like PyMuPDF text is still missing after second-pass OCR verification."
            if has_control
            else "PyMuPDF text is still missing after second-pass OCR verification."
        ),
        patch_path=verification_records[0].get("verify_patch_path") if verification_records else region.patch_path,
        debug_note=json.dumps(
            {
                "gap_kind": "parser_text_missing_from_ocr_after_second_pass",
                "parent_region_id": region.region_id,
                "gaps": gaps,
                "control_snippets": control_snippets,
                "verification_records": verification_records,
            },
            ensure_ascii=False,
        ),
    )


def verify_region_gaps(
    region: LayoutRegion,
    gaps: list[dict[str, Any]],
    all_words: list[dict],
    page_images: dict[int, Path],
    patches_dir: Path,
    dpi: int,
    padding_points: float,
    ocr: DoclingRegionalOCR,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Second-pass OCR every missing gap using its PyMuPDF word bbox.

    If this tight crop sees the text, the gap is suppressed as a visible OCR
    miss from the larger region patch. If it still does not see the text, the
    gap remains suspicious.
    """

    verified_visible: list[dict[str, Any]] = []
    still_missing: list[dict[str, Any]] = []
    page_path = page_images.get(region.page_no)
    if not page_path:
        return verified_visible, gaps

    for gap_index, gap in enumerate(gaps, start=1):
        location = locate_gap_bbox_from_words(all_words, region, gap["text"])
        verify_bbox = [round(float(v), 3) for v in location["bbox"]]
        verify_patch = patches_dir / f"{region.region_id}_gap{gap_index:02d}_verify.png"

        try:
            crop_meta = crop_pdf_bbox_to_image(
                page_path,
                verify_bbox,
                verify_patch,
                dpi,
                padding_points,
            )
            verify_ocr_text, verify_error, _records = ocr.recognize_one(verify_patch)
        except Exception as exc:
            verify_ocr_text, verify_error, crop_meta = "", f"{type(exc).__name__}: {exc}", {}

        visible, verify_similarity = ocr_verifies_gap(gap["text"], verify_ocr_text)
        record = {
            **gap,
            "verify_bbox": verify_bbox,
            "verify_patch_path": verify_patch.as_posix(),
            "verify_ocr_text": compact_csv_text(verify_ocr_text),
            "verify_ocr_error": verify_error,
            "verify_similarity": verify_similarity,
            "visible_after_second_pass": visible,
            "word_location": {
                "match_strategy": location.get("match_strategy"),
                "search_scope": location.get("search_scope"),
                "word_window_similarity": location.get("word_window_similarity"),
                "matched_word_count": len(location.get("matched_words") or []),
            },
            "crop_meta": crop_meta,
        }
        if visible:
            verified_visible.append(record)
        else:
            still_missing.append(record)

    return verified_visible, still_missing


def aggregate_risk(results: list[RegionalResult]) -> tuple[str, float]:
    if not results:
        return "Low", 0.0
    scores = sorted((item.risk_score for item in results), reverse=True)
    top = scores[:5]
    score = 0.7 * scores[0] + 0.3 * (sum(top) / len(top))
    if score >= 0.85:
        return "Critical", score
    if score >= 0.65:
        return "High", score
    if score >= 0.40:
        return "Medium", score
    return "Low", score


def build_report(
    pdf_path: Path,
    results: list[RegionalResult],
    elapsed_seconds: float,
    device: str,
) -> dict[str, Any]:
    """Build final JSON report."""

    risk_level, risk_score = aggregate_risk(results)
    counts = Counter(item.risk_type for item in results)
    suspicious = sorted(
        (item for item in results if item.risk_type != "trusted"),
        key=lambda item: item.risk_score,
        reverse=True,
    )
    return {
        "pdf_path": str(pdf_path.resolve()),
        "layout_source": "Docling",
        "text_parser": "PyMuPDF clipped to Docling regions plus PyMuPDF word/block diagnostics",
        "regional_ocr": "Docling RapidOCR (torch backend)",
        "formula_ocr": "Pix2Text recognize_formula when installed; PyMuPDF math text normalized to formula tokens",
        "gap_verification": "PyMuPDF word bbox -> tight crop -> second-pass Docling OCR",
        "device": device,
        "risk_level": risk_level,
        "risk_score": round(risk_score, 4),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "summary": {
            "total_regions": len(results),
            "docling_regions": sum(item.source == "docling_region" for item in results),
            "pymupdf_only_regions": sum(item.source == "pymupdf_only" for item in results),
            "suspicious_regions": len(suspicious),
            "trusted_regions": counts["trusted"],
            "parser_only_regions": counts["parser_only"],
            "visual_mismatch_regions": counts["visual_mismatch"],
            "formula_mismatch_regions": counts["formula_mismatch"],
            "formula_ambiguous_regions": counts["formula_ambiguous"],
            "control_intent_type_regions": counts["control_intent"],
            "ocr_only_regions": counts["ocr_only"],
            "ambiguous_regions": counts["ambiguous"],
            "control_intent_regions": sum(item.intent_score > 0 for item in results),
            "ocr_error_regions": sum(bool(item.ocr_error) for item in results),
        },
        "suspicious_regions": [asdict(item) for item in suspicious],
        "generated_at_unix": time.time(),
    }
