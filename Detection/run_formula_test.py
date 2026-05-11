from __future__ import annotations

import importlib.util
import os
from pathlib import Path

# 可选：如需强制用 GPU，可取消下一行注释
os.environ.setdefault("TORCH_DEVICE", "cuda")

BASE_DIR = Path(__file__).resolve().parent
SCRIPT_PATH = BASE_DIR / "pdf_bbox_vs_ocr_single.py"

if not SCRIPT_PATH.exists():
    raise FileNotFoundError(f"未找到主脚本: {SCRIPT_PATH}")

spec = importlib.util.spec_from_file_location("pdf_bbox_vs_ocr_single", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"无法加载脚本: {SCRIPT_PATH}")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main(root_dir) -> None:
    # root_dir = Path(r"../Parse/PDF")
    pdf_files = [file for file in root_dir.rglob("*") if file.is_file() and file.suffix.lower() == ".pdf"]

    print(f"一共找到 {len(pdf_files)} 个 PDF")
    for pdf in pdf_files:
        print(pdf)
        pdf_path = rf"{str(pdf)}"
        pdfname = str(pdf.name.split('.')[0])
        work_dir = f"output_bbox_align/{pdfname}"
        dpi = 200
        pdf_granularity = "line"
        batch_size = 8
        geom_threshold = 0.18
        text_threshold = 0.25
        min_text_len = 6
        ignore_formula_regions = True  # True=默认忽略公式型 PDF-only 区域

        print("[RUN] Starting PDF/OCR bbox alignment test...")
        print(f"[RUN] pdf_path={pdf_path}")
        print(f"[RUN] work_dir={work_dir}")

        module.run_pdf_bbox_match_and_compare(
            pdf_path=pdf_path,
            work_dir=work_dir,
            dpi=dpi,
            pdf_granularity=pdf_granularity,
            batch_size=batch_size,
            geom_threshold=geom_threshold,
            # debug_page= [1],
            # debug_pdf_region_ids=[83],
            # debug_ocr_region_ids= 5,
            # text_threshold=text_threshold,
            # min_text_len=min_text_len,
            # ignore_formula_regions=ignore_formula_regions,
        )
def single_pdf_main(pdf_path) -> None:


    # pdf_path = r"testData/Orignal_PDF.pdf"
    pdfname = pdf_path.split("/")[-1].split(".")[0]
    work_dir = f"output_bbox_align/{pdfname}"
    dpi = 200
    pdf_granularity = "line"
    batch_size = 8
    geom_threshold = 0.18
    text_threshold = 0.25
    min_text_len = 6
    ignore_formula_regions = True  # True=默认忽略公式型 PDF-only 区域

    print("[RUN] Starting PDF/OCR bbox alignment test...")
    print(f"[RUN] pdf_path={pdf_path}")
    print(f"[RUN] work_dir={work_dir}")

    module.run_pdf_bbox_match_and_compare(
        pdf_path=pdf_path,
        work_dir=work_dir,
        dpi=dpi,
        pdf_granularity=pdf_granularity,
        batch_size=batch_size,
        geom_threshold=geom_threshold,
        # debug_page= [1],
        # debug_pdf_region_ids=[83],
        # debug_ocr_region_ids= 5,
        # text_threshold=text_threshold,
        # min_text_len=min_text_len,
        # ignore_formula_regions=ignore_formula_regions,
    )

if __name__ == "__main__":
    # main(Path(r"LocalData"))
    single_pdf_main(r"testData/pdf_poc.pdf")
