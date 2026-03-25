from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import io
import re
import unicodedata
from difflib import SequenceMatcher

import fitz  # PyMuPDF
from PIL import Image
from pypdf import PdfReader
from rapidfuzz import fuzz

try:
    from pylatexenc.latex2text import LatexNodes2Text
    HAS_PYLATEXENC = True
except Exception:
    LatexNodes2Text = None
    HAS_PYLATEXENC = False


# =========================
# Surya predictor 懒加载
# =========================
_SURYA_PREDICTORS: Optional[Tuple[object, object]] = None


def get_surya_predictors():
    """
    懒加载 Surya predictors，避免重复初始化。
    注意：如果你想在 run 文件中设置 TORCH_DEVICE，
    最好在 import 本工具文件之前设置环境变量。
    """
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


# =========================
# PDF 拆页渲染
# =========================
def render_pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 200) -> List[Dict]:
    """
    将 PDF 按页渲染成图片，并保存到 output_dir。
    返回每页的基础信息。
    """
    pdf_path = str(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    results = []

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    try:
        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            pix = page.get_pixmap(matrix=matrix, alpha=False)

            image_path = output_dir / f"page_{page_idx + 1:04d}.png"
            pix.save(str(image_path))

            results.append({
                "page_num": page_idx + 1,
                "image_path": str(image_path),
                "width": pix.width,
                "height": pix.height,
            })
    finally:
        doc.close()

    return results


# =========================
# PyPDF 文件流逐页解析
# =========================
def extract_pdf_text_by_page(pdf_path: str) -> List[Dict]:
    """
    使用 PyPDF 从 PDF 文件流中逐页提取文本。
    返回格式：
    [
        {"page_num": 1, "text": "..."},
        {"page_num": 2, "text": "..."},
        ...
    ]
    """
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_results = []

    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            text = ""
            print(f"[WARN] Failed to extract text from page {i + 1}: {e}")

        page_results.append({
            "page_num": i + 1,
            "text": text
        })

    return page_results


# =========================
# OCR bbox 重排辅助函数
# =========================
MATH_SYMBOL_PATTERN = re.compile(r"[=+\-*/^_∑∫√γαλβπ≤≥→←|\[\]{}()]")
LATIN_WORD_PATTERN = re.compile(r"[A-Za-z]{2,}")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0

    values = sorted(float(v) for v in values)
    if len(values) == 1:
        return values[0]

    q = min(max(q, 0.0), 1.0)
    pos = q * (len(values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    frac = pos - lo
    return values[lo] * (1.0 - frac) + values[hi] * frac


def normalize_bbox(bbox: Any) -> Optional[List[float]]:
    """
    将不同风格的 bbox 统一为 [x1, y1, x2, y2]。

    兼容：
    - [x1, y1, x2, y2]
    - [[x, y], ...] polygon
    - {"x1":..., "y1":..., "x2":..., "y2":...}
    - 具有 bbox / polygon / x1,y1,x2,y2 属性的对象
    """
    if bbox is None:
        return None

    if hasattr(bbox, "bbox"):
        nested = getattr(bbox, "bbox")
        if nested is not bbox:
            return normalize_bbox(nested)

    if hasattr(bbox, "polygon"):
        nested = getattr(bbox, "polygon")
        if nested is not bbox:
            return normalize_bbox(nested)

    if isinstance(bbox, dict):
        keys = {str(k).lower(): v for k, v in bbox.items()}
        if {"x1", "y1", "x2", "y2"}.issubset(keys):
            return [
                float(keys["x1"]),
                float(keys["y1"]),
                float(keys["x2"]),
                float(keys["y2"]),
            ]
        if "points" in keys:
            return normalize_bbox(keys["points"])

    if all(hasattr(bbox, attr) for attr in ("x1", "y1", "x2", "y2")):
        return [
            float(getattr(bbox, "x1")),
            float(getattr(bbox, "y1")),
            float(getattr(bbox, "x2")),
            float(getattr(bbox, "y2")),
        ]

    if isinstance(bbox, (list, tuple)):
        if len(bbox) == 4 and all(_is_number(v) for v in bbox):
            return [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]

        if len(bbox) >= 4 and all(isinstance(pt, (list, tuple)) and len(pt) >= 2 for pt in bbox):
            xs = [float(pt[0]) for pt in bbox]
            ys = [float(pt[1]) for pt in bbox]
            return [min(xs), min(ys), max(xs), max(ys)]

    return None


def _enrich_line_record(line: Dict[str, Any], original_idx: int) -> Dict[str, Any]:
    text = (line.get("text") or "").strip()
    bbox = normalize_bbox(line.get("bbox"))

    record = {
        "text": text,
        "bbox": bbox,
        "original_idx": original_idx,
    }

    if bbox is None:
        record.update({
            "x1": 0.0,
            "y1": float(original_idx),
            "x2": 0.0,
            "y2": float(original_idx),
            "cx": 0.0,
            "cy": float(original_idx),
            "w": 0.0,
            "h": 0.0,
        })
    else:
        x1, y1, x2, y2 = bbox
        record.update({
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "cx": (x1 + x2) / 2.0,
            "cy": (y1 + y2) / 2.0,
            "w": max(0.0, x2 - x1),
            "h": max(0.0, y2 - y1),
        })

    return record


def _estimate_page_width(lines: List[Dict[str, Any]]) -> float:
    valid_x2 = [line["x2"] for line in lines if line.get("bbox") is not None]
    return max(valid_x2) if valid_x2 else 0.0


def _detect_two_column_layout(lines: List[Dict[str, Any]], page_width: float) -> Dict[str, Any]:
    valid_lines = [
        line for line in lines
        if line.get("bbox") is not None and str(line.get("text", "")).strip()
    ]

    if page_width <= 0 or len(valid_lines) < 6:
        return {
            "is_two_column": False,
            "split_x": page_width / 2.0 if page_width else 0.0,
            "gutter": 0.0,
            "left_count": 0,
            "right_count": 0,
        }

    # 估计页面高度（不改函数签名的前提下）
    page_bottom = max(line["y2"] for line in valid_lines)
    # 只优先看页面上半部分/上 45%，避免下半部分公式区干扰双栏检测
    top_limit = page_bottom * 0.45

    top_lines = [
        line for line in valid_lines
        if line["y1"] <= top_limit
    ]
    base_pool = top_lines if len(top_lines) >= 6 else valid_lines

    # 过滤过宽行，避免通栏大块/异常块影响判断
    base_lines = [
        line for line in base_pool
        if page_width > 0 and (line["w"] / page_width) <= 0.72
    ]
    if len(base_lines) < 6:
        base_lines = base_pool

    split_x = page_width / 2.0
    center_band = max(18.0, page_width * 0.015)  # 中线附近保留带，避免模糊块误入左右栏

    left_candidates = [
        line for line in base_lines
        if line["x2"] <= (split_x - center_band) or line["cx"] < (split_x - center_band * 0.5)
    ]
    right_candidates = [
        line for line in base_lines
        if line["x1"] >= (split_x + center_band) or line["cx"] > (split_x + center_band * 0.5)
    ]

    bucket_ratio = (len(left_candidates) + len(right_candidates)) / max(1, len(base_lines))

    # 比原来更宽松：双栏页里左右各至少有 3 个框，且大部分框都能被解释到左右两侧
    if len(left_candidates) < 3 or len(right_candidates) < 3 or bucket_ratio < 0.50:
        return {
            "is_two_column": False,
            "split_x": split_x,
            "gutter": 0.0,
            "left_count": len(left_candidates),
            "right_count": len(right_candidates),
        }

    left_edge = _percentile([line["x2"] for line in left_candidates], 0.80)
    right_edge = _percentile([line["x1"] for line in right_candidates], 0.20)
    gutter = right_edge - left_edge

    # 增加一个“中心分离度”兜底，不再只靠 gutter 一票否决
    left_cx = _percentile([line["cx"] for line in left_candidates], 0.50)
    right_cx = _percentile([line["cx"] for line in right_candidates], 0.50)
    center_sep = right_cx - left_cx

    # 判双栏条件：
    # 1) gutter 达到较宽松阈值；或
    # 2) 左右两侧数量都比较充足，且中心明显分离
    gutter_ok = gutter >= page_width * 0.015
    separation_ok = (
        len(left_candidates) >= 4 and
        len(right_candidates) >= 4 and
        center_sep >= page_width * 0.22
    )

    if not (gutter_ok or separation_ok):
        return {
            "is_two_column": False,
            "split_x": split_x,
            "gutter": gutter,
            "left_count": len(left_candidates),
            "right_count": len(right_candidates),
        }

    return {
        "is_two_column": True,
        "split_x": (left_edge + right_edge) / 2.0,
        "gutter": gutter,
        "left_count": len(left_candidates),
        "right_count": len(right_candidates),
    }


def _assign_column_labels(
    lines: List[Dict[str, Any]],
    page_width: float,
    layout_info: Dict[str, Any],
) -> List[Dict[str, Any]]:
    is_two_column = layout_info.get("is_two_column", False)
    split_x = layout_info.get("split_x", page_width / 2.0)
    gutter = layout_info.get("gutter", 0.0)

    # 比原来更稳一点，不完全跟 gutter 绑死
    margin = max(8.0, page_width * 0.012, gutter * 0.25)

    for line in lines:
        if line.get("bbox") is None:
            line["col"] = "single"
            continue

        if not is_two_column:
            line["col"] = "single"
            continue

        width_ratio = (line["w"] / page_width) if page_width > 0 else 0.0

        # 只有真正大跨度的块才算 full，避免左栏标题/长正文被误伤
        crosses_center = line["x1"] < (split_x - margin) and line["x2"] > (split_x + margin)

        if width_ratio >= 0.78 or (crosses_center and width_ratio >= 0.68):
            line["col"] = "full"
        elif line["cx"] <= split_x:
            line["col"] = "left"
        else:
            line["col"] = "right"

    return lines


def _is_equation_like(text: str) -> bool:
    if not text:
        return False

    text = text.strip()
    math_symbol_count = len(MATH_SYMBOL_PATTERN.findall(text))
    latin_word_count = len(LATIN_WORD_PATTERN.findall(text))

    if text.startswith("="):
        return True
    if "∑" in text or "∫" in text or r"\sum" in text or r"\int" in text:
        return True
    if math_symbol_count >= 4 and latin_word_count <= 8:
        return True
    if len(text) < 100 and math_symbol_count >= 3 and latin_word_count <= 5:
        return True

    return False


def _horizontal_overlap_ratio(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    overlap = max(0.0, min(a["x2"], b["x2"]) - max(a["x1"], b["x1"]))
    base = max(1.0, min(max(a["w"], 1.0), max(b["w"], 1.0)))
    return overlap / base


def _finalize_block(block: Dict[str, Any]) -> Dict[str, Any]:
    lines = sorted(block["lines"], key=lambda x: (x["y1"], x["x1"], x["original_idx"]))

    x1 = min(line["x1"] for line in lines)
    y1 = min(line["y1"] for line in lines)
    x2 = max(line["x2"] for line in lines)
    y2 = max(line["y2"] for line in lines)

    text = "\n".join(line["text"] for line in lines if line["text"])

    return {
        "type": block["type"],
        "col": block["col"],
        "bbox": [x1, y1, x2, y2],
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "cx": (x1 + x2) / 2.0,
        "cy": (y1 + y2) / 2.0,
        "w": max(0.0, x2 - x1),
        "h": max(0.0, y2 - y1),
        "text": text,
        "lines": [
            {"text": line["text"], "bbox": line["bbox"], "col": line["col"]}
            for line in lines
        ],
    }


def _merge_lines_to_blocks(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not lines:
        return []

    sorted_lines = sorted(lines, key=lambda x: (x["y1"], x["x1"], x["original_idx"]))
    blocks = []

    first_line = sorted_lines[0]
    current_block = {
        "type": "equation" if _is_equation_like(first_line["text"]) else "text",
        "col": first_line["col"],
        "lines": [first_line],
    }

    for line in sorted_lines[1:]:
        prev_line = current_block["lines"][-1]
        line_type = "equation" if _is_equation_like(line["text"]) else "text"
        gap = line["y1"] - prev_line["y2"]
        height_ref = max(prev_line["h"], line["h"], 1.0)
        x_diff = abs(prev_line["x1"] - line["x1"])
        overlap_ratio = _horizontal_overlap_ratio(prev_line, line)

        if current_block["type"] == "equation" and line_type == "equation":
            can_merge = (
                line["col"] == current_block["col"]
                and gap <= height_ref * 1.6
                and (x_diff <= height_ref * 6.0 or overlap_ratio >= 0.20)
            )
        else:
            can_merge = (
                line["col"] == current_block["col"]
                and line_type == current_block["type"]
                and gap <= height_ref * 1.25
                and (x_diff <= height_ref * 2.5 or overlap_ratio >= 0.40)
            )

        if can_merge:
            current_block["lines"].append(line)
        else:
            blocks.append(_finalize_block(current_block))
            current_block = {
                "type": line_type,
                "col": line["col"],
                "lines": [line],
            }

    blocks.append(_finalize_block(current_block))
    return blocks


def _order_blocks_in_stripe(blocks: List[Dict[str, Any]], is_two_column: bool) -> List[Dict[str, Any]]:
    if not blocks:
        return []

    if not is_two_column:
        return sorted(blocks, key=lambda x: (x["y1"], x["x1"]))

    left_like = sorted(
        [block for block in blocks if block["col"] in ("left", "single")],
        key=lambda x: (x["y1"], x["x1"]),
    )
    right_like = sorted(
        [block for block in blocks if block["col"] == "right"],
        key=lambda x: (x["y1"], x["x1"]),
    )
    return left_like + right_like


def _reorder_blocks_by_reading_order(
    blocks: List[Dict[str, Any]],
    is_two_column: bool,
) -> List[Dict[str, Any]]:
    if not blocks:
        return []

    if not is_two_column:
        return sorted(blocks, key=lambda x: (x["y1"], x["x1"]))

    full_blocks = sorted(
        [block for block in blocks if block["col"] == "full"],
        key=lambda x: (x["y1"], x["x1"]),
    )
    normal_blocks = [block for block in blocks if block["col"] != "full"]

    if not full_blocks:
        return _order_blocks_in_stripe(normal_blocks, is_two_column=True)

    ordered = []
    remaining = normal_blocks[:]

    for full_block in full_blocks:
        stripe_blocks = [block for block in remaining if block["cy"] < full_block["y1"]]
        remaining = [block for block in remaining if block not in stripe_blocks]
        ordered.extend(_order_blocks_in_stripe(stripe_blocks, is_two_column=True))
        ordered.append(full_block)

    ordered.extend(_order_blocks_in_stripe(remaining, is_two_column=True))
    return ordered


def _blocks_to_text(blocks: List[Dict[str, Any]]) -> str:
    parts = [block["text"].strip() for block in blocks if block.get("text", "").strip()]
    return "\n\n".join(parts)


def reorder_ocr_lines_by_bbox(
    ocr_lines: List[Dict[str, Any]],
    page_width: Optional[float] = None,
    page_height: Optional[float] = None,
) -> Dict[str, Any]:
    """
    基于 bbox 对 OCR 行结果做重排，适配双栏论文、长公式块等场景。

    返回：
    {
        "ocr_text": "...",              # bbox 重排后的整页文本
        "ocr_lines": [...],              # 重排后的行顺序
        "ocr_blocks": [...],             # block 级结构
        "layout": {...}                  # 双栏检测信息
    }
    """
    enriched_lines = [
        _enrich_line_record(line, idx)
        for idx, line in enumerate(ocr_lines)
        if (line.get("text") or "").strip()
    ]

    if not enriched_lines:
        return {
            "ocr_text": "",
            "ocr_lines": [],
            "ocr_blocks": [],
            "layout": {
                "page_width": page_width or 0.0,
                "page_height": page_height or 0.0,
                "is_two_column": False,
                "split_x": 0.0,
                "gutter": 0.0,
            },
        }

    effective_page_width = float(page_width) if page_width else _estimate_page_width(enriched_lines)
    layout_info = _detect_two_column_layout(enriched_lines, effective_page_width)
    layout_info.update({
        "page_width": effective_page_width,
        "page_height": float(page_height) if page_height else 0.0,
    })

    _assign_column_labels(enriched_lines, effective_page_width, layout_info)

    blocks = []
    for col_name in ("single", "full", "left", "right"):
        col_lines = [line for line in enriched_lines if line["col"] == col_name]
        blocks.extend(_merge_lines_to_blocks(col_lines))

    ordered_blocks = _reorder_blocks_by_reading_order(
        blocks,
        is_two_column=layout_info.get("is_two_column", False),
    )

    ordered_lines = []
    for block_idx, block in enumerate(ordered_blocks):
        for line_idx, line in enumerate(block.get("lines", [])):
            ordered_lines.append({
                "text": line.get("text", ""),
                "bbox": normalize_bbox(line.get("bbox")),
                "col": block.get("col"),
                "block_type": block.get("type"),
                "block_order": block_idx,
                "line_order_in_block": line_idx,
            })

    exported_blocks = []
    for order_idx, block in enumerate(ordered_blocks):
        exported_blocks.append({
            "order": order_idx,
            "type": block.get("type"),
            "col": block.get("col"),
            "bbox": normalize_bbox(block.get("bbox")),
            "text": block.get("text", ""),
            "lines": block.get("lines", []),
        })

    return {
        "ocr_text": _blocks_to_text(exported_blocks),
        "ocr_lines": ordered_lines,
        "ocr_blocks": exported_blocks,
        "layout": layout_info,
    }


# =========================
# Surya 逐页 OCR
# =========================
def ocr_images_with_surya(
    image_infos: List[Dict],
    batch_size: int = 8,
    reorder_by_bbox: bool = True,
) -> List[Dict]:
    """
    对 render_pdf_to_images 生成的图片逐页 OCR。

    当 reorder_by_bbox=True 时：
    - 保留 Surya 原始行顺序：ocr_text_raw_order / ocr_lines_raw
    - 额外输出 bbox 重排后的文本：ocr_text / ocr_lines / ocr_blocks / ocr_layout
    """
    recognition_predictor, detection_predictor = get_surya_predictors()
    results = []

    for start in range(0, len(image_infos), batch_size):
        batch_infos = image_infos[start:start + batch_size]
        images = []

        try:
            for item in batch_infos:
                with Image.open(item["image_path"]) as im:
                    images.append(im.convert("RGB"))

            predictions = recognition_predictor(images, det_predictor=detection_predictor)

            for item, pred in zip(batch_infos, predictions):
                raw_text_lines = []
                raw_full_text_lines = []

                pred_lines = getattr(pred, "text_lines", []) or []

                for line in pred_lines:
                    line_text = getattr(line, "text", "") or ""
                    line_bbox = normalize_bbox(getattr(line, "bbox", None))

                    raw_text_lines.append({
                        "text": line_text,
                        "bbox": line_bbox,
                    })
                    raw_full_text_lines.append(line_text)

                raw_ocr_text = "\n".join(raw_full_text_lines)

                result_item = {
                    "page_num": item["page_num"],
                    "image_path": item["image_path"],
                    "ocr_text_raw_order": raw_ocr_text,
                    "ocr_lines_raw": raw_text_lines,
                }

                if reorder_by_bbox:
                    reordered = reorder_ocr_lines_by_bbox(
                        raw_text_lines,
                        page_width=item.get("width"),
                        page_height=item.get("height"),
                    )
                    result_item.update({
                        "ocr_text": reordered["ocr_text"],
                        "ocr_lines": reordered["ocr_lines"],
                        "ocr_blocks": reordered["ocr_blocks"],
                        "ocr_layout": reordered["layout"],
                    })
                else:
                    result_item.update({
                        "ocr_text": raw_ocr_text,
                        "ocr_lines": raw_text_lines,
                        "ocr_blocks": [],
                        "ocr_layout": {
                            "page_width": float(item.get("width", 0) or 0),
                            "page_height": float(item.get("height", 0) or 0),
                            "is_two_column": False,
                            "split_x": 0.0,
                            "gutter": 0.0,
                        },
                    })

                results.append(result_item)
        finally:
            for img in images:
                try:
                    img.close()
                except Exception:
                    pass

    return results


# =========================
# 文本归一化
# 核心思路：
# 1) OCR 侧：先去 markup（保留边界）→ 再用 pylatexenc 把 LaTeX 转成普通文本/Unicode
# 2) PDF / OCR 两侧：统一走 Unicode 类归一化和少量规则化
# 3) 大映射表仅作为 fallback，不做主方案
# =========================
STYLE_COMMANDS = [
    "mathcal", "mathbf", "mathrm", "mathit", "mathbb",
    "mathsf", "mathtt", "mathscr", "boldsymbol", "bm"
]

# 这里只保留一个“小型 fallback 表”，仅在没有 pylatexenc
# 或 pylatexenc 处理失败时兜底，不再把它作为主方案
LATEX_FALLBACK_SYMBOL_MAP = {
    r"\Delta": "Δ",
    r"\delta": "δ",
    r"\varepsilon": "ε",
    r"\epsilon": "ϵ",
    r"\theta": "θ",
    r"\alpha": "α",
    r"\beta": "β",
    r"\lambda": "λ",
    r"\mu": "μ",
    r"\pi": "π",
    r"\sigma": "σ",
    r"\phi": "φ",
    r"\le": "≤",
    r"\ge": "≥",
    r"\neq": "≠",
    r"\approx": "≈",
    r"\times": "×",
    r"\cdot": "·",
    r"\pm": "±",
    r"\infty": "∞",
    r"\sum": "∑",
    r"\prod": "∏",
    r"\rightarrow": "→",
    r"\to": "→",
    r"\leftarrow": "←",
    r"\Rightarrow": "⇒",
    r"\Leftarrow": "⇐",
}

COMMON_CHAR_REPLACEMENTS = {
    "\u00ad": "",   # soft hyphen
    "\xa0": " ",    # no-break space
    "\u200b": "",   # zero width
    "\u200c": "",
    "\u200d": "",
    "\ufeff": "",
}

CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
MULTISPACE_PATTERN = re.compile(r"\s+")


def strip_ocr_markup_preserve_spacing(text: str) -> str:
    """
    去 OCR 输出中的 markup，但保留边界为空格，
    避免 </math> 后面的单词直接粘到前一个公式后面。
    """
    if not text:
        return ""

    text = re.sub(r"</?math>", " ", text)
    text = re.sub(r"</?(b|i|em|strong|span|sub|sup)>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def strip_latex_style_commands(text: str) -> str:
    """
    fallback 用：
    去掉纯样式类命令，仅保留内容本身。
    例如：
    \mathcal{A} -> A
    \mathbf{V} -> V
    """
    prev = None
    while prev != text:
        prev = text
        for cmd in STYLE_COMMANDS:
            text = re.sub(rf"\\{cmd}\s*\{{([^{{}}]+)\}}", r"\1", text)
    return text


def fallback_latex_to_text(text: str) -> str:
    """
    当 pylatexenc 不可用，或解析失败时的轻量兜底方案。
    """
    if not text:
        return ""

    text = strip_latex_style_commands(text)

    for k, v in LATEX_FALLBACK_SYMBOL_MAP.items():
        text = text.replace(k, v)

    # \foo{bar} -> bar
    text = re.sub(r"\\[a-zA-Z]+\*?\s*\{([^{}]*)\}", r"\1", text)

    # 剩余未知命令删掉命令名
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)

    # 去残余大括号
    text = text.replace("{", " ").replace("}", " ")

    return text


def latex_to_visual_text(text: str) -> str:
    """
    优先用 pylatexenc 把 LaTeX 结构化表示还原成普通文本/Unicode。
    """
    if not text or "\\" not in text:
        return text

    if HAS_PYLATEXENC:
        try:
            return LatexNodes2Text().latex_to_text(text)
        except Exception:
            return fallback_latex_to_text(text)

    return fallback_latex_to_text(text)


def normalize_unicode_classes(text: str) -> str:
    """
    两侧统一使用的规范化：
    - Unicode NFKC
    - 隐形/控制字符清洗
    - dash/prime/star 等类别字符统一
    - 常见运算符周围空白统一
    """
    if not text:
        return ""

    for src, tgt in COMMON_CHAR_REPLACEMENTS.items():
        text = text.replace(src, tgt)

    text = CONTROL_CHAR_PATTERN.sub("", text)
    text = unicodedata.normalize("NFKC", text)

    # 按“类别”而不是按单个符号硬编码
    dash_chars = {"−", "–", "—", "‐", "-"}
    prime_chars = {"′", "’", "`", "´"}
    star_chars = {"∗", "⋆", "✶"}
    bar_pairs = {"∥"}

    for ch in dash_chars:
        text = text.replace(ch, "-")
    for ch in prime_chars:
        text = text.replace(ch, "'")
    for ch in star_chars:
        text = text.replace(ch, "*")
    for ch in bar_pairs:
        text = text.replace(ch, "||")

    # 常见运算符空格统一
    operator_rules = [
        (r"\s*:=\s*", " := "),
        (r"\s*\|\|\s*", " || "),
        (r"\s*<=\s*", " <= "),
        (r"\s*>=\s*", " >= "),
        (r"\s*!=\s*", " != "),
        (r"\s*==\s*", " == "),
        (r"\s*≤\s*", " ≤ "),
        (r"\s*≥\s*", " ≥ "),
        (r"\s*=\s*", " = "),
        (r"\s*-\s*", " - "),
        (r"\s*\*\s*", " * "),
    ]
    for pattern, repl in operator_rules:
        text = re.sub(pattern, repl, text)

    # 常见标点和括号空格统一
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*;\s*", "; ", text)
    text = re.sub(r"\s+([.?!])", r"\1", text)
    text = re.sub(r"([\(\[\{])\s+", r"\1", text)
    text = re.sub(r"\s+([\)\]\}])", r"\1", text)

    text = MULTISPACE_PATTERN.sub(" ", text).strip()
    return text


def normalize_stream_text(text: str) -> str:
    """
    PDF 文件流文本：走 Unicode/类别级规范化。
    """
    return normalize_unicode_classes(text)


def normalize_ocr_formula_text(text: str) -> str:
    """
    OCR 文本：
    先去 markup（保留边界）→ 再把 LaTeX 转成文本/Unicode → 再做统一规范化。
    """
    if not text:
        return ""

    text = strip_ocr_markup_preserve_spacing(text)
    text = latex_to_visual_text(text)
    text = normalize_unicode_classes(text)
    return text


# =========================
# 比较函数
# =========================
MATH_KEYWORD_PATTERN = re.compile(
    r"(max|min|argmax|argmin|E\(|P\(|s\.t\.|iff|sup|inf|lim)"
)
FORMULA_TAG_PATTERN = re.compile(r"</?math[^>]*>", re.IGNORECASE)


def similarity(a: str, b: str) -> float:
    return fuzz.ratio(a, b) / 100.0


def _normalize_for_compare(text: str, is_ocr: bool) -> str:
    return normalize_ocr_formula_text(text) if is_ocr else normalize_stream_text(text)


def _split_compare_segments(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []

    parts = re.split(r"(?:\n+|(?<=[。；;.!?])\s+)", text)
    parts = [part.strip() for part in parts if part and part.strip()]

    if len(parts) <= 1:
        parts = re.split(r"\s{2,}", text)
        parts = [part.strip() for part in parts if part and part.strip()]

    return parts or [text]


def _is_formula_like_segment(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False

    if FORMULA_TAG_PATTERN.search(text):
        return True

    math_kw = len(MATH_KEYWORD_PATTERN.findall(text))
    math_sym = len(MATH_SYMBOL_PATTERN.findall(text))
    latin_word_count = len(LATIN_WORD_PATTERN.findall(text))
    alpha_ratio = sum(ch.isalpha() for ch in text) / max(1, len(text))

    if math_kw >= 1 and math_sym >= 2:
        return True
    if text.startswith("="):
        return True
    if math_sym >= 6 and latin_word_count <= 12:
        return True
    if alpha_ratio < 0.55 and math_sym >= 5:
        return True

    return False


def _mask_formula_like_segments(text: str, mask_token: str = "<FORMULA>") -> str:
    parts = _split_compare_segments(text)
    if not parts:
        return ""

    masked_parts = []
    prev_masked = False

    for part in parts:
        is_formula = _is_formula_like_segment(part)
        if is_formula:
            if not prev_masked:
                masked_parts.append(mask_token)
            prev_masked = True
        else:
            masked_parts.append(part)
            prev_masked = False

    return " ".join(masked_parts)


def _mask_ocr_blocks_for_relaxed_compare(
    ocr_item: Dict[str, Any],
    fallback_text: str,
    mask_token: str = "<FORMULA>",
) -> str:
    blocks = ocr_item.get("ocr_blocks") or []
    if not blocks:
        return _mask_formula_like_segments(fallback_text, mask_token=mask_token)

    parts = []
    prev_masked = False

    for block in blocks:
        block_type = str(block.get("type", "")).strip().lower()
        block_text = _normalize_for_compare(block.get("text", ""), is_ocr=True)
        if not block_text:
            continue

        is_formula = block_type == "equation" or _is_formula_like_segment(block_text)
        if is_formula:
            if not prev_masked:
                parts.append(mask_token)
            prev_masked = True
        else:
            parts.append(block_text)
            prev_masked = False

    return " ".join(parts) if parts else _mask_formula_like_segments(fallback_text, mask_token=mask_token)


def get_pdf_only_segments(pdf_text: str, ocr_text: str, min_len: int = 8) -> List[str]:
    matcher = SequenceMatcher(None, pdf_text, ocr_text)
    segments = []

    for tag, i1, i2, _, _ in matcher.get_opcodes():
        if tag in ("delete", "replace"):
            segment = pdf_text[i1:i2].strip()
            if len(segment) >= min_len:
                segments.append(segment)

    return segments


def _filter_non_formula_segments(segments: List[str]) -> List[str]:
    return [segment for segment in segments if not _is_formula_like_segment(segment)]


def compare_page_texts(
    pdf_page_texts: List[Dict],
    ocr_page_texts: List[Dict],
    ocr_text_key: str = "ocr_text",
    suspicious_ratio_threshold: float = 0.95,
    relaxed_ratio_threshold: float = 0.90,
    min_segment_len: int = 8,
) -> List[Dict]:
    """
    逐页比较，保留两套分数：
    - similarity_full: 全文对比
    - similarity_relaxed: 弱化公式后的对比（更适合主判定）
    """
    ocr_map = {item["page_num"]: item for item in ocr_page_texts}
    results = []

    for pdf_item in pdf_page_texts:
        page_num = pdf_item["page_num"]
        pdf_text_raw = pdf_item.get("text", "")
        ocr_item = ocr_map.get(page_num, {})
        ocr_text_raw = ocr_item.get(ocr_text_key, "")

        pdf_text = _normalize_for_compare(pdf_text_raw, is_ocr=False)
        ocr_text = _normalize_for_compare(ocr_text_raw, is_ocr=True)

        similarity_full = similarity(pdf_text, ocr_text)

        pdf_text_relaxed = _mask_formula_like_segments(pdf_text)
        ocr_text_relaxed = _mask_ocr_blocks_for_relaxed_compare(ocr_item, fallback_text=ocr_text)

        similarity_relaxed = similarity(pdf_text_relaxed, ocr_text_relaxed)

        pdf_only_segments = get_pdf_only_segments(pdf_text, ocr_text, min_len=min_segment_len)
        pdf_only_segments_non_formula = _filter_non_formula_segments(pdf_only_segments)

        suspicious = bool(
            pdf_text_relaxed
            and similarity_relaxed < relaxed_ratio_threshold
            and pdf_only_segments_non_formula
        )

        results.append({
            "page_num": page_num,
            "pdf_text_raw": pdf_text_raw,
            "ocr_text_raw": ocr_text_raw,
            "pdf_text": pdf_text,
            "ocr_text": ocr_text,
            "pdf_text_relaxed": pdf_text_relaxed,
            "ocr_text_relaxed": ocr_text_relaxed,
            "similarity": similarity_full,
            "similarity_full": similarity_full,
            "similarity_relaxed": similarity_relaxed,
            "pdf_only_segments": pdf_only_segments,
            "pdf_only_segments_non_formula": pdf_only_segments_non_formula,
            "suspicious": suspicious,
            "suspicious_by_full_similarity": bool(
                pdf_text and similarity_full < suspicious_ratio_threshold and pdf_only_segments
            ),
        })

    return results

