from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from itertools import combinations
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image
from rapidfuzz import fuzz

# ------------------------------------------------------------
# Surya lazy loading
# ------------------------------------------------------------
_SURYA_PREDICTORS: Optional[Tuple[object, object]] = None


def get_surya_predictors() -> Tuple[object, object]:
    global _SURYA_PREDICTORS
    if _SURYA_PREDICTORS is None:
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor

        foundation_predictor = FoundationPredictor()
        recognition_predictor = RecognitionPredictor(foundation_predictor)
        detection_predictor = DetectionPredictor()
        _SURYA_PREDICTORS = (recognition_predictor, detection_predictor)
    return _SURYA_PREDICTORS


# ------------------------------------------------------------
# Text / bbox helpers
# ------------------------------------------------------------
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
MULTISPACE_PATTERN = re.compile(r"\s+")
LATEX_CMD_RE = re.compile(r"\\[A-Za-z]+")
LATIN_WORD_RE = re.compile(r"[A-Za-z]{3,}")
COMMON_CHAR_REPLACEMENTS = {
    "\u00ad": "",
    "\xa0": " ",
    "\u200b": "",
    "\u200c": "",
    "\u200d": "",
    "\ufeff": "",
}
LATEX_REPLACEMENTS = {
    r"\alpha": "α",
    r"\beta": "β",
    r"\gamma": "γ",
    r"\delta": "δ",
    r"\epsilon": "ϵ",
    r"\varepsilon": "ϵ",
    r"\lambda": "λ",
    r"\mu": "μ",
    r"\nu": "ν",
    r"\pi": "π",
    r"\sigma": "σ",
    r"\Sigma": "Σ",
    r"\tau": "τ",
    r"\theta": "θ",
    r"\omega": "ω",
    r"\Omega": "Ω",
    r"\rho": "ρ",
    r"\phi": "φ",
    r"\psi": "ψ",
    r"\in": "∈",
    r"\notin": "∉",
    r"\subset": "⊂",
    r"\subseteq": "⊆",
    r"\supset": "⊃",
    r"\supseteq": "⊇",
    r"\cup": "∪",
    r"\cap": "∩",
    r"\sum": "∑",
    r"\prod": "∏",
    r"\int": "∫",
    r"\max": "max",
    r"\min": "min",
    r"\argmax": "argmax",
    r"\argmin": "argmin",
    r"\mathbb{E}": "E",
    r"\mathcal{A}": "A",
    r"\mathcal{S}": "S",
    r"\left": "",
    r"\right": "",
    r"\mid": "|",
    r"\vert": "|",
    r"\Vert": "||",
    r"\cdot": "·",
    r"\times": "×",
    r"\leq": "≤",
    r"\geq": "≥",
    r"\neq": "≠",
    r"\to": "→",
    r"\rightarrow": "→",
    r"\leftarrow": "←",
    r"\sim": "∼",
    r"\ldots": "…",
    r"\cdots": "⋯",
    r"\mathbf": "",
    r"\mathrm": "",
    r"\operatorname": "",
    r"\text": "",
    r"\underset": "",
    r"\overset": "",
}
MATH_SYMBOL_CHARS = set("=+-*/^_<>≤≥≠∈∉∑∏∫∞∂∀∃→←↔≈≜⊂⊆⊃⊇∪∩|()[]{}·×⋯…αβγδεϵζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ'\"")
PROSE_STOPWORDS = {
    "max", "min", "argmax", "argmin", "proof", "lemma", "theorem", "corollary",
    "sigma", "alpha", "beta", "gamma", "delta", "left", "right", "mathbb", "mathcal",
}


def normalize_bbox(bbox: Any) -> Optional[List[float]]:
    if bbox is None:
        return None
    if hasattr(bbox, "bbox"):
        nested = getattr(bbox, "bbox")
        if nested is not bbox:
            return normalize_bbox(nested)
    if isinstance(bbox, dict):
        keys = {str(k).lower(): v for k, v in bbox.items()}
        if {"x1", "y1", "x2", "y2"}.issubset(keys):
            return [float(keys["x1"]), float(keys["y1"]), float(keys["x2"]), float(keys["y2"])]
    if all(hasattr(bbox, attr) for attr in ("x1", "y1", "x2", "y2")):
        return [float(getattr(bbox, "x1")), float(getattr(bbox, "y1")), float(getattr(bbox, "x2")), float(getattr(bbox, "y2"))]
    if isinstance(bbox, (list, tuple)):
        if len(bbox) == 4 and all(isinstance(v, (int, float)) for v in bbox):
            return [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
        if len(bbox) >= 4 and all(isinstance(pt, (list, tuple)) and len(pt) >= 2 for pt in bbox):
            xs = [float(pt[0]) for pt in bbox]
            ys = [float(pt[1]) for pt in bbox]
            return [min(xs), min(ys), max(xs), max(ys)]
    return None


def normalize_latexish_text(text: str) -> str:
    if not text or "\\" not in text:
        return text
    out = text
    for src, tgt in LATEX_REPLACEMENTS.items():
        out = out.replace(src, tgt)
    out = re.sub(r"\\mathbb\{([^{}]+)\}", r"\1", out)
    out = re.sub(r"\\mathcal\{([^{}]+)\}", r"\1", out)
    out = re.sub(r"\\mathbf\{([^{}]+)\}", r"\1", out)
    out = re.sub(r"\\mathrm\{([^{}]+)\}", r"\1", out)
    out = re.sub(r"\\operatorname\{([^{}]+)\}", r"\1", out)
    out = re.sub(r"\\text\{([^{}]+)\}", r"\1", out)
    out = re.sub(r"_\{([^{}]+)\}", r" \1 ", out)
    out = re.sub(r"\^\{([^{}]+)\}", r" \1 ", out)
    out = re.sub(r"_([A-Za-z0-9α-ωΑ-Ω])", r" \1 ", out)
    out = re.sub(r"\^([A-Za-z0-9α-ωΑ-Ω])", r" \1 ", out)
    out = out.replace("{", " ").replace("}", " ")
    out = out.replace("[", " [ ").replace("]", " ] ")
    out = out.replace("(", " ( ").replace(")", " ) ")
    out = LATEX_CMD_RE.sub(" ", out)
    return out


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = normalize_latexish_text(text)
    for src, tgt in COMMON_CHAR_REPLACEMENTS.items():
        text = text.replace(src, tgt)
    text = CONTROL_CHAR_PATTERN.sub("", text)
    text = unicodedata.normalize("NFKC", text)

    dash_chars = {"−", "–", "—", "‐", "-"}
    prime_chars = {"′", "’", "`", "´"}
    star_chars = {"∗", "⋆", "✶"}
    for ch in dash_chars:
        text = text.replace(ch, "-")
    for ch in prime_chars:
        text = text.replace(ch, "'")
    for ch in star_chars:
        text = text.replace(ch, "*")

    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s*:=\s*", " := ", text)
    text = re.sub(r"\s*=\s*", " = ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*;\s*", "; ", text)
    text = re.sub(r"\s+([.?!])", r"\1", text)
    text = MULTISPACE_PATTERN.sub(" ", text).strip()
    return text


def count_prose_words(text: str) -> int:
    words = [w.lower() for w in LATIN_WORD_RE.findall(clean_text(text))]
    return sum(1 for w in words if w not in PROSE_STOPWORDS)


def math_signal_score(text: str) -> Dict[str, float]:
    t = clean_text(text)
    if not t:
        return {
            "latex_cmds": 0.0,
            "math_char_ratio": 0.0,
            "math_keyword_hits": 0.0,
            "prose_words": 0.0,
            "display_formula_score": 0.0,
        }
    raw = text or ""
    latex_cmds = float(len(LATEX_CMD_RE.findall(raw)))
    math_char_count = sum(1 for ch in t if ch in MATH_SYMBOL_CHARS)
    math_char_ratio = math_char_count / max(len(t), 1)
    keyword_hits = 0.0
    lower = t.lower()
    for kw in ["max", "min", "argmax", "argmin", " := ", " = ", " ∑ ", " ∫ ", " ∈ ", "→", "∀", "∃"]:
        if kw.strip() in lower:
            keyword_hits += 1.0
    prose_words = float(count_prose_words(t))
    display_formula_score = 1.6 * min(latex_cmds, 4.0) + 5.0 * math_char_ratio + 0.7 * keyword_hits - 0.45 * prose_words
    return {
        "latex_cmds": latex_cmds,
        "math_char_ratio": math_char_ratio,
        "math_keyword_hits": keyword_hits,
        "prose_words": prose_words,
        "display_formula_score": display_formula_score,
    }


def is_display_formula_like(pdf_text: str, ocr_text: str) -> bool:
    pdf_sig = math_signal_score(pdf_text)
    ocr_sig = math_signal_score(ocr_text)
    prose_words = max(pdf_sig["prose_words"], ocr_sig["prose_words"])
    max_score = max(pdf_sig["display_formula_score"], ocr_sig["display_formula_score"])
    strong_latex = ocr_sig["latex_cmds"] >= 2.0
    strong_math_ratio = max(pdf_sig["math_char_ratio"], ocr_sig["math_char_ratio"]) >= 0.22
    return (max_score >= 3.2 and prose_words <= 2.0) or (strong_latex and strong_math_ratio and prose_words <= 3.0)


def is_formula_fragment_text(text: str) -> bool:
    sig = math_signal_score(text)
    return bool(clean_text(text)) and sig["display_formula_score"] >= 2.2 and sig["prose_words"] <= 1.0


def text_consistency_metrics(a: str, b: str) -> Dict[str, float]:
    a = clean_text(a)
    b = clean_text(b)
    if not a and not b:
        return {
            "ratio": 1.0,
            "partial_ratio": 1.0,
            "token_sort_ratio": 1.0,
            "length_gap": 0.0,
        }
    if not a or not b:
        return {
            "ratio": 0.0,
            "partial_ratio": 0.0,
            "token_sort_ratio": 0.0,
            "length_gap": 1.0,
        }

    max_len = max(len(a), len(b), 1)
    return {
        "ratio": fuzz.ratio(a, b) / 100.0,
        "partial_ratio": fuzz.partial_ratio(a, b) / 100.0,
        "token_sort_ratio": fuzz.token_sort_ratio(a, b) / 100.0,
        "length_gap": abs(len(a) - len(b)) / max_len,
    }


def is_text_mismatch(pdf_text: str, ocr_text: str) -> Tuple[bool, Dict[str, float], str]:
    metrics = text_consistency_metrics(pdf_text, ocr_text)
    ratio = metrics["ratio"]
    partial = metrics["partial_ratio"]
    token_sort = metrics["token_sort_ratio"]
    length_gap = metrics["length_gap"]

    mismatch = (
        ratio < 0.45
        or (ratio < 0.70 and length_gap > 0.35)
        or (partial < 0.60 and token_sort < 0.60)
    )

    if not mismatch:
        return False, metrics, ""

    if ratio < 0.45:
        reason = "matched_bbox_but_text_ratio_low"
    elif ratio < 0.70 and length_gap > 0.35:
        reason = "matched_bbox_but_text_length_gap_large"
    else:
        reason = "matched_bbox_but_text_partial_and_token_sort_low"
    return True, metrics, reason


def bbox_area(b: List[float]) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def bbox_iou(a: List[float], b: List[float]) -> float:
    inter_x1 = max(a[0], b[0])
    inter_y1 = max(a[1], b[1])
    inter_x2 = min(a[2], b[2])
    inter_y2 = min(a[3], b[3])
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter = inter_w * inter_h
    if inter <= 0:
        return 0.0
    union = bbox_area(a) + bbox_area(b) - inter
    return inter / max(union, 1e-8)


def bbox_intersection_area(a: List[float], b: List[float]) -> float:
    inter_x1 = max(a[0], b[0])
    inter_y1 = max(a[1], b[1])
    inter_x2 = min(a[2], b[2])
    inter_y2 = min(a[3], b[3])
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    return inter_w * inter_h


def bbox_overlap_over_pdf(pdf_bbox: List[float], ocr_bbox: List[float]) -> float:
    inter = bbox_intersection_area(pdf_bbox, ocr_bbox)
    return inter / max(bbox_area(pdf_bbox), 1e-8)


def bbox_overlap_over_ocr(pdf_bbox: List[float], ocr_bbox: List[float]) -> float:
    inter = bbox_intersection_area(pdf_bbox, ocr_bbox)
    return inter / max(bbox_area(ocr_bbox), 1e-8)


def center_distance_score(a: List[float], b: List[float], page_w: float, page_h: float) -> float:
    ax = (a[0] + a[2]) / 2.0
    ay = (a[1] + a[3]) / 2.0
    bx = (b[0] + b[2]) / 2.0
    by = (b[1] + b[3]) / 2.0
    dist = math.hypot(ax - bx, ay - by)
    diag = math.hypot(max(page_w, 1.0), max(page_h, 1.0))
    return max(0.0, 1.0 - dist / max(diag, 1.0))


def bbox_to_compact_str(bbox: Optional[List[float]]) -> str:
    if not bbox:
        return ""
    return ",".join(f"{float(v):.2f}" for v in bbox)


def bbox_union(boxes: List[List[float]]) -> List[float]:
    xs1 = [b[0] for b in boxes]
    ys1 = [b[1] for b in boxes]
    xs2 = [b[2] for b in boxes]
    ys2 = [b[3] for b in boxes]
    return [min(xs1), min(ys1), max(xs2), max(ys2)]


def horizontal_gap(a: List[float], b: List[float]) -> float:
    if a[2] < b[0]:
        return b[0] - a[2]
    if b[2] < a[0]:
        return a[0] - b[2]
    return 0.0


def bbox_center_y(b: List[float]) -> float:
    return (b[1] + b[3]) / 2.0

def sort_regions_in_reading_order(regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not regions:
        return []

    regs = list(regions)
    heights = [max(1.0, bbox_height(r["bbox"])) for r in regs]
    line_tol = max(4.0, 0.8 * median(heights))

    regs.sort(key=lambda r: (bbox_center_y(r["bbox"]), r["bbox"][0]))
    lines: List[List[Dict[str, Any]]] = []
    for reg in regs:
        cy = bbox_center_y(reg["bbox"])
        if not lines:
            lines.append([reg])
            continue

        placed = False
        for line in reversed(lines):
            line_cy = sum(bbox_center_y(x["bbox"]) for x in line) / len(line)
            if abs(cy - line_cy) <= line_tol:
                line.append(reg)
                placed = True
                break

        if not placed:
            lines.append([reg])

    ordered: List[Dict[str, Any]] = []
    lines.sort(key=lambda line: sum(bbox_center_y(x["bbox"]) for x in line) / len(line))
    for line in lines:
        line.sort(key=lambda r: (r["bbox"][0], bbox_center_y(r["bbox"])))
        ordered.extend(line)
    return ordered


def bbox_height(b: List[float]) -> float:
    return max(0.0, b[3] - b[1])


def bbox_width(b: List[float]) -> float:
    return max(0.0, b[2] - b[0])


def point_in_bbox(x: float, y: float, bbox: List[float]) -> bool:
    return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]


def is_region_near_anchor(region_bbox: List[float], anchor_bbox: List[float]) -> bool:
    margin_x = max(14.0, 0.08 * bbox_width(anchor_bbox))
    margin_y = max(10.0, 0.50 * bbox_height(anchor_bbox))
    expanded = [anchor_bbox[0] - margin_x, anchor_bbox[1] - margin_y, anchor_bbox[2] + margin_x, anchor_bbox[3] + margin_y]
    cx = (region_bbox[0] + region_bbox[2]) / 2.0
    cy = (region_bbox[1] + region_bbox[3]) / 2.0
    if point_in_bbox(cx, cy, expanded):
        return True
    inter = bbox_intersection_area(region_bbox, expanded)
    return inter / max(bbox_area(region_bbox), 1e-8) >= 0.25


def can_attach_pdf_fragment_to_formula_match(pdf_region: Dict[str, Any], match_pair: Dict[str, Any]) -> bool:
    """Return True when an unmatched PDF fragment is likely part of an already matched formula block.

    We only attach to matched records that were already treated as display-formula skips.
    The fragment itself must look formula-like and be spatially close to the matched PDF/OCR anchor.
    """
    if match_pair.get("record_type") != "matched":
        return False
    if match_pair.get("compare_status") != "skipped_formula":
        return False

    text = clean_text(pdf_region.get("text", ""))
    if not text:
        return False

    # Only attach small formula-like fragments, not normal prose boxes.
    if not is_formula_fragment_text(text):
        return False

    pdf_anchor = (match_pair.get("pdf_region") or {}).get("bbox")
    ocr_anchor = (match_pair.get("ocr_region") or {}).get("bbox")
    if not pdf_anchor and not ocr_anchor:
        return False

    region_bbox = pdf_region["bbox"]
    near_pdf = is_region_near_anchor(region_bbox, pdf_anchor) if pdf_anchor else False
    near_ocr = is_region_near_anchor(region_bbox, ocr_anchor) if ocr_anchor else False
    if not (near_pdf or near_ocr):
        return False

    # Reject very large prose-like boxes even if they are near the anchor.
    anchor_bbox = pdf_anchor or ocr_anchor
    if anchor_bbox is not None:
        if bbox_area(region_bbox) > 0.70 * max(bbox_area(anchor_bbox), 1e-8):
            return False

    return True


def can_attach_ocr_fragment_to_formula_match(ocr_region: Dict[str, Any], match_pair: Dict[str, Any]) -> bool:
    """Mirror of can_attach_pdf_fragment_to_formula_match for unmatched OCR fragments."""
    if match_pair.get("record_type") != "matched":
        return False
    if match_pair.get("compare_status") != "skipped_formula":
        return False

    text = clean_text(ocr_region.get("text", ""))
    if not text:
        return False

    if not is_formula_fragment_text(text):
        return False

    pdf_anchor = (match_pair.get("pdf_region") or {}).get("bbox")
    ocr_anchor = (match_pair.get("ocr_region") or {}).get("bbox")
    if not pdf_anchor and not ocr_anchor:
        return False

    region_bbox = ocr_region["bbox"]
    near_pdf = is_region_near_anchor(region_bbox, pdf_anchor) if pdf_anchor else False
    near_ocr = is_region_near_anchor(region_bbox, ocr_anchor) if ocr_anchor else False
    if not (near_pdf or near_ocr):
        return False

    anchor_bbox = ocr_anchor or pdf_anchor
    if anchor_bbox is not None:
        if bbox_area(region_bbox) > 0.70 * max(bbox_area(anchor_bbox), 1e-8):
            return False

    return True


# ------------------------------------------------------------
# Render PDF pages to images
# ------------------------------------------------------------
def render_pdf_to_images(pdf_path: str, output_dir: str | Path, dpi: int = 200) -> List[Dict[str, Any]]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    results: List[Dict[str, Any]] = []
    try:
        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = output_dir / f"page_{page_idx + 1:04d}.png"
            pix.save(str(image_path))
            results.append({
                "page_num": page_idx + 1,
                "image_path": str(image_path),
                "image_width": pix.width,
                "image_height": pix.height,
                "pdf_width": float(page.rect.width),
                "pdf_height": float(page.rect.height),
            })
    finally:
        doc.close()
    return results


# ------------------------------------------------------------
# Extract PDF native text regions with bbox
# ------------------------------------------------------------
def extract_pdf_regions_with_bbox(pdf_path: str, granularity: str = "line") -> List[Dict[str, Any]]:
    granularity = granularity.lower().strip()
    if granularity not in {"line", "word", "span"}:
        raise ValueError("granularity must be one of: line, word, span")

    doc = fitz.open(pdf_path)
    pages: List[Dict[str, Any]] = []
    try:
        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            page_dict = page.get_text("dict")
            regions: List[Dict[str, Any]] = []
            region_id = 0

            if granularity == "word":
                for w in page.get_text("words"):
                    x1, y1, x2, y2, text, *_ = w
                    text = clean_text(text)
                    if not text:
                        continue
                    regions.append({
                        "region_id": region_id,
                        "page_num": page_idx + 1,
                        "bbox": [float(x1), float(y1), float(x2), float(y2)],
                        "text": text,
                        "source": "pdf",
                    })
                    region_id += 1
            else:
                for block in page_dict.get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        if not spans:
                            continue

                        if granularity == "span":
                            for span in spans:
                                text = clean_text(span.get("text", ""))
                                bbox = normalize_bbox(span.get("bbox"))
                                if not text or bbox is None:
                                    continue
                                regions.append({
                                    "region_id": region_id,
                                    "page_num": page_idx + 1,
                                    "bbox": bbox,
                                    "text": text,
                                    "source": "pdf",
                                })
                                region_id += 1
                        else:
                            line_text = clean_text(" ".join(span.get("text", "") for span in spans))
                            if not line_text:
                                continue
                            boxes = []
                            for span in spans:
                                bbox = normalize_bbox(span.get("bbox"))
                                if bbox is not None:
                                    boxes.append(bbox)
                            if not boxes:
                                continue
                            regions.append({
                                "region_id": region_id,
                                "page_num": page_idx + 1,
                                "bbox": bbox_union(boxes),
                                "text": line_text,
                                "source": "pdf",
                            })
                            region_id += 1

            pages.append({
                "page_num": page_idx + 1,
                "pdf_width": float(page.rect.width),
                "pdf_height": float(page.rect.height),
                "regions": regions,
            })
    finally:
        doc.close()
    return pages


# ------------------------------------------------------------
# OCR with Surya and map OCR bbox -> PDF coords
# ------------------------------------------------------------
def scale_ocr_bbox_to_pdf(ocr_bbox: List[float], image_width: float, image_height: float, pdf_width: float, pdf_height: float) -> List[float]:
    sx = pdf_width / max(image_width, 1e-8)
    sy = pdf_height / max(image_height, 1e-8)
    return [ocr_bbox[0] * sx, ocr_bbox[1] * sy, ocr_bbox[2] * sx, ocr_bbox[3] * sy]


def ocr_images_with_surya(image_infos: List[Dict[str, Any]], batch_size: int = 8) -> List[Dict[str, Any]]:
    recognition_predictor, detection_predictor = get_surya_predictors()
    results: List[Dict[str, Any]] = []

    for start in range(0, len(image_infos), batch_size):
        batch_infos = image_infos[start:start + batch_size]
        images: List[Image.Image] = []
        try:
            for item in batch_infos:
                with Image.open(item["image_path"]) as im:
                    images.append(im.convert("RGB"))

            predictions = recognition_predictor(images, det_predictor=detection_predictor)
            for item, pred in zip(batch_infos, predictions):
                page_regions: List[Dict[str, Any]] = []
                region_id = 0
                for line in getattr(pred, "text_lines", []) or []:
                    raw_text = getattr(line, "text", "") or ""
                    text = clean_text(raw_text)
                    bbox_img = normalize_bbox(getattr(line, "bbox", None))
                    if not text or bbox_img is None:
                        continue
                    bbox_pdf = scale_ocr_bbox_to_pdf(
                        bbox_img,
                        item["image_width"],
                        item["image_height"],
                        item["pdf_width"],
                        item["pdf_height"],
                    )
                    page_regions.append({
                        "region_id": region_id,
                        "page_num": item["page_num"],
                        "bbox": bbox_pdf,
                        "bbox_image": bbox_img,
                        "text": text,
                        "raw_text": raw_text,
                        "source": "ocr",
                    })
                    region_id += 1

                results.append({
                    "page_num": item["page_num"],
                    "pdf_width": item["pdf_width"],
                    "pdf_height": item["pdf_height"],
                    "image_width": item["image_width"],
                    "image_height": item["image_height"],
                    "regions": page_regions,
                })
        finally:
            for img in images:
                try:
                    img.close()
                except Exception:
                    pass
    return results


# ------------------------------------------------------------
# OCR-guided merge of PDF regions
# ------------------------------------------------------------
def should_make_ocr_cover_candidate(ocr_region: Dict[str, Any], group: List[Dict[str, Any]]) -> bool:
    """
    Decide whether to create an OCR-anchored grouped PDF candidate.

    This is intentionally conservative: we only create the grouped candidate when
    the OCR box plausibly corresponds to multiple fragmented PDF regions, or when
    the region looks formula-like and the grouped union covers a meaningful part
    of the OCR box.
    """
    if len(group) < 2:
        return False

    ocr_bbox = ocr_region["bbox"]
    union_bbox = bbox_union([r["bbox"] for r in group])
    if not union_bbox:
        return False

    overlap_ocr = bbox_overlap_over_ocr(union_bbox, ocr_bbox)
    overlap_union = bbox_overlap_over_pdf(union_bbox, ocr_bbox)

    ordered_group = sort_regions_in_reading_order(group)
    group_text = clean_text(" ".join(r.get("text", "") for r in ordered_group))
    ocr_text = clean_text(ocr_region.get("text", ""))

    ocr_sig = math_signal_score(ocr_text)
    group_sig = math_signal_score(group_text)
    formula_like = (
        max(ocr_sig["display_formula_score"], group_sig["display_formula_score"]) >= 2.2
        or ocr_sig["latex_cmds"] >= 1.0
        or max(ocr_sig["math_char_ratio"], group_sig["math_char_ratio"]) >= 0.18
    )

    ys = [bbox_center_y(r["bbox"]) for r in group]
    hs = [max(1.0, bbox_height(r["bbox"])) for r in group]
    vertical_span = (max(ys) - min(ys)) if ys else 0.0
    fragmented_layout = len(group) >= 3 or vertical_span >= 1.2 * median(hs)

    if formula_like:
        return overlap_ocr >= 0.18 and (fragmented_layout or overlap_union >= 0.35)

    return fragmented_layout and overlap_ocr >= 0.30 and overlap_union >= 0.40


def build_pdf_match_candidates(
    pdf_regions: List[Dict[str, Any]],
    ocr_regions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for reg in pdf_regions:
        candidates.append({
            "candidate_id": f"single_{reg['region_id']}",
            "page_num": reg["page_num"],
            "bbox": reg["bbox"],
            "text": reg.get("text", ""),
            "source": "pdf",
            "component_region_ids": [reg["region_id"]],
            "merged": False,
            "merge_kind": "single",
        })

    merged_seen = set()

    # 1) 原有的行级 / 邻近合并，适合普通文本或同一行公式片段
    for ocr_region in ocr_regions:
        ob = ocr_region["bbox"]
        ocr_w = bbox_width(ob)
        ocr_h = bbox_height(ob)
        margin_x = max(6.0, 0.06 * ocr_w)
        margin_y = max(3.0, 0.20 * ocr_h)
        expanded = [ob[0] - margin_x, ob[1] - margin_y, ob[2] + margin_x, ob[3] + margin_y]

        nearby: List[Dict[str, Any]] = []
        for reg in pdf_regions:
            pb = reg["bbox"]
            center_x = (pb[0] + pb[2]) / 2.0
            center_y = (pb[1] + pb[3]) / 2.0
            center_inside = expanded[0] <= center_x <= expanded[2] and expanded[1] <= center_y <= expanded[3]
            overlap_pdf = bbox_overlap_over_pdf(pb, expanded)
            overlap_ocr = bbox_overlap_over_ocr(pb, expanded)
            if center_inside or overlap_pdf >= 0.03 or overlap_ocr >= 0.01:
                nearby.append(reg)

        if len(nearby) < 2:
            continue

        heights = [max(1.0, bbox_height(r["bbox"])) for r in nearby]
        line_y_tol = max(5.0, 1.35 * median(heights))

        nearby_sorted = sorted(nearby, key=lambda r: (bbox_center_y(r["bbox"]), r["bbox"][0]))
        lines: List[List[Dict[str, Any]]] = []
        for reg in nearby_sorted:
            cy = bbox_center_y(reg["bbox"])
            if not lines:
                lines.append([reg])
                continue
            last_line = lines[-1]
            line_cy = sum(bbox_center_y(x["bbox"]) for x in last_line) / len(last_line)
            if abs(cy - line_cy) <= line_y_tol:
                last_line.append(reg)
            else:
                lines.append([reg])

        for line_regs in lines:
            line_regs = sorted(line_regs, key=lambda r: r["bbox"][0])
            current_group: List[Dict[str, Any]] = []
            for reg in line_regs:
                if not current_group:
                    current_group = [reg]
                    continue
                prev = current_group[-1]
                prev_bbox = prev["bbox"]
                cur_bbox = reg["bbox"]
                gap_x = cur_bbox[0] - prev_bbox[2]
                allow_gap = max(26.0, 0.42 * ocr_w, 3.0 * max(bbox_height(prev_bbox), bbox_height(cur_bbox)))
                vertical_close = abs(bbox_center_y(prev_bbox) - bbox_center_y(cur_bbox)) <= line_y_tol
                if gap_x <= allow_gap and vertical_close:
                    current_group.append(reg)
                else:
                    if len(current_group) >= 2:
                        comp_ids = tuple(sorted(r["region_id"] for r in current_group))
                        if comp_ids not in merged_seen:
                            merged_seen.add(comp_ids)
                            ordered_group = sort_regions_in_reading_order(current_group)
                            candidates.append({
                                "candidate_id": "merged_" + "_".join(map(str, comp_ids)),
                                "page_num": current_group[0]["page_num"],
                                "bbox": bbox_union([r["bbox"] for r in current_group]),
                                "text": clean_text(" ".join(r.get("text", "") for r in ordered_group)),
                                "source": "pdf",
                                "component_region_ids": list(comp_ids),
                                "merged": True,
                                "merge_kind": "line_merge",
                            })
                    current_group = [reg]

            if len(current_group) >= 2:
                comp_ids = tuple(sorted(r["region_id"] for r in current_group))
                if comp_ids not in merged_seen:
                    merged_seen.add(comp_ids)
                    ordered_group = sort_regions_in_reading_order(current_group)
                    candidates.append({
                        "candidate_id": "merged_" + "_".join(map(str, comp_ids)),
                        "page_num": current_group[0]["page_num"],
                        "bbox": bbox_union([r["bbox"] for r in current_group]),
                        "text": clean_text(" ".join(r.get("text", "") for r in ordered_group)),
                        "source": "pdf",
                        "component_region_ids": list(comp_ids),
                        "merged": True,
                        "merge_kind": "line_merge",
                    })

    # 2) OCR 锚点聚合：不强行要求所有碎片能拼成一个“规整大框”，
    #    而是允许一个 OCR 公式框对应多个 PDF 小碎片的集合
    for ocr_region in ocr_regions:
        ob = ocr_region["bbox"]
        ocr_w = bbox_width(ob)
        ocr_h = bbox_height(ob)
        margin_x = max(25.0, 0.16 * ocr_w)
        margin_y = max(5.0, 0.24 * ocr_h)
        expanded = [ob[0] - margin_x, ob[1] - margin_y, ob[2] + margin_x, ob[3] + margin_y]

        group: List[Dict[str, Any]] = []
        for reg in pdf_regions:
            pb = reg["bbox"]
            center_x = (pb[0] + pb[2]) / 2.0
            center_y = (pb[1] + pb[3]) / 2.0
            center_inside = expanded[0] <= center_x <= expanded[2] and expanded[1] <= center_y <= expanded[3]
            overlap_pdf = bbox_overlap_over_pdf(pb, ob)
            overlap_ocr = bbox_overlap_over_ocr(pb, ob)
            contained_like = overlap_pdf >= 0.12 or (center_inside and overlap_ocr >= 0.008)
            if contained_like:
                group.append(reg)

        if not should_make_ocr_cover_candidate(ocr_region, group):
            continue

        ordered_group = sort_regions_in_reading_order(group)
        comp_ids = tuple(sorted(r["region_id"] for r in ordered_group))
        if comp_ids in merged_seen:
            continue

        merged_seen.add(comp_ids)
        candidates.append({
            "candidate_id": "ocrcover_" + "_".join(map(str, comp_ids)),
            "page_num": ordered_group[0]["page_num"],
            "bbox": bbox_union([r["bbox"] for r in ordered_group]),
            "text": clean_text(" ".join(r.get("text", "") for r in ordered_group)),
            "source": "pdf",
            "component_region_ids": list(comp_ids),
            "merged": True,
            "merge_kind": "ocr_cover",
        })

    return candidates


# ------------------------------------------------------------
# Geometry-first matching
# ------------------------------------------------------------
def bbox_match_metrics(pdf_candidate: Dict[str, Any], ocr_region: Dict[str, Any], page_w: float, page_h: float) -> Dict[str, float]:
    pb = pdf_candidate["bbox"]
    ob = ocr_region["bbox"]
    iou = bbox_iou(pb, ob)
    overlap_pdf = bbox_overlap_over_pdf(pb, ob)
    overlap_ocr = bbox_overlap_over_ocr(pb, ob)
    center_score = center_distance_score(pb, ob, page_w, page_h)
    score = 0.30 * overlap_pdf + 0.35 * overlap_ocr + 0.25 * iou + 0.10 * center_score
    if pdf_candidate.get("merged"):
        score += min(0.03, 0.01 * (len(pdf_candidate.get("component_region_ids", [])) - 1))
    if pdf_candidate.get("merge_kind") == "ocr_cover":
        score += min(0.04, 0.04 * overlap_ocr)
    return {
        "score": score,
        "iou": iou,
        "overlap_over_pdf": overlap_pdf,
        "overlap_over_ocr": overlap_ocr,
        "center_score": center_score,
    }


def match_pdf_and_ocr_bboxes(
    pdf_pages: List[Dict[str, Any]],
    ocr_pages: List[Dict[str, Any]],
    geom_threshold: float = 0.18,
) -> List[Dict[str, Any]]:
    ocr_map = {p["page_num"]: p for p in ocr_pages}
    records: List[Dict[str, Any]] = []

    for pdf_page in pdf_pages:
        page_num = pdf_page["page_num"]
        ocr_page = ocr_map.get(page_num, {"regions": []})
        page_w = float(pdf_page.get("pdf_width", 0.0))
        page_h = float(pdf_page.get("pdf_height", 0.0))

        pdf_regions = list(pdf_page.get("regions", []))
        ocr_regions = list(ocr_page.get("regions", []))
        pdf_candidates = build_pdf_match_candidates(pdf_regions, ocr_regions)

        candidates: List[Dict[str, Any]] = []
        for pdf_candidate in pdf_candidates:
            for ocr_region in ocr_regions:
                geom = bbox_match_metrics(pdf_candidate, ocr_region, page_w, page_h)
                allow = (
                    geom["overlap_over_pdf"] >= geom_threshold
                    or geom["overlap_over_ocr"] >= geom_threshold * 0.8
                    or geom["iou"] >= geom_threshold * 0.8
                )
                if not allow:
                    continue
                candidates.append({
                    "pdf_candidate": pdf_candidate,
                    "ocr_region": ocr_region,
                    "geom": geom,
                })

        candidates.sort(key=lambda x: x["geom"]["score"], reverse=True)

        used_pdf_component_ids = set()
        matched_ocr_ids = set()
        matched_pairs: List[Dict[str, Any]] = []
        formula_anchors: List[List[float]] = []

        for cand in candidates:
            ocr_id = (page_num, cand["ocr_region"]["region_id"])
            if cand["ocr_region"]["region_id"]  == 40 or cand["ocr_region"]["region_id"]  == 104:
                print('pause')
            comp_ids = tuple(cand["pdf_candidate"].get("component_region_ids", []))
            if ocr_id in matched_ocr_ids:
                continue
            blocked_cids = [cid for cid in comp_ids if (page_num, cid) in used_pdf_component_ids]
            if blocked_cids:
                print(
                    f"[BLOCKED_BY_PDF_COMPONENT] page={page_num}, "
                    f"ocr_region={cand['ocr_region']['region_id']}, "
                    f"candidate={cand['pdf_candidate']['candidate_id']}, "
                    f"comp_ids={comp_ids}, blocked_cids={blocked_cids}"
                )
                continue
            # if any((page_num, cid) in used_pdf_component_ids for cid in comp_ids):
            #     continue

            matched_ocr_ids.add(ocr_id)
            for cid in comp_ids:
                used_pdf_component_ids.add((page_num, cid))

            pdf_text = cand["pdf_candidate"].get("text", "")
            ocr_text = cand["ocr_region"].get("text", "")
            skip_formula_compare = is_display_formula_like(pdf_text, ocr_text)
            if skip_formula_compare:
                text_metrics = text_consistency_metrics(pdf_text, ocr_text)
                text_issue_flag = False
                suspicious_flag = False
                suspicious_reason = "formula_display_skipped"
                formula_anchors.append(cand["pdf_candidate"]["bbox"])
                formula_anchors.append(cand["ocr_region"]["bbox"])
            else:
                text_issue_flag, text_metrics, suspicious_reason = is_text_mismatch(pdf_text, ocr_text)
                suspicious_flag = text_issue_flag

            matched_pairs.append({
                "page_num": page_num,
                "record_type": "matched",
                "pdf_region": cand["pdf_candidate"],
                "ocr_region": cand["ocr_region"],
                "geom": cand["geom"],
                "text_metrics": text_metrics,
                "text_issue_flag": text_issue_flag,
                "suspicious_flag": suspicious_flag,
                "suspicious_reason": suspicious_reason,
                "compare_status": "skipped_formula" if skip_formula_compare else "compared",
            })

        attached_pdf_ids = set()
        for pdf_region in pdf_regions:
            pid = (page_num, pdf_region["region_id"])
            if pid in used_pdf_component_ids:
                continue
            for mp in matched_pairs:
                if can_attach_pdf_fragment_to_formula_match(pdf_region, mp):
                    attached_pdf_ids.add(pid)
                    formula_anchors.append(pdf_region["bbox"])
                    break

        attached_ocr_ids = set()
        for ocr_region in ocr_regions:
            oid = (page_num, ocr_region["region_id"])
            if oid in matched_ocr_ids:
                continue
            for mp in matched_pairs:
                if can_attach_ocr_fragment_to_formula_match(ocr_region, mp):
                    attached_ocr_ids.add(oid)
                    formula_anchors.append(ocr_region["bbox"])
                    break

        for pdf_region in pdf_regions:
            if (page_num, pdf_region["region_id"]) in used_pdf_component_ids or (page_num, pdf_region["region_id"]) in attached_pdf_ids:
                continue
            skip_formula_fragment = is_formula_fragment_text(pdf_region.get("text", "")) and any(
                is_region_near_anchor(pdf_region["bbox"], anchor) for anchor in formula_anchors
            )
            matched_pairs.append({
                "page_num": page_num,
                "record_type": "pdf_only",
                "pdf_region": pdf_region,
                "ocr_region": None,
                "geom": {"score": 0.0, "iou": 0.0, "overlap_over_pdf": 0.0, "overlap_over_ocr": 0.0, "center_score": 0.0},
                "text_metrics": {"ratio": 0.0, "partial_ratio": 0.0, "token_sort_ratio": 0.0, "length_gap": 1.0},
                "text_issue_flag": False,
                "suspicious_flag": False if skip_formula_fragment else True,
                "suspicious_reason": "formula_fragment_skipped" if skip_formula_fragment else "pdf_only_bbox",
                "compare_status": "skipped_formula" if skip_formula_fragment else "unmatched",
            })

        for ocr_region in ocr_regions:
            if (page_num, ocr_region["region_id"]) in matched_ocr_ids or (page_num, ocr_region["region_id"]) in attached_ocr_ids:
                continue
            skip_formula_fragment = is_formula_fragment_text(ocr_region.get("text", "")) and any(
                is_region_near_anchor(ocr_region["bbox"], anchor) for anchor in formula_anchors
            )
            matched_pairs.append({
                "page_num": page_num,
                "record_type": "ocr_only",
                "pdf_region": None,
                "ocr_region": ocr_region,
                "geom": {"score": 0.0, "iou": 0.0, "overlap_over_pdf": 0.0, "overlap_over_ocr": 0.0, "center_score": 0.0},
                "text_metrics": {"ratio": 0.0, "partial_ratio": 0.0, "token_sort_ratio": 0.0, "length_gap": 1.0},
                "text_issue_flag": False,
                "suspicious_flag": False if skip_formula_fragment else True,
                "suspicious_reason": "formula_fragment_skipped" if skip_formula_fragment else "ocr_only_bbox",
                "compare_status": "skipped_formula" if skip_formula_fragment else "unmatched",
            })

        records.extend(sorted(matched_pairs, key=lambda x: (
            x["page_num"],
            {"matched": 0, "pdf_only": 1, "ocr_only": 2}[x["record_type"]],
            min(x["pdf_region"].get("component_region_ids", [10**9])) if x.get("pdf_region") else 10**9,
            x["ocr_region"]["region_id"] if x.get("ocr_region") else 10**9,
        )))

    return records


# ------------------------------------------------------------
# Export simplified records
# ------------------------------------------------------------
def build_export_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in records:
        pdf_region = item.get("pdf_region") or {}
        ocr_region = item.get("ocr_region") or {}
        text_metrics = item.get("text_metrics") or {}

        out.append({
            "page_num": int(item.get("page_num", 0)),
            "record_type": item.get("record_type", ""),
            "compare_status": item.get("compare_status", "compared"),
            "pdf_bbox": pdf_region.get("bbox"),
            "pdf_bbox_str": bbox_to_compact_str(pdf_region.get("bbox")),
            "ocr_bbox": ocr_region.get("bbox"),
            "ocr_bbox_str": bbox_to_compact_str(ocr_region.get("bbox")),
            "pdf_text": pdf_region.get("text", ""),
            "ocr_text": ocr_region.get("text", ""),
            "text_similarity": float(text_metrics.get("ratio", 0.0)),
            "suspicious_flag": bool(item.get("suspicious_flag", False)),
            "suspicious_reason": item.get("suspicious_reason", ""),
        })
    return out


def filter_suspicious_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in records if row.get("suspicious_flag", False)]


def can_attach_pdf_fragment_to_text_match(pdf_only_record: Dict[str, Any], match_pair: Dict[str, Any]) -> bool:
    if pdf_only_record.get("record_type") != "pdf_only":
        return False
    if match_pair.get("record_type") != "matched":
        return False
    if match_pair.get("compare_status") != "compared":
        return False
    if match_pair.get("suspicious_flag"):
        return False

    pdf_region = pdf_only_record.get("pdf_region") or {}
    ocr_region = match_pair.get("ocr_region") or {}
    if not pdf_region or not ocr_region:
        return False

    pb = pdf_region.get("bbox")
    ob = ocr_region.get("bbox")
    if not pb or not ob:
        return False

    text = clean_text(pdf_region.get("text", ""))
    if not text:
        return False

    ocr_h = bbox_height(ob)
    ocr_w = bbox_width(ob)
    same_line = (
        abs(pb[1] - ob[1]) <= max(4.0, 0.20 * ocr_h)
        or abs(bbox_center_y(pb) - bbox_center_y(ob)) <= max(5.0, 0.24 * ocr_h)
    )
    x_related = horizontal_gap(pb, ob) <= max(24.0, 0.18 * ocr_w)

    if bbox_area(pb) > 0.55 * max(bbox_area(ob), 1e-8):
        return False

    return same_line and x_related


def can_attach_pdf_fragment_to_suspicious_match(pdf_only_record: Dict[str, Any], suspicious_match: Dict[str, Any]) -> bool:
    if pdf_only_record.get("record_type") != "pdf_only":
        return False
    if not pdf_only_record.get("suspicious_flag", False):
        return False
    if suspicious_match.get("record_type") != "matched":
        return False
    if suspicious_match.get("compare_status") != "compared":
        return False
    if not suspicious_match.get("suspicious_flag", False):
        return False

    pdf_region = pdf_only_record.get("pdf_region") or {}
    anchor_pdf = suspicious_match.get("pdf_region") or {}
    anchor_ocr = suspicious_match.get("ocr_region") or {}
    if not pdf_region or not anchor_pdf or not anchor_ocr:
        return False

    pb = pdf_region.get("bbox")
    ab = anchor_pdf.get("bbox")
    ob = anchor_ocr.get("bbox")
    if not pb or not ab or not ob:
        return False

    text = clean_text(pdf_region.get("text", ""))
    if not text:
        return False

    anchor_h = bbox_height(ab)
    anchor_w = bbox_width(ab)
    ocr_w = bbox_width(ob)
    same_line = (
        abs(pb[1] - ab[1]) <= max(4.0, 0.18 * anchor_h)
        or abs(pb[3] - ab[3]) <= max(4.0, 0.18 * anchor_h)
        or abs(bbox_center_y(pb) - bbox_center_y(ab)) <= max(5.0, 0.20 * anchor_h)
    )
    x_related = horizontal_gap(pb, ab) <= max(28.0, 0.22 * max(anchor_w, ocr_w))
    x_overlap = not (pb[2] < ab[0] or pb[0] > ab[2])

    if bbox_area(pb) > 0.70 * max(bbox_area(ab), 1e-8):
        return False

    return same_line and (x_related or x_overlap)


def build_candidate_text_from_regions(regions: List[Dict[str, Any]]) -> str:
    if not regions:
        return ""
    ordered = sort_regions_in_reading_order(regions)
    return clean_text(" ".join(r.get("text", "") for r in ordered))


def text_reassembly_quality(metrics: Dict[str, float]) -> float:
    return (
        0.55 * metrics.get("ratio", 0.0)
        + 0.15 * metrics.get("partial_ratio", 0.0)
        + 0.10 * metrics.get("token_sort_ratio", 0.0)
        - 0.35 * metrics.get("length_gap", 0.0)
    )


def select_best_text_reassembly(
    match_pair: Dict[str, Any],
    nearby_pdf_only_records: List[Dict[str, Any]],
    max_nearby: int = 6,
    max_subset_size: int = 4,
) -> Optional[Dict[str, Any]]:
    if not nearby_pdf_only_records:
        return None

    base_pdf_region = match_pair.get("pdf_region") or {}
    ocr_region = match_pair.get("ocr_region") or {}
    if not base_pdf_region or not ocr_region:
        return None

    ocr_text = ocr_region.get("text", "")
    base_metrics = text_consistency_metrics(base_pdf_region.get("text", ""), ocr_text)
    base_quality = text_reassembly_quality(base_metrics)

    ob = ocr_region.get("bbox")
    ranked = sorted(
        nearby_pdf_only_records,
        key=lambda r: (
            horizontal_gap((r.get("pdf_region") or {}).get("bbox", [0, 0, 0, 0]), ob),
            abs(((r.get("pdf_region") or {}).get("bbox", [0, 0, 0, 0])[1]) - ob[1]),
        ),
    )[:max_nearby]

    best: Optional[Dict[str, Any]] = None
    best_quality = base_quality
    n = len(ranked)
    max_k = min(max_subset_size, n)

    for k in range(1, max_k + 1):
        for subset in combinations(ranked, k):
            subset_regions = [base_pdf_region] + [(rec.get("pdf_region") or {}) for rec in subset]
            merged_text = build_candidate_text_from_regions(subset_regions)
            merged_metrics = text_consistency_metrics(merged_text, ocr_text)
            merged_quality = text_reassembly_quality(merged_metrics)

            improvement = merged_quality - base_quality
            ratio_gain = merged_metrics["ratio"] - base_metrics["ratio"]
            gap_drop = base_metrics["length_gap"] - merged_metrics["length_gap"]

            accept = (
                improvement >= 0.08
                and (ratio_gain >= 0.04 or gap_drop >= 0.10)
                and merged_metrics["ratio"] >= max(0.42, base_metrics["ratio"] - 0.02)
            )

            if not accept:
                continue

            if merged_quality > best_quality:
                best_quality = merged_quality
                best = {
                    "subset": list(subset),
                    "merged_text": merged_text,
                    "metrics_before": base_metrics,
                    "metrics_after": merged_metrics,
                    "quality_before": base_quality,
                    "quality_after": merged_quality,
                }

    return best


def build_refined_suspicious_records(raw_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    page_map: Dict[int, List[Dict[str, Any]]] = {}
    for rec in raw_records:
        page_map.setdefault(int(rec.get("page_num", 0)), []).append(rec)

    repaired_pdf_only: Dict[Tuple[int, int], Dict[str, Any]] = {}
    repaired_anchor_info: Dict[Tuple[int, str], Dict[str, Any]] = {}

    for page_num, page_records in page_map.items():
        suspicious_matched_records = [
            r for r in page_records
            if r.get("record_type") == "matched"
            and r.get("compare_status") == "compared"
            and r.get("suspicious_flag", False)
        ]
        pdf_only_records = [
            r for r in page_records
            if r.get("record_type") == "pdf_only"
            and r.get("suspicious_flag", False)
        ]

        claimed_ids = set()
        suspicious_matched_records = sorted(
            suspicious_matched_records,
            key=lambda r: (
                ((r.get("pdf_region") or {}).get("bbox", [0, 0, 0, 0])[1]),
                ((r.get("pdf_region") or {}).get("bbox", [0, 0, 0, 0])[0]),
            ),
        )

        for mp in suspicious_matched_records:
            nearby = []
            for rec in pdf_only_records:
                rid = (page_num, (rec.get("pdf_region") or {}).get("region_id"))
                if rid in claimed_ids:
                    continue
                if can_attach_pdf_fragment_to_suspicious_match(rec, mp):
                    nearby.append(rec)

            best = select_best_text_reassembly(mp, nearby)
            if not best:
                continue

            target_ocr = mp.get("ocr_region") or {}
            target_pdf = mp.get("pdf_region") or {}
            anchor_key = (page_num, target_pdf.get("candidate_id", ""))
            group_ids = []
            for rec in best["subset"]:
                rid = (page_num, (rec.get("pdf_region") or {}).get("region_id"))
                claimed_ids.add(rid)
                group_ids.append((rec.get("pdf_region") or {}).get("region_id"))
                repaired_pdf_only[rid] = {
                    "refined_suspicious_flag": False,
                    "refined_label": "reattached_to_suspicious_match",
                    "refine_reason": "pdf_only_reassembled_with_suspicious_match",
                    "repair_target_ocr_region_id": target_ocr.get("region_id"),
                    "repair_target_pdf_candidate_id": target_pdf.get("candidate_id", ""),
                    "repair_group_pdf_ids": group_ids,
                    "repair_text_similarity_before": best["metrics_before"]["ratio"],
                    "repair_text_similarity_after": best["metrics_after"]["ratio"],
                    "repair_length_gap_before": best["metrics_before"]["length_gap"],
                    "repair_length_gap_after": best["metrics_after"]["length_gap"],
                }

            repaired_anchor_info[anchor_key] = {
                "refined_suspicious_flag": False,
                "refined_label": "suspicious_match_expanded",
                "refine_reason": "suspicious_match_absorbed_nearby_pdf_only",
                "repair_target_ocr_region_id": target_ocr.get("region_id"),
                "repair_target_pdf_candidate_id": target_pdf.get("candidate_id", ""),
                "repair_group_pdf_ids": group_ids,
                "repair_text_similarity_before": best["metrics_before"]["ratio"],
                "repair_text_similarity_after": best["metrics_after"]["ratio"],
                "repair_length_gap_before": best["metrics_before"]["length_gap"],
                "repair_length_gap_after": best["metrics_after"]["length_gap"],
            }

    refined_rows: List[Dict[str, Any]] = []
    for item in raw_records:
        if not item.get("suspicious_flag", False):
            continue

        pdf_region = item.get("pdf_region") or {}
        ocr_region = item.get("ocr_region") or {}
        text_metrics = item.get("text_metrics") or {}
        row = {
            "page_num": int(item.get("page_num", 0)),
            "record_type": item.get("record_type", ""),
            "compare_status": item.get("compare_status", "compared"),
            "pdf_bbox_str": bbox_to_compact_str(pdf_region.get("bbox")),
            "ocr_bbox_str": bbox_to_compact_str(ocr_region.get("bbox")),
            "pdf_text": pdf_region.get("text", ""),
            "ocr_text": ocr_region.get("text", ""),
            "text_similarity": float(text_metrics.get("ratio", 0.0)),
            "suspicious_flag": bool(item.get("suspicious_flag", False)),
            "suspicious_reason": item.get("suspicious_reason", ""),
            "refined_suspicious_flag": bool(item.get("suspicious_flag", False)),
            "refined_label": "keep_suspicious",
            "refine_reason": "",
            "repair_target_ocr_region_id": "",
            "repair_target_pdf_candidate_id": "",
            "repair_group_pdf_ids": "",
            "repair_text_similarity_before": "",
            "repair_text_similarity_after": "",
            "repair_length_gap_before": "",
            "repair_length_gap_after": "",
        }

        if item.get("record_type") == "pdf_only":
            rid = (row["page_num"], pdf_region.get("region_id"))
            if rid in repaired_pdf_only:
                info = repaired_pdf_only[rid]
                row.update(info)
                row["repair_group_pdf_ids"] = ",".join(str(x) for x in info["repair_group_pdf_ids"])
        elif item.get("record_type") == "matched":
            key = (row["page_num"], pdf_region.get("candidate_id", ""))
            if key in repaired_anchor_info:
                info = repaired_anchor_info[key]
                row.update(info)
                row["repair_group_pdf_ids"] = ",".join(str(x) for x in info["repair_group_pdf_ids"])

        refined_rows.append(row)

    return refined_rows

def write_refined_records_json_csv(records: List[Dict[str, Any]], json_path: str | Path, csv_path: str | Path) -> None:
    json_path = Path(json_path)
    csv_path = Path(csv_path)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    fields = [
        "page_num",
        "record_type",
        "compare_status",
        "pdf_bbox_str",
        "ocr_bbox_str",
        "pdf_text",
        "ocr_text",
        "text_similarity",
        "suspicious_flag",
        "suspicious_reason",
        "refined_suspicious_flag",
        "refined_label",
        "refine_reason",
        "repair_target_ocr_region_id",
        "repair_target_pdf_candidate_id",
        "repair_group_pdf_ids",
        "repair_text_similarity_before",
        "repair_text_similarity_after",
        "repair_length_gap_before",
        "repair_length_gap_after",
    ]

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({k: row.get(k, "") for k in fields})


def write_records_json_csv(records: List[Dict[str, Any]], json_path: str | Path, csv_path: str | Path) -> None:
    json_path = Path(json_path)
    csv_path = Path(csv_path)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    fields = [
        "page_num",
        "record_type",
        "compare_status",
        "pdf_bbox_str",
        "ocr_bbox_str",
        "pdf_text",
        "ocr_text",
        "text_similarity",
        "suspicious_flag",
        "suspicious_reason",
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({k: row.get(k, "") for k in fields})


# ------------------------------------------------------------
# Main pipeline
# ------------------------------------------------------------
def run_pdf_bbox_match_and_compare(
    pdf_path: str,
    work_dir: str | Path = "output_bbox_align",
    dpi: int = 200,
    pdf_granularity: str = "line",
    batch_size: int = 8,
    geom_threshold: float = 0.18,
) -> Dict[str, Any]:
    work_dir = Path(work_dir)
    image_dir = work_dir / "images"
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"[PDF] {pdf_path}")
    print("[1] Rendering PDF pages to images...")
    image_infos = render_pdf_to_images(pdf_path, image_dir, dpi=dpi)

    print("[2] Extracting PDF text regions with bbox...")
    pdf_pages = extract_pdf_regions_with_bbox(pdf_path, granularity=pdf_granularity)

    print("[3] Running OCR with Surya...")
    ocr_pages = ocr_images_with_surya(image_infos, batch_size=batch_size)

    print("[4] Matching PDF bbox with OCR bbox (with PDF-side merge candidates)...")
    raw_records = match_pdf_and_ocr_bboxes(
        pdf_pages,
        ocr_pages,
        geom_threshold=geom_threshold,
    )

    print("[5] Exporting simplified comparison records...")
    export_records = build_export_records(raw_records)
    suspicious_records = filter_suspicious_records(export_records)

    all_json = work_dir / "bbox_records.json"
    all_csv = work_dir / "bbox_records.csv"
    suspicious_json = work_dir / "suspicious_bbox_records.json"
    suspicious_csv = work_dir / "suspicious_bbox_records.csv"
    refined_json = work_dir / "suspicious_bbox_records_refined.json"
    refined_csv = work_dir / "suspicious_bbox_records_refined.csv"

    write_records_json_csv(export_records, all_json, all_csv)
    write_records_json_csv(suspicious_records, suspicious_json, suspicious_csv)

    print("[6] Refining suspicious records with local reassembly...")
    refined_suspicious_records = build_refined_suspicious_records(raw_records)
    write_refined_records_json_csv(refined_suspicious_records, refined_json, refined_csv)

    print(f"[DONE] bbox_records.csv -> {all_csv}")
    print(f"[DONE] suspicious_bbox_records.csv -> {suspicious_csv}")
    print(f"[DONE] suspicious_bbox_records_refined.csv -> {refined_csv}")

    return {
        "bbox_records": export_records,
        "suspicious_bbox_records": suspicious_records,
        "suspicious_bbox_records_refined": refined_suspicious_records,
        "output_dir": str(work_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract text bboxes from PDF and OCR, match them by geometry, then compare text content."
    )
    parser.add_argument("pdf_path", type=str, help="Path to the input PDF")
    parser.add_argument("--work-dir", type=str, default="output_bbox_align", help="Output directory")
    parser.add_argument("--dpi", type=int, default=200, help="Render DPI")
    parser.add_argument("--pdf-granularity", type=str, default="line", choices=["line", "word", "span"], help="PDF extraction granularity")
    parser.add_argument("--batch-size", type=int, default=8, help="Surya batch size")
    parser.add_argument("--geom-threshold", type=float, default=0.18, help="Geometry overlap threshold")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not Path(args.pdf_path).exists():
        raise FileNotFoundError(f"PDF not found: {args.pdf_path}")

    run_pdf_bbox_match_and_compare(
        pdf_path=args.pdf_path,
        work_dir=args.work_dir,
        dpi=args.dpi,
        pdf_granularity=args.pdf_granularity,
        batch_size=args.batch_size,
        geom_threshold=args.geom_threshold,
    )
