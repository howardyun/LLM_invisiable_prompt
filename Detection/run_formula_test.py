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


def main() -> None:
    pdf_path = "testData/formula.pdf"
    work_dir = "output_bbox_align/formula"
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

    module.run_pdf_implicit_injection_check_bbox(
        pdf_path=pdf_path,
        work_dir=work_dir,
        dpi=dpi,
        pdf_granularity=pdf_granularity,
        batch_size=batch_size,
        geom_threshold=geom_threshold,
        text_threshold=text_threshold,
        min_text_len=min_text_len,
        ignore_formula_regions=ignore_formula_regions,
    )


if __name__ == "__main__":
    main()
