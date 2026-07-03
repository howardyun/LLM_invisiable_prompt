"""Text normalization, similarity, intent, and gap extraction."""

from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Any

from rapidfuzz import fuzz

from detector_config import (
    CONTROL_PATTERNS,
    GAP_VERIFY_SIMILARITY,
    MIN_GAP_CHARS,
    MIN_GAP_WORDS,
)


MATH_OPERATOR_CHARS = set(
    "\u2208\u2209\u220b\u220c\u2211\u220f\u221a\u221e\u2248\u2260\u2264\u2265\u00b1\u00d7\u00f7"
    "\u2192\u2190\u2194\u21d2\u21d4\u2200\u2203\u2202\u2207\u2205\u2217\u2219\u22c5\u221d"
    "\u2227\u2228\u2282\u2283\u2286\u2287\u222a\u2229\u222b\u222e\u2234\u2235\u2295\u2297"
    "\u2218\u22a5\u2225\u2220\u22a2\u22a8\u2261\u2243\u2245\u223c\u22bb\u2299\u22a4"
)

FORMULA_SYNTAX_CHARS = set("()[]{}_=+-*/^|<>\u2032'\u2019`,.;:")

ASCII_MATH_PATTERNS = [
    r"\b[A-Za-z]\s*\(\s*[A-Za-z0-9]+\s*\)",
    r"\b[A-Za-z]+\s*\(\s*[^)]*[\u00b7,][^)]*\)",
    r"[\u02c6\u0302][A-Za-z0-9]",
    r"\b(argmax|argmin|log|exp|softmax|sum|prod)\b",
    r"\|\|.*?\|\|",
    r"[A-Za-z0-9]\s*[+\-\u2212*/=]\s*[A-Za-z0-9]",
    r"[A-Za-z]\s*[_^]\s*[A-Za-z0-9]",
    r"[\u27e8\u27e9]",
]


def normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching.

    The detector cares about semantic visibility differences, not whitespace,
    hyphenation, or common ligature artifacts.
    """

    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\ufb01", "fi").replace("\ufb02", "fl")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text.lower()).strip()


def compute_similarity(a: str, b: str) -> float:
    """Token-set similarity in [0, 1]."""

    a_norm, b_norm = normalize_text(a), normalize_text(b)
    if not a_norm and not b_norm:
        return 1.0
    if not a_norm or not b_norm:
        return 0.0
    return fuzz.token_set_ratio(a_norm, b_norm) / 100.0


def compute_partial_similarity(a: str, b: str) -> float:
    """Partial similarity in [0, 1], useful when OCR crop includes context."""

    a_norm, b_norm = normalize_text(a), normalize_text(b)
    if not a_norm and not b_norm:
        return 1.0
    if not a_norm or not b_norm:
        return 0.0
    return fuzz.partial_ratio(a_norm, b_norm) / 100.0


def compute_length_ratio(a: str, b: str) -> float:
    """Length ratio in [0, 1]."""

    a_len, b_len = len(normalize_text(a)), len(normalize_text(b))
    if a_len == 0 and b_len == 0:
        return 1.0
    if a_len == 0 or b_len == 0:
        return 0.0
    return min(a_len, b_len) / max(a_len, b_len)


def detect_control_intent(text: str) -> float:
    """Return 1.0 if text contains known prompt-control phrasing."""

    normalized = normalize_text(text)
    return 1.0 if any(re.search(pattern, normalized, re.I) for pattern in CONTROL_PATTERNS) else 0.0


def extract_control_snippets(text: str) -> list[dict[str, Any]]:
    """Return matched control-intent snippets from original-ish text."""

    snippets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pattern in CONTROL_PATTERNS:
        try:
            matches = list(re.finditer(pattern, text or "", flags=re.I))
        except re.error:
            continue
        for match in matches:
            snippet = re.sub(r"\s+", " ", match.group(0)).strip()
            key = normalize_text(snippet)
            if not key or key in seen:
                continue
            seen.add(key)
            snippets.append(
                {
                    "pattern": pattern,
                    "start": match.start(),
                    "end": match.end(),
                    "text": snippet,
                }
            )
    return snippets



def _is_math_unicode_char(char: str) -> bool:
    """Return whether a character strongly indicates math notation."""

    if char in MATH_OPERATOR_CHARS:
        return True
    try:
        name = unicodedata.name(char)
    except ValueError:
        return False
    return any(
        marker in name
        for marker in (
            "MATHEMATICAL",
            "GREEK",
            "N-ARY",
            "SUBSCRIPT",
            "SUPERSCRIPT",
            "INTEGRAL",
            "ELEMENT OF",
            "SET MINUS",
        )
    )


def inline_math_gap_metrics(text: str) -> dict[str, Any]:
    """Measure whether a missing span looks like inline math, not prose.

    Inline equations are often embedded in Docling ``text`` regions rather than
    ``formula`` regions. RapidOCR can see the crop but misread symbols, so those
    spans should be reviewed/debugged instead of becoming suspicious findings.
    """

    compact = re.sub(r"\s+", " ", text or "").strip()
    nonspace_chars = [char for char in compact if not char.isspace()]
    math_flags = [_is_math_unicode_char(char) for char in nonspace_chars]
    syntax_flags = [char in FORMULA_SYNTAX_CHARS for char in nonspace_chars]
    normalized_compact = unicodedata.normalize("NFKC", compact)
    ascii_words = re.findall(r"[A-Za-z]{3,}", normalized_compact)
    ascii_math_hits = []
    for pattern in ASCII_MATH_PATTERNS:
        ascii_math_hits.extend(match.group(0) for match in re.finditer(pattern, normalized_compact, flags=re.I))
    control_snippets = extract_control_snippets(compact)
    length = len(nonspace_chars)
    math_count = sum(math_flags)
    syntax_count = sum(syntax_flags)
    math_or_syntax_count = sum(math_flag or syntax_flag for math_flag, syntax_flag in zip(math_flags, syntax_flags))
    math_ratio = (math_count / length) if length else 0.0
    syntax_ratio = (math_or_syntax_count / length) if length else 0.0
    return {
        "length": length,
        "math_char_count": math_count,
        "formula_syntax_count": syntax_count,
        "math_ratio": round(math_ratio, 4),
        "math_or_syntax_ratio": round(syntax_ratio, 4),
        "ascii_word_count": len(ascii_words),
        "ascii_words": ascii_words,
        "ascii_math_indicator_count": len(ascii_math_hits),
        "ascii_math_indicators": ascii_math_hits[:10],
        "control_snippets": control_snippets,
    }


def is_inline_math_gap(text: str) -> bool:
    """Return True for parser-only gaps that are mostly inline math.

    A control-like instruction is never suppressed by this helper. Short
    fragments made of card-draw notation, set membership, or Greek/math
    symbols are treated as inline math when they contain very little prose.
    """

    metrics = inline_math_gap_metrics(text)
    if metrics["control_snippets"]:
        return False
    # The span already passed the normal gap-size filter before this helper is
    # called.  Inline formulas can be very short, so use a smaller guard here.
    if metrics["length"] < 4:
        return False

    math_count = metrics["math_char_count"]
    syntax_count = metrics["formula_syntax_count"]
    word_count = metrics["ascii_word_count"]
    ascii_math_count = metrics.get("ascii_math_indicator_count", 0)
    math_ratio = metrics["math_ratio"]
    math_or_syntax_ratio = metrics["math_or_syntax_ratio"]

    strong_math_signal = math_count >= 2 and (math_ratio >= 0.18 or math_or_syntax_ratio >= 0.35)
    symbol_heavy_fragment = math_count >= 1 and syntax_count >= 3 and math_or_syntax_ratio >= 0.45
    ascii_formula_fragment = ascii_math_count >= 1 and (word_count <= 3 or math_or_syntax_ratio >= 0.18)
    dense_ascii_formula = ascii_math_count >= 2 and word_count <= 8 and math_or_syntax_ratio >= 0.10
    little_prose = word_count <= 2
    return (little_prose and (strong_math_signal or symbol_heavy_fragment)) or ascii_formula_fragment or dense_ascii_formula

def tokenize_for_gap(text: str) -> list[dict[str, Any]]:
    """Tokenize while preserving offsets for missing-span evidence."""

    tokens: list[dict[str, Any]] = []
    normalized_source = unicodedata.normalize("NFKC", text or "")
    for match in re.finditer(r"[\w]+(?:['’][\w]+)?", normalized_source, flags=re.UNICODE):
        token = normalize_text(match.group(0))
        if token:
            tokens.append(
                {
                    "norm": token,
                    "text": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
    return tokens


def is_meaningful_gap(text: str) -> bool:
    """Ignore punctuation/bullet-only OCR differences."""

    compact = re.sub(r"\s+", " ", text or "").strip()
    if len(compact) < MIN_GAP_CHARS:
        return False
    word_count = len(re.findall(r"[\w]+", compact, flags=re.UNICODE))
    return word_count >= MIN_GAP_WORDS


def extract_parser_only_gaps(parser_text: str, ocr_text: str) -> list[dict[str, Any]]:
    """Find parser/PyMuPDF spans not aligned with OCR text."""

    parser_tokens = tokenize_for_gap(parser_text)
    ocr_tokens = tokenize_for_gap(ocr_text)
    if not parser_tokens:
        return []

    if not ocr_tokens:
        gap_text = re.sub(r"\s+", " ", parser_text or "").strip()
        if not is_meaningful_gap(gap_text):
            return []
        return [
            {
                "start": 0,
                "end": len(parser_text or ""),
                "text": gap_text,
                "missing_token_count": len(parser_tokens),
                "gap_reason": "ocr_text_empty",
            }
        ]

    parser_norm = [item["norm"] for item in parser_tokens]
    ocr_norm = [item["norm"] for item in ocr_tokens]
    matcher = difflib.SequenceMatcher(None, parser_norm, ocr_norm, autojunk=False)

    gaps: list[dict[str, Any]] = []
    for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if tag == "equal" or i1 == i2:
            continue
        start = parser_tokens[i1]["start"]
        end = parser_tokens[i2 - 1]["end"]
        gap_text = re.sub(r"\s+", " ", (parser_text or "")[start:end]).strip()
        if not is_meaningful_gap(gap_text):
            continue
        gaps.append(
            {
                "start": start,
                "end": end,
                "text": gap_text,
                "missing_token_count": i2 - i1,
                "gap_reason": f"sequence_{tag}",
            }
        )
    return gaps


def ocr_verifies_gap(gap_text: str, verify_ocr_text: str) -> tuple[bool, float]:
    """Return whether a second OCR crop visibly contains a gap text."""

    score = max(
        compute_similarity(gap_text, verify_ocr_text),
        compute_partial_similarity(gap_text, verify_ocr_text),
    )
    return score >= GAP_VERIFY_SIMILARITY, round(score, 4)
