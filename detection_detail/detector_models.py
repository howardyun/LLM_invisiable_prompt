"""Dataclasses used across the detector pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LayoutRegion:
    """One candidate region to crop/OCR/compare.

    source:
        - docling_region: region produced by Docling layout.
        - pymupdf_only: text-layer candidate produced from PyMuPDF.
    """

    region_id: str
    order: int
    source: str
    label: str
    page_no: int
    bbox: list[float]
    coord_origin: str
    docling_text: str = ""
    pymupdf_text: str = ""
    patch_path: str | None = None
    charspan: list[int] | None = None
    content_layer: str | None = None
    raw_ref: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RegionalResult:
    """Final row written to regional_ocr_results.* files."""

    region_id: str
    source: str
    page_no: int
    label: str
    bbox: list[float]
    docling_text: str
    pymupdf_text: str
    ocr_text: str
    similarity: float
    length_ratio: float
    intent_score: float
    risk_type: str
    risk_score: float
    reason: str
    patch_path: str | None
    ocr_error: str | None = None
    parent_region_id: str | None = None

    # Second-pass OCR diagnostics for *_gap rows.  These are deliberately kept
    # as first-class CSV columns so the tight-crop OCR output is not hidden in
    # debug_note only.
    verify_ocr_text: str | None = None
    verify_similarity: float | None = None
    visible_after_second_pass: bool | None = None

    # Formula-specialized diagnostics.  visual_latex comes from formula OCR;
    # parser_latex is the normalized PyMuPDF math text.
    formula_visual_latex: str | None = None
    formula_parser_latex: str | None = None
    formula_similarity: float | None = None
    formula_error: str | None = None

    debug_note: str | None = None
