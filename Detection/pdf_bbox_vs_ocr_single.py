from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import unicodedata
from pathlib import Path
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
# Basic helpers
# ------------------------------------------------------------
MATH_SYMBOL_PATTERN = re.compile(r"[=+\-*/^_∑∫√∞≈≠≤≥→←∈∉⊂⊆⊇α-ωΑ-ΩσγλπθμνρτφψωΣΠΔ\[\]\(\)\{\}|]")
LATIN_WORD_PATTERN = re.compile(r"[A-Za-z]{2,}")
MATH_KEYWORD_PATTERN = re.compile(r"\b(max|min|argmax|argmin|lim|sup|inf)\b|E\(|P\(")
FORMULA_TAG_PATTERN = re.compile(r"</?math[^>]*>", re.IGNORECASE)
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
MULTISPACE_PATTERN = re.compile(r"\s+")

COMMON_CHAR_REPLACEMENTS = {
    "\u00ad": "",
    "\xa0": " ",
    "\u200b": "",
    "\u200c": "",
    "\u200d": "",
    "\ufeff": "",
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


def clean_text(text: str) -> str:
    if not text:
        return ""
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

    text = FORMULA_TAG_PATTERN.sub(" ", text)
    text = re.sub(r"<[^>]+>", " ", text)

    operator_rules = [
        (r"\s*:=\s*", " := "),
        (r"\s*\|\|\s*", " || "),
        (r"\s*<=\s*", " <= "),
        (r"\s*>=\s*", " >= "),
        (r"\s*!=\s*", " != "),
        (r"\s*==\s*", " == "),
        (r"\s*=\s*", " = "),
    ]
    for pattern, repl in operator_rules:
        text = re.sub(pattern, repl, text)

    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*;\s*", "; ", text)
    text = re.sub(r"\s+([.?!])", r"\1", text)
    text = re.sub(r"([\(\[\{])\s+", r"\1", text)
    text = re.sub(r"\s+([\)\]\}])", r"\1", text)
    text = MULTISPACE_PATTERN.sub(" ", text).strip()
    return text


def is_formula_like_text(text: str) -> bool:
    text = clean_text(text)
    if not text:
        return False
    if FORMULA_TAG_PATTERN.search(text):
        return True
    if text.startswith("="):
        return True
    math_kw = len(MATH_KEYWORD_PATTERN.findall(text))
    math_sym = len(MATH_SYMBOL_PATTERN.findall(text))
    latin_words = len(LATIN_WORD_PATTERN.findall(text))
    alpha_ratio = sum(ch.isalpha() for ch in text) / max(1, len(text))
    if math_kw >= 1 and math_sym >= 2:
        return True
    if math_sym >= 6 and latin_words <= 12:
        return True
    if alpha_ratio < 0.55 and math_sym >= 5:
        return True
    return False


def text_similarity(a: str, b: str) -> float:
    a = clean_text(a)
    b = clean_text(b)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return fuzz.ratio(a, b) / 100.0


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


def bbox_overlap_over_pdf(pdf_bbox: List[float], ocr_bbox: List[float]) -> float:
    inter_x1 = max(pdf_bbox[0], ocr_bbox[0])
    inter_y1 = max(pdf_bbox[1], ocr_bbox[1])
    inter_x2 = min(pdf_bbox[2], ocr_bbox[2])
    inter_y2 = min(pdf_bbox[3], ocr_bbox[3])
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter = inter_w * inter_h
    return inter / max(bbox_area(pdf_bbox), 1e-8)


def center_distance_score(a: List[float], b: List[float], page_w: float, page_h: float) -> float:
    ax = (a[0] + a[2]) / 2.0
    ay = (a[1] + a[3]) / 2.0
    bx = (b[0] + b[2]) / 2.0
    by = (b[1] + b[3]) / 2.0
    dist = math.hypot(ax - bx, ay - by)
    diag = math.hypot(max(page_w, 1.0), max(page_h, 1.0))
    return max(0.0, 1.0 - dist / max(diag, 1.0))


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
                        "type": "formula" if is_formula_like_text(text) else "text",
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
                                    "type": "formula" if is_formula_like_text(text) else "text",
                                })
                                region_id += 1
                        else:  # line
                            line_text = clean_text(" ".join(span.get("text", "") for span in spans))
                            if not line_text:
                                continue
                            xs1 = []
                            ys1 = []
                            xs2 = []
                            ys2 = []
                            for span in spans:
                                bbox = normalize_bbox(span.get("bbox"))
                                if bbox is None:
                                    continue
                                xs1.append(bbox[0])
                                ys1.append(bbox[1])
                                xs2.append(bbox[2])
                                ys2.append(bbox[3])
                            if not xs1:
                                continue
                            bbox = [min(xs1), min(ys1), max(xs2), max(ys2)]
                            regions.append({
                                "region_id": region_id,
                                "page_num": page_idx + 1,
                                "bbox": bbox,
                                "text": line_text,
                                "source": "pdf",
                                "type": "formula" if is_formula_like_text(line_text) else "text",
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
                    text = clean_text(getattr(line, "text", "") or "")
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
                        "source": "ocr",
                        "type": "formula" if is_formula_like_text(text) else "text",
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
# Alignment and suspicious region detection
# ------------------------------------------------------------
def region_match_score(pdf_region: Dict[str, Any], ocr_region: Dict[str, Any], page_w: float, page_h: float) -> Dict[str, float]:
    pb = pdf_region["bbox"]
    ob = ocr_region["bbox"]
    iou = bbox_iou(pb, ob)
    overlap_pdf = bbox_overlap_over_pdf(pb, ob)
    center_score = center_distance_score(pb, ob, page_w, page_h)
    txt_sim = text_similarity(pdf_region.get("text", ""), ocr_region.get("text", ""))

    # 几何优先，文本次要；公式默认少依赖文本相似度
    if pdf_region.get("type") == "formula" or ocr_region.get("type") == "formula":
        final_score = 0.55 * overlap_pdf + 0.35 * center_score + 0.10 * txt_sim
    else:
        final_score = 0.45 * overlap_pdf + 0.25 * iou + 0.15 * center_score + 0.15 * txt_sim

    return {
        "score": final_score,
        "iou": iou,
        "overlap_over_pdf": overlap_pdf,
        "center_score": center_score,
        "text_similarity": txt_sim,
    }


def align_pdf_and_ocr_regions(
    pdf_pages: List[Dict[str, Any]],
    ocr_pages: List[Dict[str, Any]],
    geom_threshold: float = 0.18,
    text_threshold: float = 0.25,
) -> List[Dict[str, Any]]:
    ocr_map = {p["page_num"]: p for p in ocr_pages}
    all_matches: List[Dict[str, Any]] = []

    for pdf_page in pdf_pages:
        page_num = pdf_page["page_num"]
        ocr_page = ocr_map.get(page_num, {"regions": []})
        page_w = float(pdf_page.get("pdf_width", 0.0))
        page_h = float(pdf_page.get("pdf_height", 0.0))

        for pdf_region in pdf_page.get("regions", []):
            best = None
            best_metrics = None
            for ocr_region in ocr_page.get("regions", []):
                metrics = region_match_score(pdf_region, ocr_region, page_w, page_h)
                # 文本很短时更依赖几何，长文本可以兼顾文本
                allow = (
                    metrics["overlap_over_pdf"] >= geom_threshold
                    or metrics["iou"] >= geom_threshold * 0.8
                    or (metrics["overlap_over_pdf"] >= geom_threshold * 0.65 and metrics["text_similarity"] >= text_threshold)
                )
                if not allow:
                    continue
                if best is None or metrics["score"] > best_metrics["score"]:
                    best = ocr_region
                    best_metrics = metrics

            match_item = {
                "page_num": page_num,
                "pdf_region": pdf_region,
                "ocr_region": best,
                "matched": best is not None,
                "metrics": best_metrics or {
                    "score": 0.0,
                    "iou": 0.0,
                    "overlap_over_pdf": 0.0,
                    "center_score": 0.0,
                    "text_similarity": 0.0,
                },
            }
            all_matches.append(match_item)
    return all_matches


def detect_pdf_only_regions(
    matches: List[Dict[str, Any]],
    min_text_len: int = 6,
    ignore_formula_regions: bool = True,
    strong_text_mismatch_threshold: float = 0.35,
) -> List[Dict[str, Any]]:
    suspicious: List[Dict[str, Any]] = []
    for item in matches:
        pdf_region = item["pdf_region"]
        text = clean_text(pdf_region.get("text", ""))
        region_type = str(pdf_region.get("type", "text"))

        if len(text) < min_text_len:
            continue
        if ignore_formula_regions and region_type == "formula":
            continue

        matched = item.get("matched", False)
        metrics = item.get("metrics", {})
        is_pdf_only = False
        reason = ""

        if not matched:
            is_pdf_only = True
            reason = "no_ocr_region_matched"
        else:
            overlap_pdf = float(metrics.get("overlap_over_pdf", 0.0))
            txt_sim = float(metrics.get("text_similarity", 0.0))
            # 有重叠但文本几乎完全不对应，且是正文，认为弱匹配中的可疑区
            if overlap_pdf < 0.20 and txt_sim < strong_text_mismatch_threshold:
                is_pdf_only = True
                reason = "weak_geometric_match_and_low_text_similarity"

        if is_pdf_only:
            suspicious.append({
                "page_num": item["page_num"],
                "reason": reason,
                "pdf_region": pdf_region,
                "ocr_region": item.get("ocr_region"),
                "metrics": metrics,
            })
    return suspicious


def summarize_by_page(matches: List[Dict[str, Any]], suspicious_regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    match_count: Dict[int, int] = {}
    total_count: Dict[int, int] = {}
    suspicious_count: Dict[int, int] = {}
    avg_text_sim_acc: Dict[int, float] = {}

    for item in matches:
        p = int(item["page_num"])
        total_count[p] = total_count.get(p, 0) + 1
        if item.get("matched"):
            match_count[p] = match_count.get(p, 0) + 1
        avg_text_sim_acc[p] = avg_text_sim_acc.get(p, 0.0) + float(item.get("metrics", {}).get("text_similarity", 0.0))

    for item in suspicious_regions:
        p = int(item["page_num"])
        suspicious_count[p] = suspicious_count.get(p, 0) + 1

    pages = sorted(set(total_count) | set(suspicious_count))
    out = []
    for p in pages:
        total = total_count.get(p, 0)
        matched = match_count.get(p, 0)
        out.append({
            "page_num": p,
            "pdf_region_count": total,
            "matched_region_count": matched,
            "match_ratio": (matched / total) if total else 0.0,
            "avg_text_similarity": (avg_text_sim_acc.get(p, 0.0) / total) if total else 0.0,
            "suspicious_region_count": suspicious_count.get(p, 0),
            "suspicious": suspicious_count.get(p, 0) > 0,
        })
    return out


# ------------------------------------------------------------
# Main pipeline
# ------------------------------------------------------------
def run_pdf_implicit_injection_check_bbox(
    pdf_path: str,
    work_dir: str | Path = "output_bbox_align",
    dpi: int = 200,
    pdf_granularity: str = "line",
    batch_size: int = 8,
    geom_threshold: float = 0.18,
    text_threshold: float = 0.25,
    min_text_len: int = 6,
    ignore_formula_regions: bool = True,
) -> Dict[str, Any]:
    work_dir = Path(work_dir)
    image_dir = work_dir / "images"
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"[PDF] {pdf_path}")
    print("[1] Rendering PDF pages to images...")
    image_infos = render_pdf_to_images(pdf_path, image_dir, dpi=dpi)

    print("[2] Extracting PDF native regions with bbox...")
    pdf_pages = extract_pdf_regions_with_bbox(pdf_path, granularity=pdf_granularity)

    print("[3] Running OCR with Surya...")
    ocr_pages = ocr_images_with_surya(image_infos, batch_size=batch_size)

    print("[4] Aligning PDF regions with OCR regions...")
    matches = align_pdf_and_ocr_regions(
        pdf_pages,
        ocr_pages,
        geom_threshold=geom_threshold,
        text_threshold=text_threshold,
    )

    print("[5] Detecting PDF-only suspicious regions...")
    suspicious_regions = detect_pdf_only_regions(
        matches,
        min_text_len=min_text_len,
        ignore_formula_regions=ignore_formula_regions,
    )
    page_summary = summarize_by_page(matches, suspicious_regions)

    pdf_path_out = work_dir / "pdf_regions.json"
    ocr_path_out = work_dir / "ocr_pages.json"
    matches_path_out = work_dir / "matches.json"
    suspicious_path_out = work_dir / "suspicious_regions.json"
    summary_path_out = work_dir / "page_summary.json"

    with open(pdf_path_out, "w", encoding="utf-8") as f:
        json.dump(pdf_pages, f, ensure_ascii=False, indent=2)
    with open(ocr_path_out, "w", encoding="utf-8") as f:
        json.dump(ocr_pages, f, ensure_ascii=False, indent=2)
    with open(matches_path_out, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
    with open(suspicious_path_out, "w", encoding="utf-8") as f:
        json.dump(suspicious_regions, f, ensure_ascii=False, indent=2)
    with open(summary_path_out, "w", encoding="utf-8") as f:
        json.dump(page_summary, f, ensure_ascii=False, indent=2)

    suspicious_pages = [x["page_num"] for x in page_summary if x.get("suspicious")]
    print(f"[DONE] Suspicious pages: {suspicious_pages}")
    print(f"[DONE] page_summary.json -> {summary_path_out}")
    print(f"[DONE] suspicious_regions.json -> {suspicious_path_out}")

    return {
        "pdf_pages": pdf_pages,
        "ocr_pages": ocr_pages,
        "matches": matches,
        "suspicious_regions": suspicious_regions,
        "page_summary": page_summary,
        "output_dir": str(work_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Align PDF native bbox regions with OCR bbox regions to detect PDF-only suspicious text.")
    parser.add_argument("pdf_path", type=str, help="Path to the input PDF")
    parser.add_argument("--work-dir", type=str, default="output_bbox_align", help="Output directory")
    parser.add_argument("--dpi", type=int, default=200, help="Render DPI")
    parser.add_argument("--pdf-granularity", type=str, default="line", choices=["line", "word", "span"], help="PDF extraction granularity")
    parser.add_argument("--batch-size", type=int, default=8, help="Surya batch size")
    parser.add_argument("--geom-threshold", type=float, default=0.18, help="Geometry overlap threshold")
    parser.add_argument("--text-threshold", type=float, default=0.25, help="Text similarity threshold for weak geometric matches")
    parser.add_argument("--min-text-len", type=int, default=6, help="Minimum PDF region text length to consider suspicious")
    parser.add_argument("--keep-formula", action="store_true", help="Do not ignore formula-like PDF-only regions")
    return parser.parse_args()


if __name__ == "__main__":
    # 建议在运行前设置：
    # os.environ["TORCH_DEVICE"] = "cuda"
    args = parse_args()
    if not Path(args.pdf_path).exists():
        raise FileNotFoundError(f"PDF not found: {args.pdf_path}")

    run_pdf_implicit_injection_check_bbox(
        pdf_path=args.pdf_path,
        work_dir=args.work_dir,
        dpi=args.dpi,
        pdf_granularity=args.pdf_granularity,
        batch_size=args.batch_size,
        geom_threshold=args.geom_threshold,
        text_threshold=args.text_threshold,
        min_text_len=args.min_text_len,
        ignore_formula_regions=not args.keep_formula,
    )
