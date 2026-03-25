import os
import json
from pathlib import Path

import torch

# 一定尽量提前设置
os.environ["TORCH_DEVICE"] = "cuda"

from Detection.utils import (
    render_pdf_to_images,
    extract_pdf_text_by_page,
    ocr_images_with_surya,
    compare_page_texts,   # 直接用工具类里的新版 compare_page_texts
)

print("cuda available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))


def run_pdf_implicit_injection_check(
    pdf_path: str,
    work_dir: str = "pdf_check_output",
    dpi: int = 200,
    batch_size: int = 8,
    reorder_by_bbox: bool = True,
    save_raw_compare: bool = True,
):
    work_dir = Path(work_dir)
    image_dir = work_dir / "images"
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[PDF] {pdf_path}")
    print("[1] Rendering PDF pages to images...")
    image_infos = render_pdf_to_images(pdf_path, image_dir, dpi=dpi)

    print("[2] Extracting PDF text by page with PyPDF...")
    pdf_page_texts = extract_pdf_text_by_page(pdf_path)

    print("[3] Running OCR with Surya...")
    ocr_page_texts = ocr_images_with_surya(
        image_infos,
        batch_size=batch_size,
        reorder_by_bbox=reorder_by_bbox,
    )

    print("[4] Comparing page-level OCR text vs PDF parsed text...")
    compare_results = compare_page_texts(
        pdf_page_texts,
        ocr_page_texts,
        ocr_text_key="ocr_text",   # bbox 重排后的 OCR 文本
    )

    # 打印字段，确认你现在真的在走新版 compare_page_texts
    if compare_results:
        print("[DEBUG] comparison result keys:", list(compare_results[0].keys()))

    output_path = work_dir / "comparison_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(compare_results, f, ensure_ascii=False, indent=2)

    print(f"[DONE] Reordered comparison results saved to: {output_path}")

    suspicious_pages = [r for r in compare_results if r.get("suspicious", False)]
    print(f"[INFO] Suspicious pages (reordered OCR): {[r['page_num'] for r in suspicious_pages]}")

    compare_results_raw = None
    if save_raw_compare:
        print("[5] Comparing raw-order OCR text vs PDF parsed text...")
        compare_results_raw = compare_page_texts(
            pdf_page_texts,
            ocr_page_texts,
            ocr_text_key="ocr_text_raw_order",
        )

        raw_output_path = work_dir / "comparison_results_raw_order.json"
        with open(raw_output_path, "w", encoding="utf-8") as f:
            json.dump(compare_results_raw, f, ensure_ascii=False, indent=2)

        suspicious_pages_raw = [r for r in compare_results_raw if r.get("suspicious", False)]
        print(f"[DONE] Raw-order comparison results saved to: {raw_output_path}")
        print(f"[INFO] Suspicious pages (raw OCR): {[r['page_num'] for r in suspicious_pages_raw]}")

    ocr_dump_path = work_dir / "ocr_page_texts.json"
    with open(ocr_dump_path, "w", encoding="utf-8") as f:
        json.dump(ocr_page_texts, f, ensure_ascii=False, indent=2)

    print(f"[DONE] OCR structural results saved to: {ocr_dump_path}")

    return {
        "reordered_compare": compare_results,
        "raw_compare": compare_results_raw,
        "ocr_page_texts": ocr_page_texts,
    }


if __name__ == "__main__":
    pdf_path = Path("../testData/pdf-easy.pdf")

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 不存在: {pdf_path}")

    print("=" * 80)
    print(f"测试单个 PDF: {pdf_path}")

    pdf_name = pdf_path.stem
    out_dir = Path("../output_single_page") / pdf_name

    results = run_pdf_implicit_injection_check(
        pdf_path=str(pdf_path),
        work_dir=str(out_dir),
        dpi=200,
        batch_size=8,
        reorder_by_bbox=True,
        save_raw_compare=True,
    )

    print("[DONE] 单文件测试完成")