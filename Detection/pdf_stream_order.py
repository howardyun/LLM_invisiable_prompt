#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detect likely PDF stream-order manipulation attacks.

Goal
----
Find lines where:
1) visual order reconstructed from PDF word bboxes matches OCR,
2) but the PDF extraction / stream-ish order differs significantly.

Dependencies
------------
pip install pymupdf pillow surya-ocr

Notes
-----
- This script uses PyMuPDF word extraction as a practical proxy for "stream-ish"
  order by keeping the original order returned from page.get_text("words", sort=False).
  For many attack PoCs this is enough to surface suspicious local re-orderings.
- Surya APIs can vary slightly by version. The helper functions below try to be
  tolerant, but you may still need to adapt one small parsing function for your
  local Surya version.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import fitz  # PyMuPDF
from PIL import Image, ImageDraw


# -----------------------------
# Basic data structures
# -----------------------------

@dataclass
class Word:
    page_num: int
    stream_idx: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    block_no: int
    line_no: int
    word_no: int

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2.0

    @property
    def h(self) -> float:
        return max(1e-6, self.y1 - self.y0)

    @property
    def w(self) -> float:
        return max(1e-6, self.x1 - self.x0)


@dataclass
class LineRecord:
    page_num: int
    line_id: int
    bbox_pdf: Tuple[float, float, float, float]
    bbox_img: Tuple[float, float, float, float]
    words_visual: List[Word]
    visual_text: str
    stream_text: str
    stream_indices_in_visual_order: List[int]
    inversion_ratio: float
    mean_displacement: float
    max_displacement: int
    backtrack_count: int
    backtrack_max: float
    token_bag_similarity: float
    ocr_text: str = ""
    ocr_bbox_img: Optional[Tuple[float, float, float, float]] = None
    sim_visual_ocr: float = 0.0
    sim_stream_ocr: float = 0.0
    flagged: bool = False
    reason: str = ""


# -----------------------------
# Normalization & similarity
# -----------------------------

TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def normalize_text(s: str) -> str:
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_token(token: str) -> str:
    token = normalize_text(token)
    token = token.lower()
    return token


def smart_join(tokens: Sequence[str]) -> str:
    """Simple English-ish join, good enough for a detector prototype."""
    out: List[str] = []
    no_space_before = set(",.;:!?%)]}\u2019\u201d")
    no_space_after = set("([{\u2018\u201c")

    for tok in tokens:
        tok = normalize_text(tok)
        if not tok:
            continue
        if not out:
            out.append(tok)
            continue
        prev = out[-1]
        if tok[:1] in no_space_before or prev[-1:] in no_space_after:
            out[-1] = prev + tok
        else:
            out.append(" " + tok)
    return "".join(out).strip()


def str_sim(a: str, b: str) -> float:
    a = normalize_text(a)
    b = normalize_text(b)
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def token_bag_sim(a: str, b: str) -> float:
    ta = [normalize_token(t) for t in TOKEN_RE.findall(a) if normalize_token(t)]
    tb = [normalize_token(t) for t in TOKEN_RE.findall(b) if normalize_token(t)]
    if not ta and not tb:
        return 1.0
    ca, cb = Counter(ta), Counter(tb)
    inter = sum((ca & cb).values())
    total = sum(ca.values()) + sum(cb.values())
    if total == 0:
        return 1.0
    return 2.0 * inter / total


# -----------------------------
# Geometry helpers
# -----------------------------


def union_bbox(words: Sequence[Word]) -> Tuple[float, float, float, float]:
    return (
        min(w.x0 for w in words),
        min(w.y0 for w in words),
        max(w.x1 for w in words),
        max(w.y1 for w in words),
    )



def scale_bbox(b: Tuple[float, float, float, float], scale: float) -> Tuple[float, float, float, float]:
    x0, y0, x1, y1 = b
    return (x0 * scale, y0 * scale, x1 * scale, y1 * scale)



def bbox_iou(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    iw = max(0.0, ix1 - ix0)
    ih = max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


# -----------------------------
# PDF extraction with fitz
# -----------------------------


def extract_words(page: fitz.Page, page_num: int) -> List[Word]:
    """
    Keep the original order returned by get_text('words', sort=False) as stream-ish order.
    """
    raw = page.get_text("words", sort=False)
    words: List[Word] = []
    for idx, item in enumerate(raw):
        x0, y0, x1, y1, text, block_no, line_no, word_no = item
        text = normalize_text(str(text))
        if not text:
            continue
        words.append(
            Word(
                page_num=page_num,
                stream_idx=idx,
                x0=float(x0),
                y0=float(y0),
                x1=float(x1),
                y1=float(y1),
                text=text,
                block_no=int(block_no),
                line_no=int(line_no),
                word_no=int(word_no),
            )
        )
    return words


# -----------------------------
# Visual line reconstruction
# -----------------------------


def cluster_visual_lines(words: Sequence[Word], y_tol_ratio: float = 0.45) -> List[List[Word]]:
    """
    Simple visual line grouping by vertical proximity, then sort each line by x.
    This is intentionally simple for a detector prototype.
    """
    if not words:
        return []

    by_y = sorted(words, key=lambda w: (w.cy, w.x0))
    lines: List[List[Word]] = []

    for w in by_y:
        placed = False
        for line in lines:
            median_h = sorted(x.h for x in line)[len(line) // 2]
            cy_mean = sum(x.cy for x in line) / len(line)
            y_tol = max(2.0, median_h * y_tol_ratio)
            if abs(w.cy - cy_mean) <= y_tol:
                line.append(w)
                placed = True
                break
        if not placed:
            lines.append([w])

    for line in lines:
        line.sort(key=lambda w: (w.x0, w.y0, w.stream_idx))

    # final sort top-to-bottom, then left-to-right by line bbox
    lines.sort(key=lambda line: (min(w.y0 for w in line), min(w.x0 for w in line)))
    return lines


# -----------------------------
# Order anomaly features
# -----------------------------


def inversion_ratio(seq: Sequence[int]) -> float:
    n = len(seq)
    if n < 2:
        return 0.0
    inv = 0
    total = n * (n - 1) // 2
    for i in range(n):
        si = seq[i]
        for j in range(i + 1, n):
            if si > seq[j]:
                inv += 1
    return inv / total if total else 0.0



def displacement_stats(words_visual: Sequence[Word]) -> Tuple[float, int]:
    if not words_visual:
        return 0.0, 0
    stream_sorted = sorted(words_visual, key=lambda w: w.stream_idx)
    visual_rank = {id(w): i for i, w in enumerate(words_visual)}
    stream_rank = {id(w): i for i, w in enumerate(stream_sorted)}
    disps = [abs(visual_rank[id(w)] - stream_rank[id(w)]) for w in words_visual]
    return (sum(disps) / len(disps), max(disps) if disps else 0)



def backtrack_stats(words_visual: Sequence[Word]) -> Tuple[int, float]:
    if len(words_visual) < 2:
        return 0, 0.0
    stream_sorted = sorted(words_visual, key=lambda w: w.stream_idx)
    count = 0
    max_back = 0.0
    prev_x = stream_sorted[0].cx
    for w in stream_sorted[1:]:
        if w.cx + 1.0 < prev_x:
            count += 1
            max_back = max(max_back, prev_x - w.cx)
        prev_x = w.cx
    return count, max_back


# -----------------------------
# Surya OCR helpers
# -----------------------------


def page_to_pil(page: fitz.Page, dpi: int) -> Image.Image:
    scale = dpi / 72.0
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    mode = "RGB" if pix.n < 4 else "RGBA"
    return Image.frombytes(mode, [pix.width, pix.height], pix.samples)



def _obj_to_dict(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _obj_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_obj_to_dict(x) for x in obj]
    if hasattr(obj, "model_dump"):
        try:
            return _obj_to_dict(obj.model_dump())
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            return _obj_to_dict(obj.dict())
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return {k: _obj_to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
        except Exception:
            pass
    return obj



def _extract_bbox_text_entries(node: Any, out: List[Dict[str, Any]]) -> None:
    """
    Tries to find line-like OCR items in Surya outputs with fields similar to:
    {'text': ..., 'bbox': [x0,y0,x1,y1]}
    """
    node = _obj_to_dict(node)
    if isinstance(node, dict):
        has_text = isinstance(node.get("text"), str)
        bbox = node.get("bbox")
        if has_text and isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            out.append({"text": normalize_text(node["text"]), "bbox": tuple(float(v) for v in bbox)})
        for v in node.values():
            _extract_bbox_text_entries(v, out)
    elif isinstance(node, list):
        for item in node:
            _extract_bbox_text_entries(item, out)



def run_surya_ocr(images: Sequence[Image.Image]) -> List[List[Dict[str, Any]]]:
    """
    Returns one list of OCR lines per page image.
    Each OCR line is {'text': str, 'bbox': (x0,y0,x1,y1)} in image coordinates.
    """
    try:
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor
    except ImportError as exc:
        raise RuntimeError(
            "Surya import failed. Install it first, e.g. `pip install surya-ocr`."
        ) from exc

    foundation = FoundationPredictor()
    rec = RecognitionPredictor(foundation)
    det = DetectionPredictor()

    preds = rec(list(images), det_predictor=det)
    all_pages: List[List[Dict[str, Any]]] = []
    for pred in preds:
        entries: List[Dict[str, Any]] = []
        _extract_bbox_text_entries(pred, entries)

        # Deduplicate exact same bbox+text entries that may appear through nested structures.
        uniq = []
        seen = set()
        for e in entries:
            key = (e["text"], tuple(round(v, 3) for v in e["bbox"]))
            if key in seen:
                continue
            seen.add(key)
            uniq.append(e)

        # Heuristic: keep medium-length entries and sort by y/x.
        uniq = [e for e in uniq if e["text"]]
        uniq.sort(key=lambda e: (e["bbox"][1], e["bbox"][0]))
        all_pages.append(uniq)

    return all_pages


# -----------------------------
# OCR ↔ PDF line matching
# -----------------------------


def best_ocr_match(line_bbox_img: Tuple[float, float, float, float], ocr_lines: Sequence[Dict[str, Any]]) -> Tuple[str, Optional[Tuple[float, float, float, float]], float]:
    best_text = ""
    best_bbox = None
    best_score = 0.0
    for o in ocr_lines:
        b = tuple(o["bbox"])
        score = bbox_iou(line_bbox_img, b)
        if score > best_score:
            best_score = score
            best_text = normalize_text(o["text"])
            best_bbox = b
    return best_text, best_bbox, best_score


# -----------------------------
# Core detector
# -----------------------------


def build_line_records(words: Sequence[Word], page_num: int, scale: float, ocr_lines: Sequence[Dict[str, Any]],
                       vis_ocr_sim_min: float, stream_ocr_sim_max: float,
                       inv_ratio_min: float, disp_min: float, iou_min: float) -> List[LineRecord]:
    lines = cluster_visual_lines(words)
    records: List[LineRecord] = []

    for line_id, line_words in enumerate(lines):
        if not line_words:
            continue
        visual_words = sorted(line_words, key=lambda w: (w.x0, w.y0, w.stream_idx))
        stream_words = sorted(line_words, key=lambda w: w.stream_idx)

        visual_text = smart_join([w.text for w in visual_words])
        stream_text = smart_join([w.text for w in stream_words])
        stream_idx_seq = [w.stream_idx for w in visual_words]

        inv = inversion_ratio(stream_idx_seq)
        mean_disp, max_disp = displacement_stats(visual_words)
        bt_count, bt_max = backtrack_stats(visual_words)
        bag_sim = token_bag_sim(visual_text, stream_text)

        bbox_pdf = union_bbox(visual_words)
        bbox_img = scale_bbox(bbox_pdf, scale)
        ocr_text, ocr_bbox, ocr_iou = best_ocr_match(bbox_img, ocr_lines)
        sim_vo = str_sim(visual_text, ocr_text) if ocr_iou >= iou_min else 0.0
        sim_so = str_sim(stream_text, ocr_text) if ocr_iou >= iou_min else 0.0

        flagged = False
        reason_parts = []
        if ocr_iou >= iou_min and sim_vo >= vis_ocr_sim_min and sim_so <= stream_ocr_sim_max:
            flagged = True
            reason_parts.append("visual≈ocr but stream≠ocr")
        if inv >= inv_ratio_min:
            flagged = True
            reason_parts.append(f"high inversion_ratio={inv:.3f}")
        if mean_disp >= disp_min:
            flagged = True
            reason_parts.append(f"high mean_displacement={mean_disp:.2f}")
        if bt_count > 0:
            reason_parts.append(f"backtracks={bt_count}")

        records.append(
            LineRecord(
                page_num=page_num,
                line_id=line_id,
                bbox_pdf=bbox_pdf,
                bbox_img=bbox_img,
                words_visual=visual_words,
                visual_text=visual_text,
                stream_text=stream_text,
                stream_indices_in_visual_order=stream_idx_seq,
                inversion_ratio=inv,
                mean_displacement=mean_disp,
                max_displacement=max_disp,
                backtrack_count=bt_count,
                backtrack_max=bt_max,
                token_bag_similarity=bag_sim,
                ocr_text=ocr_text,
                ocr_bbox_img=ocr_bbox,
                sim_visual_ocr=sim_vo,
                sim_stream_ocr=sim_so,
                flagged=flagged,
                reason="; ".join(reason_parts),
            )
        )

    return records


# -----------------------------
# Visualization
# -----------------------------


def draw_flags(image: Image.Image, line_records: Sequence[LineRecord], out_path: Path) -> None:
    draw = ImageDraw.Draw(image)
    for rec in line_records:
        if not rec.flagged:
            continue
        x0, y0, x1, y1 = rec.bbox_img
        draw.rectangle([x0, y0, x1, y1], outline=(255, 0, 0), width=3)
    image.save(out_path)


# -----------------------------
# Main
# -----------------------------


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Detect likely PDF stream-order manipulation using fitz + Surya OCR.")
    ap.add_argument("pdf", help="Input PDF path")
    ap.add_argument("--out-dir", default="stream_order_detect_out", help="Output directory")
    ap.add_argument("--dpi", type=int, default=200, help="Render DPI for OCR")
    ap.add_argument("--max-pages", type=int, default=0, help="Maximum number of pages to process; 0 means all")
    ap.add_argument("--vis-ocr-sim-min", type=float, default=0.78)
    ap.add_argument("--stream-ocr-sim-max", type=float, default=0.58)
    ap.add_argument("--inv-ratio-min", type=float, default=0.12)
    ap.add_argument("--disp-min", type=float, default=1.0)
    ap.add_argument("--iou-min", type=float, default=0.15, help="Min line IoU to accept OCR line matching")
    return ap.parse_args()



def main() -> None:
    args = parse_args()
    pdf_path = Path(args.pdf)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    scale = args.dpi / 72.0

    pages = list(range(len(doc)))
    if args.max_pages and args.max_pages > 0:
        pages = pages[: args.max_pages]

    # 1) Render pages for OCR
    pil_pages: List[Image.Image] = [page_to_pil(doc[p], dpi=args.dpi) for p in pages]

    # 2) OCR all pages with Surya
    ocr_results = run_surya_ocr(pil_pages)

    all_output: Dict[str, Any] = {
        "pdf": str(pdf_path),
        "dpi": args.dpi,
        "pages": [],
    }

    for local_idx, page_idx in enumerate(pages):
        page = doc[page_idx]
        words = extract_words(page, page_num=page_idx + 1)
        page_records = build_line_records(
            words=words,
            page_num=page_idx + 1,
            scale=scale,
            ocr_lines=ocr_results[local_idx],
            vis_ocr_sim_min=args.vis_ocr_sim_min,
            stream_ocr_sim_max=args.stream_ocr_sim_max,
            inv_ratio_min=args.inv_ratio_min,
            disp_min=args.disp_min,
            iou_min=args.iou_min,
        )

        page_json = {
            "page_num": page_idx + 1,
            "flagged_count": sum(1 for r in page_records if r.flagged),
            "lines": [
                {
                    **{k: v for k, v in asdict(r).items() if k != "words_visual"},
                    "words_visual": [
                        {
                            "text": w.text,
                            "stream_idx": w.stream_idx,
                            "bbox_pdf": [w.x0, w.y0, w.x1, w.y1],
                        }
                        for w in r.words_visual
                    ],
                }
                for r in page_records
            ],
        }
        all_output["pages"].append(page_json)

        img_out = out_dir / f"page_{page_idx + 1:04d}_flags.png"
        draw_flags(pil_pages[local_idx].copy(), page_records, img_out)

        print(f"[Page {page_idx + 1}] flagged lines: {page_json['flagged_count']}")
        for rec in page_records:
            if rec.flagged:
                print(f"  - line {rec.line_id}: {rec.reason}")
                print(f"    visual: {rec.visual_text}")
                print(f"    stream: {rec.stream_text}")
                print(f"    ocr   : {rec.ocr_text}")

    json_path = out_dir / "results.json"
    json_path.write_text(json.dumps(all_output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved results to: {json_path}")


if __name__ == "__main__":
    main()
