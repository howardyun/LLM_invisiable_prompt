"""PyMuPDF text-layer extraction and gap localization."""

from __future__ import annotations

from pathlib import Path

import fitz
from rapidfuzz import fuzz

from detector_config import MIN_ORPHAN_TEXT_CHARS, ORPHAN_COVERAGE_THRESHOLD
from detector_geometry import best_region_match, bbox_union, cumulative_region_coverage
from detector_models import LayoutRegion
from detector_text import normalize_text, tokenize_for_gap


def extract_pymupdf_region_text(pdf_path: Path, regions: list[LayoutRegion]) -> None:
    """Fill each Docling region with PyMuPDF text clipped to that bbox."""

    with fitz.open(pdf_path) as pdf:
        for region in regions:
            if region.page_no < 1 or region.page_no > len(pdf):
                continue
            page = pdf[region.page_no - 1]
            clip = fitz.Rect(*region.bbox) & page.rect
            if clip.is_empty or clip.is_infinite:
                continue
            region.pymupdf_text = page.get_text("text", clip=clip, sort=True).strip()


def collect_pymupdf_structures(
    pdf_path: Path,
    docling_regions: list[LayoutRegion],
    max_pages: int | None,
) -> tuple[list[dict], list[dict]]:
    """Collect PyMuPDF blocks and words for debugging and gap localization."""

    blocks: list[dict] = []
    words: list[dict] = []
    with fitz.open(pdf_path) as pdf:
        page_count = min(len(pdf), max_pages) if max_pages else len(pdf)
        for page_index in range(page_count):
            page_no = page_index + 1
            page = pdf[page_index]

            for raw_block in page.get_text("blocks", sort=True):
                if len(raw_block) < 5:
                    continue
                x0, y0, x1, y1, block_text = raw_block[:5]
                block_no = raw_block[5] if len(raw_block) > 5 else None
                block_type = raw_block[6] if len(raw_block) > 6 else None
                bbox = [round(float(x0), 3), round(float(y0), 3), round(float(x1), 3), round(float(y1), 3)]
                best = best_region_match(bbox, docling_regions, page_no)
                blocks.append(
                    {
                        "page_no": page_no,
                        "block_no": int(block_no) if isinstance(block_no, (int, float)) else block_no,
                        "block_type": int(block_type) if isinstance(block_type, (int, float)) else block_type,
                        "bbox": bbox,
                        "text": str(block_text or "").strip(),
                        "best_docling_region_id": best["region_id"],
                        "best_docling_label": best["label"],
                        "coverage_by_best_docling_region": best["coverage"],
                        "coverage_by_all_docling_regions": round(
                            cumulative_region_coverage(bbox, docling_regions, page_no),
                            4,
                        ),
                    }
                )

            for raw_word in page.get_text("words", sort=True):
                if len(raw_word) < 5:
                    continue
                x0, y0, x1, y1, word_text = raw_word[:5]
                block_no = raw_word[5] if len(raw_word) > 5 else None
                line_no = raw_word[6] if len(raw_word) > 6 else None
                word_no = raw_word[7] if len(raw_word) > 7 else None
                bbox = [round(float(x0), 3), round(float(y0), 3), round(float(x1), 3), round(float(y1), 3)]
                best = best_region_match(bbox, docling_regions, page_no)
                words.append(
                    {
                        "page_no": page_no,
                        "block_no": int(block_no) if isinstance(block_no, (int, float)) else block_no,
                        "line_no": int(line_no) if isinstance(line_no, (int, float)) else line_no,
                        "word_no": int(word_no) if isinstance(word_no, (int, float)) else word_no,
                        "bbox": bbox,
                        "text": str(word_text or ""),
                        "norm": normalize_text(str(word_text or "")),
                        "best_docling_region_id": best["region_id"],
                        "best_docling_label": best["label"],
                        "coverage_by_best_docling_region": best["coverage"],
                    }
                )

    return blocks, words


def add_pymupdf_only_regions(
    pdf_path: Path,
    regions: list[LayoutRegion],
    max_pages: int | None,
) -> int:
    """Add outside-layout PyMuPDF-only blocks.

    Important: this uses coverage by the *union* of Docling regions, not just
    the best single region. This avoids treating a large PyMuPDF block spanning
    many list_items as hidden text.
    """

    order = max((region.order for region in regions), default=0)
    added = 0
    docling_regions = [region for region in regions if region.source == "docling_region"]

    with fitz.open(pdf_path) as pdf:
        page_count = min(len(pdf), max_pages) if max_pages else len(pdf)
        for page_index in range(page_count):
            page_no = page_index + 1
            page = pdf[page_index]
            for block in page.get_text("blocks", sort=True):
                if len(block) < 5:
                    continue
                x0, y0, x1, y1, block_text = block[:5]
                block_no = block[5] if len(block) > 5 else None
                block_type = block[6] if len(block) > 6 else 0
                if block_type != 0:
                    continue
                block_text = str(block_text or "").strip()
                if len(normalize_text(block_text)) < MIN_ORPHAN_TEXT_CHARS:
                    continue

                clip = fitz.Rect(float(x0), float(y0), float(x1), float(y1)) & page.rect
                if clip.is_empty or clip.is_infinite:
                    continue
                bbox = [round(clip.x0, 3), round(clip.y0, 3), round(clip.x1, 3), round(clip.y1, 3)]
                all_coverage = cumulative_region_coverage(bbox, docling_regions, page_no)
                if all_coverage >= ORPHAN_COVERAGE_THRESHOLD:
                    continue

                best = best_region_match(bbox, docling_regions, page_no)
                order += 1
                added += 1
                regions.append(
                    LayoutRegion(
                        region_id=f"r{order:05d}",
                        order=order,
                        source="pymupdf_only",
                        label="pymupdf_only",
                        page_no=page_no,
                        bbox=bbox,
                        coord_origin="TOPLEFT",
                        pymupdf_text=block_text,
                        extra={
                            "coverage_by_all_docling_regions": round(all_coverage, 4),
                            "best_docling_region_id": best["region_id"],
                            "coverage_by_best_docling_region": best["coverage"],
                            "pymupdf_block_no": int(block_no) if isinstance(block_no, (int, float)) else block_no,
                        },
                    )
                )
    return added


def _words_inside_region(words: list[dict], region: LayoutRegion) -> list[dict]:
    """Return page words whose centers fall inside a region bbox."""

    x0, y0, x1, y1 = region.bbox
    inside = []
    for word in words:
        if word.get("page_no") != region.page_no:
            continue
        wx0, wy0, wx1, wy1 = word["bbox"]
        cx = (wx0 + wx1) / 2.0
        cy = (wy0 + wy1) / 2.0
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            inside.append(word)
    return sorted(inside, key=lambda w: (w.get("block_no", 0), w.get("line_no", 0), w.get("word_no", 0)))


def _page_words(words: list[dict], page_no: int) -> list[dict]:
    """Return all PyMuPDF words from one page in reading order."""

    return sorted(
        [word for word in words if word.get("page_no") == page_no],
        key=lambda w: (w.get("block_no", 0), w.get("line_no", 0), w.get("word_no", 0)),
    )


def _locate_gap_in_words(words: list[dict], gap_text: str) -> dict | None:
    """Find a gap span inside an already selected PyMuPDF word list."""

    gap_tokens = [token["norm"] for token in tokenize_for_gap(gap_text)]
    if not words or not gap_tokens:
        return None

    word_tokens = [word["norm"] for word in words]

    # Prefer exact contiguous token match.
    for start in range(0, len(word_tokens) - len(gap_tokens) + 1):
        if word_tokens[start : start + len(gap_tokens)] == gap_tokens:
            matched = words[start : start + len(gap_tokens)]
            return {
                "bbox": bbox_union([word["bbox"] for word in matched]),
                "matched_words": matched,
                "match_strategy": "exact_word_sequence",
            }

    # Fallback: fuzzy best window around the expected length.
    best_score = 0.0
    best_window: list[dict] = []
    expected = len(gap_tokens)
    for size in range(max(1, expected - 2), min(len(words), expected + 3) + 1):
        for start in range(0, len(words) - size + 1):
            window = words[start : start + size]
            window_text = " ".join(word["text"] for word in window)
            score = fuzz.token_set_ratio(normalize_text(gap_text), normalize_text(window_text)) / 100.0
            if score > best_score:
                best_score = score
                best_window = window

    if best_score >= 0.65 and best_window:
        return {
            "bbox": bbox_union([word["bbox"] for word in best_window]),
            "matched_words": best_window,
            "match_strategy": "fuzzy_word_window",
            "word_window_similarity": round(best_score, 4),
        }

    return None


def locate_gap_bbox_from_words(
    all_words: list[dict],
    region: LayoutRegion,
    gap_text: str,
) -> dict:
    """Locate a missing gap's bbox using PyMuPDF word positions.

    First try the parent Docling region because it is usually the right local
    context. If layout boundaries caused the text to be absorbed into a nearby
    block, fall back to all words on the same PDF page. This is the second-pass
    verification anchor: it uses the parser's own word coordinates instead of
    trusting Docling's crop.
    """

    located = _locate_gap_in_words(_words_inside_region(all_words, region), gap_text)
    if located and located.get("bbox"):
        located["search_scope"] = "parent_region_words"
        return located

    located = _locate_gap_in_words(_page_words(all_words, region.page_no), gap_text)
    if located and located.get("bbox"):
        located["search_scope"] = "full_page_words"
        return located

    return {
        "bbox": region.bbox,
        "matched_words": [],
        "match_strategy": "fallback_region_bbox",
        "search_scope": "fallback_region_bbox",
    }
