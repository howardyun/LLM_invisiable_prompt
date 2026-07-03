#!/usr/bin/env python3
"""Folder-level PDF pre-screen with lazy OCR verification for hits."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from ocr_verify import RapidOCRBatchRegionalOCR, verify_candidates_with_ocr
from output_schema import (
    DETECTION_FIELDS,
    DOCUMENT_FIELDS,
    PAGE_FIELDS,
    CsvTableWriter,
    build_detection_rows,
    build_document_row,
    build_page_rows,
    make_doc_id,
    merge_ocr_into_detection_rows,
    should_save_per_pdf,
)
from prescreen_core import PrescreenConfig, scan_pdf_prescreen, write_prescreen_outputs


SUMMARY_FIELDS = [
    "index",
    "pdf_path",
    "status",
    "risk_level",
    "risk_score",
    "candidate_count",
    "ocr_candidate_count",
    "verified_hidden_count",
    "elapsed_seconds",
    "report_path",
    "error",
]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch PDF pre-screen before OCR.")
    parser.add_argument("--input-dir", required=True, help="Folder containing PDFs.")
    parser.add_argument("--out", default="./prescreen_batch_out", help="Output root directory.")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--candidate-threshold", type=float, default=0.55)
    parser.add_argument("--ocr-threshold", type=float, default=0.65)
    parser.add_argument("--ocr", choices=["never", "on-hit", "always"], default="on-hit")
    parser.add_argument("--device", choices=["cuda", "auto", "cpu"], default="cuda")
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--padding", type=float, default=3.0)
    parser.add_argument("--ocr-cls-batch-size", type=int, default=32)
    parser.add_argument("--ocr-rec-batch-size", type=int, default=64)
    parser.add_argument("--max-ocr-candidates", type=int, default=50)
    parser.add_argument("--recursive", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument(
        "--output-layout",
        choices=["csv", "legacy", "both"],
        default="csv",
        help="csv writes batch-level tables only; legacy/both also write one folder per PDF.",
    )
    parser.add_argument(
        "--keep-ocr-work",
        action="store_true",
        help="Keep temporary OCR crop folders when --output-layout csv is used.",
    )
    return parser


def find_pdfs(input_dir: Path, recursive: bool) -> list[Path]:
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(input_dir.glob(pattern), key=lambda path: str(path).lower())


def output_root_for_pdf(batch_out: Path, input_dir: Path, pdf_path: Path, recursive: bool) -> Path:
    if not recursive:
        return batch_out / pdf_path.stem
    relative_parent = pdf_path.parent.relative_to(input_dir)
    return (batch_out if str(relative_parent) == "." else batch_out / relative_parent) / pdf_path.stem


def write_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS})
    path.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
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

    config = PrescreenConfig(
        max_pages=args.max_pages,
        candidate_threshold=args.candidate_threshold,
        ocr_threshold=args.ocr_threshold,
    )
    summary_path = batch_out / "prescreen_summary"
    documents_path = batch_out / "documents.csv"
    detections_path = batch_out / "detections.csv"
    pages_path = batch_out / "pages.csv"
    rows: list[dict[str, Any]] = []
    failures = 0
    recognizer: RapidOCRBatchRegionalOCR | None = None
    save_per_pdf = should_save_per_pdf(args.output_layout)

    print(f"Found {len(pdfs)} PDF(s) under {input_dir}")
    print(f"Summary: {summary_path.with_suffix('.csv')}")
    print(f"Flat CSV: {documents_path}, {detections_path}, {pages_path}")

    with (
        CsvTableWriter(documents_path, DOCUMENT_FIELDS) as document_writer,
        CsvTableWriter(detections_path, DETECTION_FIELDS) as detection_writer,
        CsvTableWriter(pages_path, PAGE_FIELDS) as page_writer,
    ):
        for index, pdf_path in enumerate(pdfs, start=1):
            started = time.time()
            doc_id = make_doc_id(index)
            run_dir = output_root_for_pdf(batch_out, input_dir, pdf_path, args.recursive)
            work_dir = run_dir if save_per_pdf else batch_out / "_ocr_work" / doc_id
            report_path = str(run_dir / "prescreen_report.json") if save_per_pdf else ""
            row: dict[str, Any] = {
                "index": index,
                "pdf_path": str(pdf_path),
                "status": "failed",
                "risk_level": "",
                "risk_score": "",
                "candidate_count": "",
                "ocr_candidate_count": "",
                "verified_hidden_count": "",
                "elapsed_seconds": "",
                "report_path": report_path,
                "error": "",
            }
            print(f"\n[{index}/{len(pdfs)}] Pre-screening {pdf_path.name}")
            try:
                report = scan_pdf_prescreen(pdf_path, config)
                if save_per_pdf:
                    write_prescreen_outputs(run_dir, report)
                row.update(
                    {
                        "status": "ok",
                        "risk_level": report["risk_level"],
                        "risk_score": report["risk_score"],
                        "candidate_count": report["candidate_count"],
                        "ocr_candidate_count": report["ocr_candidate_count"],
                    }
                )

                ocr_report: dict[str, Any] | None = None
                ocr_report_path = ""
                should_ocr = args.ocr == "always" or (args.ocr == "on-hit" and report["should_run_ocr"])
                if should_ocr:
                    if recognizer is None:
                        warm_started = time.time()
                        print("      Warming OCR model for candidate verification")
                        recognizer = RapidOCRBatchRegionalOCR(
                            device=args.device,
                            cls_batch_size=args.ocr_cls_batch_size,
                            rec_batch_size=args.ocr_rec_batch_size,
                        )
                        print(f"      OCR model ready in {time.time() - warm_started:.2f}s")
                    ocr_report, recognizer = verify_candidates_with_ocr(
                        pdf_path=pdf_path,
                        candidates=report["candidates"],
                        out_dir=work_dir,
                        recognizer=recognizer,
                        device=args.device,
                        dpi=args.dpi,
                        padding=args.padding,
                        cls_batch_size=args.ocr_cls_batch_size,
                        rec_batch_size=args.ocr_rec_batch_size,
                        max_candidates=args.max_ocr_candidates,
                    )
                    if not save_per_pdf and not args.keep_ocr_work:
                        for result in ocr_report.get("results", []) or []:
                            result["patch_path"] = ""
                    ocr_report_path = str(work_dir / "ocr_verification.json") if (save_per_pdf or args.keep_ocr_work) else ""
                    row["verified_hidden_count"] = ocr_report["verified_hidden_count"]
                else:
                    row["verified_hidden_count"] = 0

                elapsed = round(time.time() - started, 3)
                detection_rows = merge_ocr_into_detection_rows(
                    build_detection_rows(
                        index=index,
                        doc_id=doc_id,
                        pdf_path=pdf_path,
                        input_dir=input_dir,
                        report=report,
                    ),
                    ocr_report,
                )
                document_writer.writerow(
                    build_document_row(
                        index=index,
                        doc_id=doc_id,
                        pdf_path=pdf_path,
                        input_dir=input_dir,
                        status="ok",
                        report=report,
                        ocr_report=ocr_report,
                        total_elapsed_seconds=elapsed,
                        report_path=report_path,
                        ocr_report_path=ocr_report_path,
                    )
                )
                detection_writer.writerows(detection_rows)
                page_writer.writerows(
                    build_page_rows(
                        index=index,
                        doc_id=doc_id,
                        pdf_path=pdf_path,
                        input_dir=input_dir,
                        report=report,
                    )
                )
                if not save_per_pdf and not args.keep_ocr_work and work_dir.exists():
                    shutil.rmtree(work_dir, ignore_errors=True)

                print(
                    "      OK: "
                    f"risk={row['risk_level']} score={row['risk_score']} "
                    f"candidates={row['candidate_count']} ocr={row['ocr_candidate_count']} "
                    f"verified_hidden={row['verified_hidden_count']}"
                )
            except KeyboardInterrupt:
                print("Interrupted.", file=sys.stderr)
                return 130
            except Exception as exc:
                failures += 1
                row["error"] = f"{type(exc).__name__}: {exc}"
                document_writer.writerow(
                    build_document_row(
                        index=index,
                        doc_id=doc_id,
                        pdf_path=pdf_path,
                        input_dir=input_dir,
                        status="failed",
                        error=row["error"],
                        total_elapsed_seconds=round(time.time() - started, 3),
                        report_path=report_path,
                    )
                )
                print(f"      FAILED: {row['error']}", file=sys.stderr)
                if args.stop_on_error:
                    row["elapsed_seconds"] = round(time.time() - started, 3)
                    rows.append(row)
                    write_summary(summary_path, rows)
                    return 1
            finally:
                row["elapsed_seconds"] = round(time.time() - started, 3)
                if row not in rows:
                    rows.append(row)
                write_summary(summary_path, rows)

    print(f"\nDone. Success={len(pdfs) - failures}, Failed={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())