#!/usr/bin/env python3
"""Batch entry point for the patch-parallel detector."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from batch_ocr import RapidOCRBatchRegionalOCR
from parallel_pipeline import scan_pdf_parallel


SUMMARY_FIELDS = [
    "index",
    "pdf_path",
    "status",
    "risk_level",
    "risk_score",
    "suspicious_regions",
    "report_path",
    "elapsed_seconds",
    "error",
]


def build_argument_parser() -> argparse.ArgumentParser:
    """Define the folder-level patch-parallel CLI."""

    parser = argparse.ArgumentParser(description="Scan every PDF in a folder with patch-level parallel OCR.")
    parser.add_argument("--input-dir", required=True, help="Folder containing PDF files.")
    parser.add_argument("--out", default="./out_parallel", help="Batch output root directory.")
    parser.add_argument("--max-pages", type=int, default=None, help="Only scan the first N pages of each PDF.")
    parser.add_argument("--dpi", type=int, default=180, help="Page rendering DPI.")
    parser.add_argument("--padding", type=float, default=3.0, help="OCR patch padding in PDF points.")
    parser.add_argument("--device", choices=["cuda", "auto", "cpu"], default="cuda")
    parser.add_argument("--num-threads", type=int, default=4)
    parser.add_argument("--patch-workers", type=int, default=0, help="Primary patch OCR workers. 0 means auto.")
    parser.add_argument("--gap-workers", type=int, default=0, help="Second-pass gap OCR workers. 0 means auto.")
    parser.add_argument("--ocr-threads-per-worker", type=int, default=None)
    parser.add_argument("--ocr-mode", choices=["batch", "workers"], default="batch")
    parser.add_argument("--ocr-cls-batch-size", type=int, default=32)
    parser.add_argument("--ocr-rec-batch-size", type=int, default=64)
    parser.add_argument("--recursive", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--draw-bboxes", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--stop-on-error", action="store_true", help="Stop after the first failed PDF.")
    return parser


def find_pdfs(input_dir: Path, recursive: bool) -> list[Path]:
    """Return PDFs in stable order."""

    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(input_dir.glob(pattern), key=lambda path: str(path).lower())


def output_root_for_pdf(batch_out: Path, input_dir: Path, pdf_path: Path, recursive: bool) -> Path:
    """Mirror input subfolders in the output root to avoid duplicate-stem collisions."""

    if not recursive:
        return batch_out
    relative_parent = pdf_path.parent.relative_to(input_dir)
    return batch_out if str(relative_parent) == "." else batch_out / relative_parent


def make_scan_args(args: argparse.Namespace, pdf_path: Path, pdf_out_root: Path) -> SimpleNamespace:
    """Convert batch args to single-PDF scan args."""

    return SimpleNamespace(
        pdf=str(pdf_path),
        out=str(pdf_out_root),
        max_pages=args.max_pages,
        dpi=args.dpi,
        padding=args.padding,
        device=args.device,
        num_threads=args.num_threads,
        patch_workers=args.patch_workers,
        gap_workers=args.gap_workers,
        ocr_threads_per_worker=args.ocr_threads_per_worker,
        ocr_mode=args.ocr_mode,
        ocr_cls_batch_size=args.ocr_cls_batch_size,
        ocr_rec_batch_size=args.ocr_rec_batch_size,
        draw_bboxes=args.draw_bboxes,
    )


def summarize_report(report_path: Path) -> dict[str, Any]:
    """Extract fields useful for batch-level triage."""

    report = json.loads(report_path.read_text(encoding="utf-8"))
    summary = report.get("summary") or {}
    return {
        "risk_level": report.get("risk_level", ""),
        "risk_score": report.get("risk_score", ""),
        "suspicious_regions": summary.get("suspicious_regions", ""),
    }


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write or refresh the batch summary CSV after each PDF."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS})


def write_summary_json(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write or refresh the batch summary JSON after each PDF."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    """Scan PDFs one by one and keep a batch summary."""

    args = build_argument_parser().parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve()
    batch_out = Path(args.out).expanduser().resolve()
    if not input_dir.is_dir():
        print(f"ERROR: input directory not found: {input_dir}", file=sys.stderr)
        return 2

    pdfs = find_pdfs(input_dir, args.recursive)
    if not pdfs:
        print(f"No PDF files found under: {input_dir}")
        return 0

    batch_out.mkdir(parents=True, exist_ok=True)
    summary_csv = batch_out / "batch_summary.csv"
    summary_json = batch_out / "batch_summary.json"
    rows: list[dict[str, Any]] = []
    failures = 0

    print(f"Found {len(pdfs)} PDF(s) under {input_dir}")
    print(f"Batch summary: {summary_csv}")

    shared_batch_recognizer = None
    if args.ocr_mode == "batch":
        warm_started = time.time()
        print(
            "Warming shared RapidOCR batch model: "
            f"device={args.device}, cls_batch={args.ocr_cls_batch_size}, "
            f"rec_batch={args.ocr_rec_batch_size}"
        )
        shared_batch_recognizer = RapidOCRBatchRegionalOCR(
            device=args.device,
            cls_batch_size=args.ocr_cls_batch_size,
            rec_batch_size=args.ocr_rec_batch_size,
        )
        print(f"      Warmed in {time.time() - warm_started:.2f}s")

    for index, pdf_path in enumerate(pdfs, start=1):
        started = time.time()
        row: dict[str, Any] = {
            "index": index,
            "pdf_path": str(pdf_path),
            "status": "failed",
            "risk_level": "",
            "risk_score": "",
            "suspicious_regions": "",
            "report_path": "",
            "elapsed_seconds": "",
            "error": "",
        }
        print(f"\n[{index}/{len(pdfs)}] Scanning {pdf_path.name}")
        try:
            pdf_out_root = output_root_for_pdf(batch_out, input_dir, pdf_path, args.recursive)
            report_path = scan_pdf_parallel(make_scan_args(args, pdf_path, pdf_out_root), batch_recognizer=shared_batch_recognizer)
            report_summary = summarize_report(report_path)
            row.update(report_summary)
            row["status"] = "ok"
            row["report_path"] = str(report_path)
            print(
                "      OK: "
                f"risk={row['risk_level']} score={row['risk_score']} "
                f"suspicious={row['suspicious_regions']}"
            )
        except KeyboardInterrupt:
            print("Interrupted.", file=sys.stderr)
            return 130
        except Exception as exc:
            failures += 1
            row["error"] = f"{type(exc).__name__}: {exc}"
            print(f"      FAILED: {row['error']}", file=sys.stderr)
            if args.stop_on_error:
                rows.append(row)
                row["elapsed_seconds"] = round(time.time() - started, 2)
                write_summary_csv(summary_csv, rows)
                write_summary_json(summary_json, rows)
                return 1
        finally:
            row["elapsed_seconds"] = round(time.time() - started, 2)
            if row not in rows:
                rows.append(row)
            write_summary_csv(summary_csv, rows)
            write_summary_json(summary_json, rows)

    print(f"\nDone. Success={len(pdfs) - failures}, Failed={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

