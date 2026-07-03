#!/usr/bin/env python3
"""Enterprise-style PDF pre-screen pipeline.

Architecture:
- CPU stage: many worker processes run PyMuPDF-only pre-screening.
- GPU stage: one OCR model instance consumes candidate micro-batches.

This keeps the cheap structural scan parallel while avoiding multiple OCR
processes fighting over one GPU.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
PRESCREEN_DIR = ROOT_DIR / "detection_prescreen"
DETAIL_PARALLEL_DIR = ROOT_DIR / "detection_detail_parallel"
for path in (PRESCREEN_DIR, DETAIL_PARALLEL_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from batch_ocr import RapidOCRBatchRegionalOCR  # noqa: E402
from ocr_verify import (  # noqa: E402
    _crop_candidate_patches,
    _ocr_similarity,
    _target_text,
    write_ocr_outputs,
)
from output_schema import (  # noqa: E402
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
from prescreen_core import PrescreenConfig, scan_pdf_prescreen, write_prescreen_outputs  # noqa: E402


SUMMARY_FIELDS = [
    "index",
    "pdf_path",
    "status",
    "risk_level",
    "risk_score",
    "candidate_count",
    "ocr_candidate_count",
    "verified_hidden_count",
    "prescreen_elapsed_seconds",
    "ocr_elapsed_seconds",
    "total_elapsed_seconds",
    "report_path",
    "ocr_report_path",
    "error",
]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parallel enterprise PDF pre-screen pipeline.")
    parser.add_argument("--input-dir", required=True, help="Folder containing PDFs.")
    parser.add_argument("--out", default="./enterprise_prescreen_out", help="Output root directory.")
    parser.add_argument("--recursive", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--candidate-threshold", type=float, default=0.55)
    parser.add_argument("--ocr-threshold", type=float, default=0.65)
    parser.add_argument("--ocr", choices=["never", "on-hit", "always"], default="on-hit")
    parser.add_argument("--prescreen-workers", type=int, default=0, help="0 means auto.")
    parser.add_argument("--device", choices=["cuda", "auto", "cpu"], default="cuda")
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--padding", type=float, default=3.0)
    parser.add_argument("--ocr-cls-batch-size", type=int, default=32)
    parser.add_argument("--ocr-rec-batch-size", type=int, default=64)
    parser.add_argument("--max-ocr-candidates-per-pdf", type=int, default=50)
    parser.add_argument("--ocr-micro-batch-candidates", type=int, default=64)
    parser.add_argument("--summary-flush-interval", type=int, default=10)
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


def resolve_worker_count(requested: int, pdf_count: int) -> int:
    if pdf_count <= 0:
        return 0
    if requested and requested > 0:
        return min(requested, pdf_count)
    cpu_count = os.cpu_count() or 4
    return min(pdf_count, max(1, min(8, cpu_count - 1)))


def output_root_for_pdf(batch_out: Path, input_dir: Path, pdf_path: Path, recursive: bool) -> Path:
    if not recursive:
        return batch_out / pdf_path.stem
    relative_parent = pdf_path.parent.relative_to(input_dir)
    return (batch_out if str(relative_parent) == "." else batch_out / relative_parent) / pdf_path.stem


def make_prescreen_job(
    index: int,
    pdf_path: Path,
    input_dir: Path,
    batch_out: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    doc_id = make_doc_id(index)
    save_per_pdf = should_save_per_pdf(args.output_layout)
    run_dir = output_root_for_pdf(batch_out, input_dir, pdf_path, args.recursive)
    work_dir = run_dir if save_per_pdf else batch_out / "_ocr_work" / doc_id
    return {
        "index": index,
        "doc_id": doc_id,
        "pdf_path": str(pdf_path),
        "input_dir": str(input_dir),
        "run_dir": str(run_dir),
        "work_dir": str(work_dir),
        "save_per_pdf": save_per_pdf,
        "max_pages": args.max_pages,
        "candidate_threshold": args.candidate_threshold,
        "ocr_threshold": args.ocr_threshold,
        "ocr_mode": args.ocr,
        "max_ocr_candidates_per_pdf": args.max_ocr_candidates_per_pdf,
    }


def prescreen_worker(job: dict[str, Any]) -> dict[str, Any]:
    """Worker-process entry point. Must stay top-level for Windows spawn."""

    started = time.time()
    pdf_path = Path(job["pdf_path"])
    input_dir = Path(job["input_dir"])
    run_dir = Path(job["run_dir"])
    doc_id = str(job["doc_id"])
    save_per_pdf = bool(job.get("save_per_pdf"))
    report_path = str(run_dir / "prescreen_report.json") if save_per_pdf else ""
    row = {
        "index": job["index"],
        "pdf_path": str(pdf_path),
        "status": "failed",
        "risk_level": "",
        "risk_score": "",
        "candidate_count": "",
        "ocr_candidate_count": "",
        "verified_hidden_count": "",
        "prescreen_elapsed_seconds": "",
        "ocr_elapsed_seconds": "",
        "total_elapsed_seconds": "",
        "report_path": report_path,
        "ocr_report_path": "",
        "error": "",
    }
    try:
        config = PrescreenConfig(
            max_pages=job["max_pages"],
            candidate_threshold=job["candidate_threshold"],
            ocr_threshold=job["ocr_threshold"],
        )
        report = scan_pdf_prescreen(pdf_path, config)
        if save_per_pdf:
            write_prescreen_outputs(run_dir, report)
        selected = select_ocr_candidates(
            report.get("candidates", []),
            job["ocr_mode"],
            int(job["max_ocr_candidates_per_pdf"]),
        )
        total_elapsed = round(time.time() - started, 3)
        row.update(
            {
                "status": "ok",
                "risk_level": report.get("risk_level", ""),
                "risk_score": report.get("risk_score", ""),
                "candidate_count": report.get("candidate_count", 0),
                "ocr_candidate_count": len(selected),
                "verified_hidden_count": 0 if not selected else "pending",
                "prescreen_elapsed_seconds": report.get("elapsed_seconds", ""),
                "total_elapsed_seconds": total_elapsed,
            }
        )
        document_row = build_document_row(
            index=int(job["index"]),
            doc_id=doc_id,
            pdf_path=pdf_path,
            input_dir=input_dir,
            status="ok",
            report=report,
            total_elapsed_seconds=total_elapsed,
            report_path=report_path,
        )
        return {
            "ok": True,
            "index": job["index"],
            "doc_id": doc_id,
            "pdf_path": str(pdf_path),
            "run_dir": str(run_dir),
            "work_dir": str(job["work_dir"]),
            "row": row,
            "document_row": document_row,
            "detection_rows": build_detection_rows(
                index=int(job["index"]),
                doc_id=doc_id,
                pdf_path=pdf_path,
                input_dir=input_dir,
                report=report,
            ),
            "page_rows": build_page_rows(
                index=int(job["index"]),
                doc_id=doc_id,
                pdf_path=pdf_path,
                input_dir=input_dir,
                report=report,
            ),
            "ocr_candidates": selected,
        }
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["prescreen_elapsed_seconds"] = round(time.time() - started, 3)
        row["total_elapsed_seconds"] = row["prescreen_elapsed_seconds"]
        document_row = build_document_row(
            index=int(job["index"]),
            doc_id=doc_id,
            pdf_path=pdf_path,
            input_dir=input_dir,
            status="failed",
            error=row["error"],
            total_elapsed_seconds=row["total_elapsed_seconds"],
            report_path=report_path,
        )
        return {
            "ok": False,
            "index": job["index"],
            "doc_id": doc_id,
            "pdf_path": str(pdf_path),
            "run_dir": str(run_dir),
            "work_dir": str(job["work_dir"]),
            "row": row,
            "document_row": document_row,
            "detection_rows": [],
            "page_rows": [],
            "ocr_candidates": [],
        }


def select_ocr_candidates(
    candidates: list[dict[str, Any]],
    ocr_mode: str,
    limit: int,
) -> list[dict[str, Any]]:
    if ocr_mode == "never":
        return []
    if ocr_mode == "always":
        selected = candidates
    else:
        selected = [item for item in candidates if item.get("needs_ocr")]
    return sorted(selected, key=lambda item: float(item.get("score") or 0.0), reverse=True)[:limit]


def write_summary(summary_base: Path, rows_by_index: dict[int, dict[str, Any]]) -> None:
    summary_base.parent.mkdir(parents=True, exist_ok=True)
    rows = [rows_by_index[index] for index in sorted(rows_by_index)]
    with summary_base.with_suffix(".csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS})
    summary_base.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def pending_candidate_count(jobs: list[dict[str, Any]]) -> int:
    return sum(len(job.get("ocr_candidates") or []) for job in jobs)


def run_ocr_microbatch(
    jobs: list[dict[str, Any]],
    recognizer: RapidOCRBatchRegionalOCR | None,
    args: argparse.Namespace,
) -> tuple[RapidOCRBatchRegionalOCR | None, dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    """OCR candidate patches across multiple PDFs in one GPU batch."""

    if not jobs:
        return recognizer, {}, {}
    selected_jobs = [job for job in jobs if job.get("ocr_candidates")]
    if not selected_jobs:
        return recognizer, {}, {}

    save_per_pdf = should_save_per_pdf(args.output_layout)
    if recognizer is None:
        warm_started = time.time()
        print("      Warming single OCR model for enterprise GPU stage")
        recognizer = RapidOCRBatchRegionalOCR(
            device=args.device,
            cls_batch_size=args.ocr_cls_batch_size,
            rec_batch_size=args.ocr_rec_batch_size,
        )
        print(f"      OCR model ready in {time.time() - warm_started:.2f}s")

    batch_started = time.time()
    all_ready: list[dict[str, Any]] = []
    grouped_rows: dict[int, list[dict[str, Any]]] = {int(job["index"]): [] for job in selected_jobs}
    grouped_counts: dict[int, int] = {int(job["index"]): len(job["ocr_candidates"]) for job in selected_jobs}

    for job in selected_jobs:
        work_dir = Path(job["work_dir"])
        patches_dir = work_dir / "ocr_candidate_patches"
        patches_dir.mkdir(parents=True, exist_ok=True)
        crop_records = _crop_candidate_patches(
            Path(job["pdf_path"]),
            job["ocr_candidates"],
            patches_dir,
            args.dpi,
            args.padding,
        )
        for record in crop_records:
            record["job_index"] = int(job["index"])
            if record.get("patch_path"):
                all_ready.append(record)
            else:
                candidate = record["candidate"]
                grouped_rows[int(job["index"])].append(
                    {
                        "candidate_id": candidate.get("candidate_id"),
                        "page_no": candidate.get("page_no"),
                        "kind": candidate.get("kind"),
                        "candidate_score": candidate.get("score"),
                        "ocr_similarity": 0.0,
                        "visible_in_ocr": False,
                        "verified_hidden": False,
                        "text": _target_text(candidate),
                        "ocr_text": "",
                        "patch_path": "",
                        "bbox": candidate.get("bbox"),
                        "reason": [record.get("error", "crop failed")],
                        "ocr_error": record.get("error"),
                    }
                )

    patch_paths = [Path(record["patch_path"]) for record in all_ready]
    ocr_results, ocr_stats = recognizer.recognize_many(patch_paths) if patch_paths else ([], {})

    for record, result in zip(all_ready, ocr_results):
        candidate = record["candidate"]
        target_text = _target_text(candidate)
        similarity = _ocr_similarity(target_text, result.ocr_text)
        visible = similarity >= 0.72
        has_control = bool(candidate.get("control_snippets"))
        verified_hidden = has_control and not visible
        grouped_rows[int(record["job_index"])].append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "page_no": candidate.get("page_no"),
                "kind": candidate.get("kind"),
                "candidate_score": candidate.get("score"),
                "ocr_similarity": round(similarity, 4),
                "visible_in_ocr": visible,
                "verified_hidden": verified_hidden,
                "text": target_text,
                "ocr_text": result.ocr_text,
                "patch_path": record.get("patch_path") if (save_per_pdf or args.keep_ocr_work) else "",
                "bbox": record.get("bbox"),
                "reason": candidate.get("reason") or [],
                "ocr_error": result.ocr_error,
            }
        )

    ocr_updates: dict[int, dict[str, Any]] = {}
    ocr_reports: dict[int, dict[str, Any]] = {}
    batch_elapsed = time.time() - batch_started
    for job in selected_jobs:
        job_index = int(job["index"])
        rows = grouped_rows[job_index]
        verified_hidden_count = sum(bool(row.get("verified_hidden")) for row in rows)
        visible_count = sum(bool(row.get("visible_in_ocr")) for row in rows)
        report = {
            "pdf_path": str(Path(job["pdf_path"]).resolve()),
            "mode": "enterprise_ocr_candidate_microbatch",
            "elapsed_seconds": round(batch_elapsed, 4),
            "candidate_count": grouped_counts[job_index],
            "verified_hidden_count": verified_hidden_count,
            "visible_count": visible_count,
            "risk_level": "High" if verified_hidden_count else ("Medium" if rows else "Low"),
            "ocr_stats": {
                **ocr_stats,
                "micro_batch_pdf_count": len(selected_jobs),
                "micro_batch_candidate_count": len(all_ready),
            },
            "results": rows,
        }
        work_dir = Path(job["work_dir"])
        if save_per_pdf or args.keep_ocr_work:
            write_ocr_outputs(work_dir, report)
        ocr_updates[job_index] = {
            "verified_hidden_count": verified_hidden_count,
            "ocr_elapsed_seconds": round(batch_elapsed, 3),
            "ocr_report_path": str(work_dir / "ocr_verification.json") if (save_per_pdf or args.keep_ocr_work) else "",
        }
        ocr_reports[job_index] = report
        if not save_per_pdf and not args.keep_ocr_work and work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)

    return recognizer, ocr_updates, ocr_reports


def write_flat_result(
    document_writer: CsvTableWriter,
    detection_writer: CsvTableWriter,
    page_writer: CsvTableWriter,
    result: dict[str, Any],
    ocr_report: dict[str, Any] | None = None,
    ocr_update: dict[str, Any] | None = None,
) -> None:
    document_row = dict(result.get("document_row") or {})
    if ocr_update:
        document_row["verified_hidden_count"] = ocr_update.get("verified_hidden_count", "")
        document_row["ocr_elapsed_seconds"] = ocr_update.get("ocr_elapsed_seconds", "")
        document_row["ocr_report_path"] = ocr_update.get("ocr_report_path", "")
        document_row["visible_ocr_count"] = (ocr_report or {}).get("visible_count", "")
        document_row["total_elapsed_seconds"] = _sum_seconds(
            document_row.get("prescreen_elapsed_seconds"),
            document_row.get("ocr_elapsed_seconds"),
        )
    document_writer.writerow(document_row)
    detection_writer.writerows(
        merge_ocr_into_detection_rows(list(result.get("detection_rows") or []), ocr_report)
    )
    page_writer.writerows(list(result.get("page_rows") or []))


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

    workers = resolve_worker_count(args.prescreen_workers, len(pdfs))
    summary_base = batch_out / "enterprise_summary"
    documents_path = batch_out / "documents.csv"
    detections_path = batch_out / "detections.csv"
    pages_path = batch_out / "pages.csv"
    rows_by_index: dict[int, dict[str, Any]] = {}
    pending_ocr_jobs: list[dict[str, Any]] = []
    recognizer: RapidOCRBatchRegionalOCR | None = None
    failures = 0
    completed = 0
    submitted_at = time.time()

    print(f"Found {len(pdfs)} PDF(s) under {input_dir}")
    print(f"CPU pre-screen workers: {workers}")
    print(
        "GPU OCR stage: "
        f"mode={args.ocr}, single_model=true, micro_batch_candidates={args.ocr_micro_batch_candidates}"
    )
    print(f"Output layout: {args.output_layout}")
    print(f"Summary: {summary_base.with_suffix('.csv')}")
    print(f"Flat CSV: {documents_path}, {detections_path}, {pages_path}")

    jobs = [
        make_prescreen_job(index, pdf_path, input_dir, batch_out, args)
        for index, pdf_path in enumerate(pdfs, start=1)
    ]

    with (
        CsvTableWriter(documents_path, DOCUMENT_FIELDS) as document_writer,
        CsvTableWriter(detections_path, DETECTION_FIELDS) as detection_writer,
        CsvTableWriter(pages_path, PAGE_FIELDS) as page_writer,
    ):
        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_map = {executor.submit(prescreen_worker, job): job for job in jobs}
            for future in as_completed(future_map):
                result = future.result()
                completed += 1
                index = int(result["index"])
                row = dict(result["row"])
                rows_by_index[index] = row

                if not result.get("ok"):
                    failures += 1
                    write_flat_result(document_writer, detection_writer, page_writer, result)
                    print(f"[{completed}/{len(pdfs)}] FAILED {Path(row['pdf_path']).name}: {row['error']}")
                    if args.stop_on_error:
                        write_summary(summary_base, rows_by_index)
                        return 1
                else:
                    print(
                        f"[{completed}/{len(pdfs)}] OK {Path(row['pdf_path']).name}: "
                        f"candidates={row['candidate_count']} ocr={row['ocr_candidate_count']} "
                        f"risk={row['risk_level']}"
                    )
                    if result.get("ocr_candidates"):
                        pending_ocr_jobs.append(result)
                    else:
                        write_flat_result(document_writer, detection_writer, page_writer, result)

                if pending_candidate_count(pending_ocr_jobs) >= args.ocr_micro_batch_candidates:
                    print(
                        "      Flushing OCR micro-batch: "
                        f"{len(pending_ocr_jobs)} PDF(s), {pending_candidate_count(pending_ocr_jobs)} candidate(s)"
                    )
                    flushed_jobs = pending_ocr_jobs
                    recognizer, updates, ocr_reports = run_ocr_microbatch(flushed_jobs, recognizer, args)
                    for update_index, update in updates.items():
                        rows_by_index[update_index].update(update)
                        total = _sum_seconds(
                            rows_by_index[update_index].get("prescreen_elapsed_seconds"),
                            rows_by_index[update_index].get("ocr_elapsed_seconds"),
                        )
                        rows_by_index[update_index]["total_elapsed_seconds"] = total
                    for job_result in flushed_jobs:
                        job_index = int(job_result["index"])
                        write_flat_result(
                            document_writer,
                            detection_writer,
                            page_writer,
                            job_result,
                            ocr_reports.get(job_index),
                            updates.get(job_index),
                        )
                    pending_ocr_jobs = []

                if completed % max(1, args.summary_flush_interval) == 0:
                    write_summary(summary_base, rows_by_index)

        if pending_ocr_jobs:
            print(
                "      Final OCR micro-batch: "
                f"{len(pending_ocr_jobs)} PDF(s), {pending_candidate_count(pending_ocr_jobs)} candidate(s)"
            )
            flushed_jobs = pending_ocr_jobs
            recognizer, updates, ocr_reports = run_ocr_microbatch(flushed_jobs, recognizer, args)
            for update_index, update in updates.items():
                rows_by_index[update_index].update(update)
                total = _sum_seconds(
                    rows_by_index[update_index].get("prescreen_elapsed_seconds"),
                    rows_by_index[update_index].get("ocr_elapsed_seconds"),
                )
                rows_by_index[update_index]["total_elapsed_seconds"] = total
            for job_result in flushed_jobs:
                job_index = int(job_result["index"])
                write_flat_result(
                    document_writer,
                    detection_writer,
                    page_writer,
                    job_result,
                    ocr_reports.get(job_index),
                    updates.get(job_index),
                )

    write_summary(summary_base, rows_by_index)
    elapsed = time.time() - submitted_at
    print(f"\nDone. Success={len(pdfs) - failures}, Failed={failures}, elapsed={elapsed:.2f}s")
    return 1 if failures else 0


def _sum_seconds(a: Any, b: Any) -> float:
    try:
        return round(float(a or 0.0) + float(b or 0.0), 3)
    except Exception:
        return 0.0


if __name__ == "__main__":
    raise SystemExit(main())