import os
from pathlib import Path
from typing import List, Dict
import fitz  # PyMuPDF
from PIL import Image
import io
from typing import List, Dict
from pypdf import PdfReader
from PIL import Image
from typing import List, Dict

from surya.foundation import FoundationPredictor
from surya.recognition import RecognitionPredictor
from surya.detection import DetectionPredictor





# PDF 拆分成逐页图片
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

    doc.close()
    return results

# PyPDF 文件流解析函数
def extract_pdf_text_by_page(pdf_path: str) -> List[Dict]:
    """
    使用 PyPDF 从 PDF 文件流中逐页提取文本。
    返回:
    [
        {"page_num": 1, "text": "..."},
        {"page_num": 2, "text": "..."},
        ...
    ]
    """
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    stream = io.BytesIO(pdf_bytes)
    reader = PdfReader(stream)

    page_results = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            text = f""
            print(f"[WARN] Failed to extract text from page {i + 1}: {e}")

        page_results.append({
            "page_num": i + 1,
            "text": text
        })

    return page_results

# Surya 逐页 OCR
def init_surya_predictors():
    foundation_predictor = FoundationPredictor()
    recognition_predictor = RecognitionPredictor(foundation_predictor)
    detection_predictor = DetectionPredictor()
    return recognition_predictor, detection_predictor

def ocr_images_with_surya(image_infos: List[Dict]) -> List[Dict]:
    """
    对 render_pdf_to_images 生成的图片逐页 OCR。
    返回每页 OCR 文本和行级结果。
    """
    recognition_predictor, detection_predictor = init_surya_predictors()

    results = []
    images = [Image.open(item["image_path"]).convert("RGB") for item in image_infos]
    predictions = recognition_predictor(images, det_predictor=detection_predictor)

    for item, pred in zip(image_infos, predictions):
        text_lines = []
        full_text_lines = []

        for line in pred.text_lines:
            line_text = getattr(line, "text", "") or ""
            line_bbox = getattr(line, "bbox", None)

            text_lines.append({
                "text": line_text,
                "bbox": line_bbox
            })
            full_text_lines.append(line_text)

        results.append({
            "page_num": item["page_num"],
            "image_path": item["image_path"],
            "ocr_text": "\n".join(full_text_lines),
            "ocr_lines": text_lines
        })

    return results


# 文本归一化

import re
import unicodedata


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00ad", "")  # soft hyphen
    text = text.replace("\xa0", " ")   # no-break space
    text = re.sub(r"<[^>]+>", "", text)  # 去掉可能存在的 HTML 标签
    text = re.sub(r"\s+", " ", text).strip()
    return text