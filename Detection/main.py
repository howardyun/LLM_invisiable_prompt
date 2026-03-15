from difflib import SequenceMatcher
from typing import List, Dict
from Detection.utils import normalize_text, render_pdf_to_images, extract_pdf_text_by_page, ocr_images_with_surya
import json
from pathlib import Path

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def get_pdf_only_segments(pdf_text: str, ocr_text: str, min_len: int = 8) -> List[str]:
    """
    提取“更偏向只出现在 PDF 解析文本中”的差异片段。
    这是一个粗粒度实现，后续你可以升级成 token 级或 n-gram 级。
    """
    matcher = SequenceMatcher(None, pdf_text, ocr_text)
    suspicious_segments = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("delete", "replace"):
            seg = pdf_text[i1:i2].strip()
            if len(seg) >= min_len:
                suspicious_segments.append(seg)

    return suspicious_segments


def compare_page_texts(
    pdf_page_texts: List[Dict],
    ocr_page_texts: List[Dict],
    suspicious_ratio_threshold: float = 0.75,
    min_segment_len: int = 8
) -> List[Dict]:
    """
    对齐页号后逐页比较 PyPDF 文本与 OCR 文本。
    """
    ocr_map = {item["page_num"]: item for item in ocr_page_texts}
    results = []

    for pdf_item in pdf_page_texts:
        page_num = pdf_item["page_num"]
        pdf_text_raw = pdf_item["text"]
        ocr_item = ocr_map.get(page_num, {})

        ocr_text_raw = ocr_item.get("ocr_text", "")

        pdf_text = normalize_text(pdf_text_raw)
        ocr_text = normalize_text(ocr_text_raw)

        sim = similarity(pdf_text, ocr_text)
        pdf_only_segments = get_pdf_only_segments(pdf_text, ocr_text, min_len=min_segment_len)

        suspicious = False
        if pdf_text and sim < suspicious_ratio_threshold and len(pdf_only_segments) > 0:
            suspicious = True

        results.append({
            "page_num": page_num,
            "pdf_text": pdf_text,
            "ocr_text": ocr_text,
            "similarity": sim,
            "pdf_only_segments": pdf_only_segments,
            "suspicious": suspicious,
        })

    return results

# 主流程整合
def run_pdf_implicit_injection_check(pdf_path: str, work_dir: str = "pdf_check_output"):
    work_dir = Path(work_dir)
    image_dir = work_dir / "images"
    work_dir.mkdir(parents=True, exist_ok=True)

    print("[1] Rendering PDF pages to images...")
    image_infos = render_pdf_to_images(pdf_path, image_dir, dpi=200)

    print("[2] Extracting PDF text by page with PyPDF...")
    pdf_page_texts = extract_pdf_text_by_page(pdf_path)

    print("[3] Running OCR with Surya...")
    ocr_page_texts = ocr_images_with_surya(image_infos)

    print("[4] Comparing page-level OCR text vs PDF parsed text...")
    compare_results = compare_page_texts(pdf_page_texts, ocr_page_texts)

    output_path = work_dir / "comparison_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(compare_results, f, ensure_ascii=False, indent=2)

    print(f"[DONE] Comparison results saved to: {output_path}")

    suspicious_pages = [r for r in compare_results if r["suspicious"]]
    print(f"[INFO] Suspicious pages: {[r['page_num'] for r in suspicious_pages]}")

    return compare_results


if __name__ == "__main__":


    pdf_path = "text_version.pdf"
    results = run_pdf_implicit_injection_check(pdf_path)

