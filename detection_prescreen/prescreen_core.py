"""Cheap PDF pre-screening for likely hidden prompt-injection content.

This module deliberately avoids OCR.  It only uses PyMuPDF text extraction,
span style metadata, annotations, metadata, and decoded page content streams to
find candidates that are worth sending to OCR verification.
"""

from __future__ import annotations

import csv
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import fitz


try:
    from .prescreen_patterns import extract_control_snippets, normalize_text
except ImportError:
    from prescreen_patterns import extract_control_snippets, normalize_text


CSV_FIELDS = [
    "candidate_id",
    "page_no",
    "kind",
    "score",
    "needs_ocr",
    "text",
    "control_snippets",
    "reason",
    "bbox",
    "font_size",
    "font",
    "color_rgb",
    "alpha",
    "source",
]


@dataclass(frozen=True)
class PrescreenConfig:
    """Thresholds for the non-OCR pre-screen."""

    max_pages: int | None = None
    candidate_threshold: float = 0.55
    ocr_threshold: float = 0.65
    tiny_font_size: float = 3.5
    very_tiny_font_size: float = 2.0
    near_white_channel: int = 245
    low_alpha: int = 80
    hidden_text_min_chars: int = 12
    max_candidates: int = 200


@dataclass
class Candidate:
    """One suspicious text/style/content candidate."""

    candidate_id: str
    page_no: int | None
    kind: str
    score: float
    needs_ocr: bool
    text: str
    control_snippets: list[dict[str, Any]] = field(default_factory=list)
    reason: list[str] = field(default_factory=list)
    bbox: list[float] | None = None
    font_size: float | None = None
    font: str | None = None
    color_rgb: list[int] | None = None
    alpha: int | None = None
    source: str = "text"
    extra: dict[str, Any] = field(default_factory=dict)


def scan_pdf_prescreen(pdf_path: Path, config: PrescreenConfig) -> dict[str, Any]:
    """Run the fast pre-screen and return a JSON-serializable report."""

    started = time.time()
    pdf_path = Path(pdf_path).expanduser().resolve()
    candidates: list[Candidate] = []
    page_stats: list[dict[str, Any]] = []

    with fitz.open(pdf_path) as doc:
        page_count = min(len(doc), config.max_pages) if config.max_pages else len(doc)
        _scan_metadata(doc, candidates, config)

        for page_index in range(page_count):
            page_no = page_index + 1
            page = doc[page_index]
            before = len(candidates)
            candidates.extend(_scan_page_spans(page, page_no, config))
            candidates.extend(_scan_page_blocks(page, page_no, config))
            candidates.extend(_scan_page_stream(page, page_no, config))
            candidates.extend(_scan_page_annotations(page, page_no, config))
            page_stats.append(
                {
                    "page_no": page_no,
                    "candidate_count": len(candidates) - before,
                    **_page_text_stats(page),
                }
            )

        ocg_count = 0
        try:
            ocg_count = len(doc.get_ocgs() or {})
        except Exception:
            ocg_count = 0

    candidates = _dedupe_and_limit(candidates, config.max_candidates)
    candidates.sort(key=lambda item: (-item.score, item.page_no or 0, item.candidate_id))
    for index, candidate in enumerate(candidates, start=1):
        candidate.candidate_id = f"c{index:05d}"

    selected = [item for item in candidates if item.needs_ocr]
    risk_level, risk_score = _aggregate_risk(candidates)
    return {
        "pdf_path": str(pdf_path),
        "mode": "pymupdf_prescreen_no_ocr",
        "elapsed_seconds": round(time.time() - started, 4),
        "page_count_scanned": len(page_stats),
        "risk_level": risk_level,
        "risk_score": risk_score,
        "should_run_ocr": bool(selected),
        "candidate_count": len(candidates),
        "ocr_candidate_count": len(selected),
        "ocg_count": ocg_count,
        "summary": _candidate_summary(candidates),
        "page_stats": page_stats,
        "candidates": [asdict(item) for item in candidates],
    }


def write_prescreen_outputs(run_dir: Path, report: dict[str, Any]) -> None:
    """Write report JSON and a compact candidates CSV."""

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prescreen_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (run_dir / "prescreen_candidates.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for candidate in report.get("candidates", []):
            writer.writerow(
                {
                    "candidate_id": candidate.get("candidate_id", ""),
                    "page_no": candidate.get("page_no", ""),
                    "kind": candidate.get("kind", ""),
                    "score": candidate.get("score", ""),
                    "needs_ocr": candidate.get("needs_ocr", ""),
                    "text": _csv_text(candidate.get("text", "")),
                    "control_snippets": _csv_text(
                        " | ".join(item.get("text", "") for item in candidate.get("control_snippets", []))
                    ),
                    "reason": _csv_text(" | ".join(candidate.get("reason", []))),
                    "bbox": json.dumps(candidate.get("bbox"), ensure_ascii=False),
                    "font_size": candidate.get("font_size", ""),
                    "font": candidate.get("font", ""),
                    "color_rgb": json.dumps(candidate.get("color_rgb"), ensure_ascii=False),
                    "alpha": candidate.get("alpha", ""),
                    "source": candidate.get("source", ""),
                }
            )


def _scan_metadata(doc: fitz.Document, out: list[Candidate], config: PrescreenConfig) -> None:
    for key, value in (doc.metadata or {}).items():
        text = str(value or "").strip()
        if not text:
            continue
        snippets = extract_control_snippets(text)
        if not snippets:
            continue
        out.append(
            Candidate(
                candidate_id="pending",
                page_no=None,
                kind="metadata_control_intent",
                score=0.78,
                needs_ocr=False,
                text=text,
                control_snippets=snippets,
                reason=[f"metadata field contains control-like text: {key}"],
                source="metadata",
                extra={"metadata_key": key},
            )
        )


def _scan_page_spans(page: fitz.Page, page_no: int, config: PrescreenConfig) -> list[Candidate]:
    candidates: list[Candidate] = []
    hidden_bucket: list[dict[str, Any]] = []
    try:
        page_dict = page.get_text("dict")
    except Exception:
        return candidates

    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            line_spans = [span for span in line.get("spans", []) if str(span.get("text") or "").strip()]
            if line_spans:
                line_candidate = _candidate_from_line(line_spans, page.rect, page_no, config)
                if line_candidate:
                    candidates.append(line_candidate)
            for span in line_spans:
                candidate = _candidate_from_span(span, page.rect, page_no, config)
                if candidate:
                    candidates.append(candidate)
                if _is_hiddenish_span(span, page.rect, config):
                    hidden_bucket.append(span)

    bulk = _candidate_from_hidden_bucket(hidden_bucket, page_no, config)
    if bulk:
        candidates.append(bulk)
    return candidates


def _scan_page_blocks(page: fitz.Page, page_no: int, config: PrescreenConfig) -> list[Candidate]:
    candidates: list[Candidate] = []
    for raw_block in page.get_text("blocks", sort=True):
        if len(raw_block) < 5:
            continue
        text = str(raw_block[4] or "").strip()
        if not text:
            continue
        snippets = extract_control_snippets(text)
        if not snippets:
            continue
        bbox = [round(float(v), 3) for v in raw_block[:4]]
        candidates.append(
            Candidate(
                candidate_id="pending",
                page_no=page_no,
                kind="visible_text_control_intent",
                score=0.68,
                needs_ocr=True,
                text=text,
                control_snippets=snippets,
                reason=["PyMuPDF text block contains control-like instruction"],
                bbox=bbox,
                source="pymupdf_block",
            )
        )
    return candidates


def _scan_page_stream(page: fitz.Page, page_no: int, config: PrescreenConfig) -> list[Candidate]:
    candidates: list[Candidate] = []
    try:
        stream_text = (page.read_contents() or b"").decode("latin1", "ignore")
    except Exception:
        return candidates

    if re.search(r"(?<![\d.])3\s+Tr\b", stream_text):
        candidates.append(
            Candidate(
                candidate_id="pending",
                page_no=page_no,
                kind="invisible_text_render_mode",
                score=0.76,
                needs_ocr=True,
                text="",
                reason=["page content stream uses PDF text rendering mode 3 (invisible text)"],
                bbox=[round(page.rect.x0, 3), round(page.rect.y0, 3), round(page.rect.x1, 3), round(page.rect.y1, 3)],
                source="content_stream",
            )
        )

    has_actual_text = "/ActualText" in stream_text
    has_optional_content = "/OC" in stream_text and "BDC" in stream_text
    has_marked_content = "BDC" in stream_text or "BMC" in stream_text
    if has_actual_text:
        compact = _compact_pdf_stream_text(stream_text)
        candidates.append(
            Candidate(
                candidate_id="pending",
                page_no=page_no,
                kind="actualtext_replacement_layer",
                score=0.74,
                needs_ocr=True,
                text=_trim(compact, 1200),
                control_snippets=extract_control_snippets(compact),
                reason=["page content stream contains /ActualText replacement text"],
                bbox=[round(page.rect.x0, 3), round(page.rect.y0, 3), round(page.rect.x1, 3), round(page.rect.y1, 3)],
                source="content_stream",
            )
        )
    elif has_optional_content:
        candidates.append(
            Candidate(
                candidate_id="pending",
                page_no=page_no,
                kind="optional_content_layer",
                score=0.68,
                needs_ocr=True,
                text="",
                reason=["page content stream uses optional-content layer markers (/OC ... BDC)"],
                bbox=[round(page.rect.x0, 3), round(page.rect.y0, 3), round(page.rect.x1, 3), round(page.rect.y1, 3)],
                source="content_stream",
            )
        )
    elif has_marked_content and not (page.get_text("text") or "").strip():
        candidates.append(
            Candidate(
                candidate_id="pending",
                page_no=page_no,
                kind="marked_content_without_extracted_text",
                score=0.64,
                needs_ocr=False,
                text="",
                reason=["page has marked content but PyMuPDF extracted no visible text"],
                bbox=[round(page.rect.x0, 3), round(page.rect.y0, 3), round(page.rect.x1, 3), round(page.rect.y1, 3)],
                source="content_stream",
            )
        )
    normalized_stream = _compact_pdf_stream_text(stream_text)
    snippets = extract_control_snippets(normalized_stream)
    if snippets:
        candidates.append(
            Candidate(
                candidate_id="pending",
                page_no=page_no,
                kind="content_stream_control_intent",
                score=0.82,
                needs_ocr=True,
                text=_trim(normalized_stream, 1200),
                control_snippets=snippets[:8],
                reason=["decoded page content stream contains control-like text"],
                bbox=[round(page.rect.x0, 3), round(page.rect.y0, 3), round(page.rect.x1, 3), round(page.rect.y1, 3)],
                source="content_stream",
            )
        )
    return candidates


def _scan_page_annotations(page: fitz.Page, page_no: int, config: PrescreenConfig) -> list[Candidate]:
    candidates: list[Candidate] = []
    try:
        annotations = list(page.annots() or [])
    except Exception:
        return candidates
    for annot in annotations:
        info = annot.info or {}
        text = " ".join(str(info.get(key) or "") for key in ("title", "subject", "content")).strip()
        snippets = extract_control_snippets(text)
        if not snippets:
            continue
        rect = annot.rect
        candidates.append(
            Candidate(
                candidate_id="pending",
                page_no=page_no,
                kind="annotation_control_intent",
                score=0.80,
                needs_ocr=False,
                text=text,
                control_snippets=snippets,
                reason=["PDF annotation contains control-like text"],
                bbox=[round(rect.x0, 3), round(rect.y0, 3), round(rect.x1, 3), round(rect.y1, 3)],
                source="annotation",
            )
        )
    return candidates


def _candidate_from_line(
    spans: list[dict[str, Any]],
    page_rect: fitz.Rect,
    page_no: int,
    config: PrescreenConfig,
) -> Candidate | None:
    text = " ".join(str(span.get("text") or "").strip() for span in spans).strip()
    if not text:
        return None
    snippets = extract_control_snippets(text)
    hidden_signals = [_span_signals(span, page_rect, config) for span in spans]
    reasons = sorted({reason for signals in hidden_signals for reason in signals})
    if not snippets and not reasons:
        return None

    score = 0.0
    if snippets:
        score += 0.66
    if reasons:
        score += 0.28
    if snippets and reasons:
        score += 0.14
    if len(normalize_text(text)) >= config.hidden_text_min_chars and any("near-white" in item for item in reasons):
        score += 0.12
    score = min(score, 0.99)
    if score < config.candidate_threshold:
        return None

    bbox = _bbox_union([span.get("bbox") for span in spans])
    return Candidate(
        candidate_id="pending",
        page_no=page_no,
        kind="line_control_or_hidden_style",
        score=round(score, 4),
        needs_ocr=score >= config.ocr_threshold,
        text=_trim(text),
        control_snippets=snippets,
        reason=reasons or ["line contains control-like instruction"],
        bbox=bbox,
        font_size=round(min(float(span.get("size") or 0.0) for span in spans), 4),
        font=str(spans[0].get("font") or ""),
        color_rgb=_rgb_from_int(int(spans[0].get("color") or 0)),
        alpha=_span_alpha(spans[0]),
        source="pymupdf_line",
    )


def _candidate_from_span(
    span: dict[str, Any],
    page_rect: fitz.Rect,
    page_no: int,
    config: PrescreenConfig,
) -> Candidate | None:
    text = str(span.get("text") or "").strip()
    if not text:
        return None

    snippets = extract_control_snippets(text)
    reasons = _span_signals(span, page_rect, config)
    if not snippets and not reasons:
        return None

    has_letters = bool(re.search(r"[A-Za-z\u4e00-\u9fff]", text))
    normalized_len = len(normalize_text(text))
    score = 0.0
    if snippets:
        score += 0.68
    if "near-white text color" in reasons:
        score += 0.36 if has_letters or normalized_len >= config.hidden_text_min_chars else 0.24
    if "low alpha text" in reasons:
        score += 0.50
    if "very tiny font" in reasons:
        score += 0.34 if has_letters else 0.16
    elif "tiny font" in reasons:
        score += 0.24 if has_letters and normalized_len >= 4 else 0.10
    if "bbox outside page" in reasons:
        score += 0.42
    if snippets and reasons:
        score += 0.16
    score = min(score, 0.99)
    if score < config.candidate_threshold:
        return None

    bbox = [round(float(value), 3) for value in span.get("bbox", [])] or None
    return Candidate(
        candidate_id="pending",
        page_no=page_no,
        kind="span_control_or_hidden_style",
        score=round(score, 4),
        needs_ocr=score >= config.ocr_threshold,
        text=_trim(text),
        control_snippets=snippets,
        reason=reasons or ["span contains control-like instruction"],
        bbox=bbox,
        font_size=round(float(span.get("size") or 0.0), 4),
        font=str(span.get("font") or ""),
        color_rgb=_rgb_from_int(int(span.get("color") or 0)),
        alpha=_span_alpha(span),
        source="pymupdf_span",
    )


def _candidate_from_hidden_bucket(
    spans: list[dict[str, Any]],
    page_no: int,
    config: PrescreenConfig,
) -> Candidate | None:
    if not spans:
        return None
    texts = [str(span.get("text") or "").strip() for span in spans if str(span.get("text") or "").strip()]
    joined = " ".join(texts)
    if len(normalize_text(joined)) < config.hidden_text_min_chars:
        return None
    has_letters = bool(re.search(r"[A-Za-z\u4e00-\u9fff]", joined))
    if not has_letters and len(texts) < 8:
        return None
    score = 0.62 if has_letters else 0.42
    snippets = extract_control_snippets(joined)
    if snippets:
        score = 0.92
    if score < config.candidate_threshold:
        return None
    return Candidate(
        candidate_id="pending",
        page_no=page_no,
        kind="page_hidden_style_text_cluster",
        score=round(score, 4),
        needs_ocr=score >= config.ocr_threshold,
        text=_trim(joined, 1200),
        control_snippets=snippets,
        reason=[f"page has {len(spans)} hidden-style text spans"],
        bbox=_bbox_union([span.get("bbox") for span in spans]),
        source="pymupdf_span_cluster",
        extra={"hidden_style_span_count": len(spans)},
    )


def _span_signals(span: dict[str, Any], page_rect: fitz.Rect, config: PrescreenConfig) -> list[str]:
    reasons: list[str] = []
    size = float(span.get("size") or 0.0)
    if 0 < size <= config.very_tiny_font_size:
        reasons.append("very tiny font")
    elif 0 < size <= config.tiny_font_size:
        reasons.append("tiny font")

    rgb = _rgb_from_int(int(span.get("color") or 0))
    if all(channel >= config.near_white_channel for channel in rgb):
        reasons.append("near-white text color")

    alpha = _span_alpha(span)
    if alpha is not None and alpha <= config.low_alpha:
        reasons.append("low alpha text")

    bbox = span.get("bbox")
    if bbox and not _bbox_intersects_page(bbox, page_rect):
        reasons.append("bbox outside page")
    return reasons


def _is_hiddenish_span(span: dict[str, Any], page_rect: fitz.Rect, config: PrescreenConfig) -> bool:
    signals = _span_signals(span, page_rect, config)
    return any(signal in signals for signal in ("near-white text color", "low alpha text", "bbox outside page"))


def _page_text_stats(page: fitz.Page) -> dict[str, Any]:
    text = page.get_text("text") or ""
    return {
        "text_chars": len(text),
        "text_words": len(re.findall(r"\w+", text)),
    }


def _dedupe_and_limit(candidates: list[Candidate], limit: int) -> list[Candidate]:
    best: dict[tuple[Any, ...], Candidate] = {}
    for candidate in candidates:
        key = (
            candidate.page_no,
            candidate.kind,
            tuple(round(float(value), 1) for value in candidate.bbox or []),
            normalize_text(candidate.text)[:160],
        )
        current = best.get(key)
        if current is None or candidate.score > current.score:
            best[key] = candidate
    return sorted(best.values(), key=lambda item: item.score, reverse=True)[:limit]


def _aggregate_risk(candidates: list[Candidate]) -> tuple[str, float]:
    if not candidates:
        return "Low", 0.0
    top = max(candidate.score for candidate in candidates)
    ocr_hits = sum(candidate.needs_ocr for candidate in candidates)
    score = min(1.0, top + min(0.12, ocr_hits * 0.015))
    if score >= 0.9:
        return "Critical", round(score, 4)
    if score >= 0.75:
        return "High", round(score, 4)
    if score >= 0.55:
        return "Medium", round(score, 4)
    return "Low", round(score, 4)


def _candidate_summary(candidates: list[Candidate]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    for candidate in candidates:
        by_kind[candidate.kind] = by_kind.get(candidate.kind, 0) + 1
    return {
        "by_kind": by_kind,
        "max_score": max((candidate.score for candidate in candidates), default=0.0),
        "control_intent_candidates": sum(bool(candidate.control_snippets) for candidate in candidates),
        "ocr_candidates": sum(candidate.needs_ocr for candidate in candidates),
    }


def _rgb_from_int(value: int) -> list[int]:
    return [(value >> 16) & 255, (value >> 8) & 255, value & 255]


def _span_alpha(span: dict[str, Any]) -> int | None:
    value = span.get("alpha")
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _bbox_intersects_page(bbox: Any, page_rect: fitz.Rect) -> bool:
    try:
        rect = fitz.Rect(*bbox)
    except Exception:
        return True
    return not (rect & page_rect).is_empty


def _bbox_union(bboxes: list[Any]) -> list[float] | None:
    rect: fitz.Rect | None = None
    for bbox in bboxes:
        if not bbox:
            continue
        try:
            item = fitz.Rect(*bbox)
        except Exception:
            continue
        rect = item if rect is None else rect | item
    if rect is None:
        return None
    return [round(rect.x0, 3), round(rect.y0, 3), round(rect.x1, 3), round(rect.y1, 3)]


def _compact_pdf_stream_text(stream_text: str) -> str:
    # Pull literal-string fragments out of common PDF text arrays. This is not a
    # full PDF parser; it is a cheap signal for ASCII prompt injections.
    fragments = re.findall(r"\(([^()]*)\)", stream_text)
    if fragments:
        stream_text = " ".join(fragment.replace(r"\(", "(").replace(r"\)", ")") for fragment in fragments)
    return re.sub(r"\s+", " ", stream_text).strip()


def _trim(text: str, limit: int = 700) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _csv_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()
