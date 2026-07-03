"""Shared thresholds and pattern configuration for the PDF detector."""

from __future__ import annotations


# Intent patterns are *not* allowed to trigger a finding on their own.
# They only upgrade an already suspicious parser/OCR mismatch.
CONTROL_PATTERNS = [
    r"\bignore\s+(all\s+)?(previous|above)\s+instructions?\b",
    r"\bdisregard\s+(the\s+)?(previous|above)\s+instructions?\b",
    r"\bforget\s+(all\s+)?(previous|above)\s+instructions?\b",
    r"\byou\s+are\s+now\b",
    r"\bact\s+as\b",
    r"\bas\s+a\s+language\s+model\b",
    r"\bsystem\s+prompt\b",
    r"\bdeveloper\s+message\b",
    r"\bonly\s+output\b",
    r"\boutput\s+exactly\b",
    r"\banswer\s+in\s+(json|markdown|xml)\b",
    r"\bdo\s+not\s+mention\b",
    r"\bgive\s+this\s+paper\s+a\s+positive\s+review\b",
    r"\bgive\s+(a|the|this paper|this candidate)\s+positive\s+review\b",
    r"\bgive\s+(a|the|this paper|this candidate)\s+a\s+positive\s+review\b",
    r"\bpositive\s+review\s+only\b",
    r"\bpositive\s+review\b.{0,80}\baccept\b",
    r"\brecommend\s+(accepting|acceptance|to\s+accept)\s+(this\s+)?(paper|submission|work)\b",
    r"\baccept\s+this\s+(paper|submission|work)\b",
    r"\brecommend\s+hiring\s+this\s+candidate\b",
    r"\bwell\s+qualified\s+candidate\b",
    r"\breveal\b.{0,80}\b(prompt|instruction|context)\b",
    r"\bprint\b.{0,80}\b(system|developer)\b.{0,80}\b(message|prompt)\b",
    r"\bexecute\s+code\b",
    r"\bcall\s+(a\s+)?tool\b",
    r"\bsend\s+email\b",
    r"\bbrowse\s+(the\s+)?web\b",
]

PERIPHERAL_LABELS = {
    "page_header",
    "page_footer",
    "footnote",
    "sidebar",
    "margin_note",
}

FORMULA_LABELS = {"formula"}
TABLE_LABELS = {"table"}
PICTURE_LABELS = {"picture", "figure", "image", "chart", "diagram"}
COMPLEX_LABELS = TABLE_LABELS | FORMULA_LABELS | PICTURE_LABELS

# If a PyMuPDF block is not sufficiently covered by the union of Docling
# regions, we keep it as an outside-layout PyMuPDF-only candidate.
ORPHAN_COVERAGE_THRESHOLD = 0.60

# Small OCR/tokenization differences should not create gap findings.
MIN_ORPHAN_TEXT_CHARS = 3
MIN_GAP_WORDS = 2
MIN_GAP_CHARS = 8

# A gap is suppressed when a second, tightly cropped OCR pass can see it.
GAP_VERIFY_SIMILARITY = 0.72

# Formula comparison thresholds.  Formula OCR is noisier than normal text OCR,
# so this is intentionally not as strict as natural-language matching.
FORMULA_TRUSTED_SIMILARITY = 0.62
FORMULA_MISMATCH_SIMILARITY = 0.38

CSV_FIELDS = [
    "risk_type",
    "risk_score",
    "source",
    "region_id",
    "parent_region_id",
    "page_no",
    "label",
    "similarity",
    "length_ratio",
    "intent_score",
    "pymupdf_text",
    "ocr_text",
    "verify_ocr_text",
    "verify_similarity",
    "visible_after_second_pass",
    "formula_visual_latex",
    "formula_parser_latex",
    "formula_similarity",
    "formula_error",
    "docling_text",
    "reason",
    "bbox",
    "patch_path",
    "ocr_error",
    "debug_note",
]
