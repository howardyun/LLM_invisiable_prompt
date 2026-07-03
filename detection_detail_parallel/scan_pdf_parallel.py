#!/usr/bin/env python3
"""Command-line entry point for the patch-parallel detector."""

from __future__ import annotations

import argparse
import sys

from parallel_pipeline import scan_pdf_parallel


def build_argument_parser() -> argparse.ArgumentParser:
    """Define the single-PDF patch-parallel CLI."""

    parser = argparse.ArgumentParser(
        description=(
            "Patch-level regional OCR + PyMuPDF text comparison, with RapidOCR "
            "batch inference for primary and second-pass gap OCR by default."
        )
    )
    parser.add_argument("--pdf", required=True, help="Input PDF path.")
    parser.add_argument("--out", default="./outputs_parallel", help="Output root directory.")
    parser.add_argument("--max-pages", type=int, default=None, help="Only scan the first N pages.")
    parser.add_argument("--dpi", type=int, default=180, help="Page rendering DPI.")
    parser.add_argument("--padding", type=float, default=3.0, help="OCR patch padding in PDF points.")
    parser.add_argument("--device", choices=["cuda", "auto", "cpu"], default="cuda")
    parser.add_argument("--num-threads", type=int, default=4, help="Docling layout threads and total CPU OCR budget.")
    parser.add_argument(
        "--patch-workers",
        type=int,
        default=0,
        help="Primary patch OCR workers. 0 means auto; CUDA auto is conservative.",
    )
    parser.add_argument(
        "--gap-workers",
        type=int,
        default=0,
        help="Second-pass tight gap OCR workers. 0 means auto.",
    )
    parser.add_argument(
        "--ocr-threads-per-worker",
        type=int,
        default=None,
        help="Override OCR CPU threads per worker. By default CPU divides --num-threads by workers.",
    )
    parser.add_argument(
        "--ocr-mode",
        choices=["batch", "workers"],
        default="batch",
        help="batch uses one RapidOCR model with batched recognition; workers keeps the older Docling worker mode.",
    )
    parser.add_argument(
        "--ocr-cls-batch-size",
        type=int,
        default=32,
        help="RapidOCR classifier batch size in --ocr-mode batch.",
    )
    parser.add_argument(
        "--ocr-rec-batch-size",
        type=int,
        default=64,
        help="RapidOCR recognizer batch size in --ocr-mode batch.",
    )
    parser.add_argument(
        "--draw-bboxes",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Save page images with candidate region boxes.",
    )
    return parser


def main() -> int:
    """Parse CLI args, run the detector, and convert exceptions to exit codes."""

    args = build_argument_parser().parse_args()
    try:
        scan_pdf_parallel(args)
        return 0
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

