from __future__ import annotations

import argparse
import csv
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .config import ScanConfig
from .loader_profiles import PROFILES, get_loader_profile
from .outputs import (
    FINDING_CSV_FIELDS,
    PROBLEM_SENTENCE_CSV_FIELDS,
    error_finding_row,
    finding_rows,
    problem_sentence_rows,
    summary_row,
    write_csv_rows,
    write_findings_csv,
    write_findings_csv_stream,
    write_json_report,
    write_problem_sentences_csv,
    write_summary_csv,
)
from .scanner import scan_pdf_multi
from .utils import dumps_json, iter_pdf_files


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan":
        return _cmd_scan(args)
    if args.command == "batch":
        return _cmd_batch(args)
    parser.print_help()
    return 2


def _cmd_scan(args: argparse.Namespace) -> int:
    loaders = _parse_loaders(args)
    config = _config_from_args(args, include_objects=bool(args.dump_objects))
    reports = scan_pdf_multi(args.input, loaders, config)
    output: Dict[str, Any] | List[Dict[str, Any]]
    output = reports[0] if len(reports) == 1 else reports
    csv_output = args.output_csv or (args.output if args.output and args.output.lower().endswith(".csv") else None)
    if csv_output:
        write_findings_csv(reports, csv_output)
    elif args.output:
        write_json_report(output, args.output)
    else:
        write_findings_csv_stream(reports)
    if args.output_problem_csv:
        write_problem_sentences_csv(reports, args.output_problem_csv)
    if args.dump_objects:
        objects_payload = reports[0].get("objects", []) if len(reports) == 1 else {r["loader"]: r.get("objects", []) for r in reports}
        write_json_report(objects_payload, args.dump_objects)
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    loaders = _parse_loaders(args)
    config = _config_from_args(args)
    files = list(iter_pdf_files(args.input_dir, recursive=not args.no_recursive))
    if args.limit:
        files = files[: args.limit]
    if not files:
        print(f"No PDF files found under {args.input_dir}", file=sys.stderr)
        return 1

    for loader in loaders:
        get_loader_profile(loader)

    summary_rows: List[Dict[str, Any]] = []
    report_count = 0
    print_summary_stdout = not args.output_jsonl and not args.output_csv and not args.output_findings_csv
    keep_rows = bool(args.output_csv or print_summary_stdout)
    jsonl_handle = None
    findings_csv_handle = None
    findings_csv_writer = None
    problem_csv_handle = None
    problem_csv_writer = None
    problem_seen: set[tuple[str, str, str, str]] = set()
    if args.output_jsonl:
        out_path = Path(args.output_jsonl)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        jsonl_handle = out_path.open("w", encoding="utf-8", newline="\n")
    if args.output_findings_csv:
        findings_path = Path(args.output_findings_csv)
        findings_path.parent.mkdir(parents=True, exist_ok=True)
        findings_csv_handle = findings_path.open("w", encoding="utf-8", newline="")
        findings_csv_writer = csv.DictWriter(
            findings_csv_handle,
            fieldnames=FINDING_CSV_FIELDS,
            extrasaction="ignore",
        )
        findings_csv_writer.writeheader()
    if args.output_problem_csv:
        problem_path = Path(args.output_problem_csv)
        problem_path.parent.mkdir(parents=True, exist_ok=True)
        problem_csv_handle = problem_path.open("w", encoding="utf-8", newline="")
        problem_csv_writer = csv.DictWriter(
            problem_csv_handle,
            fieldnames=PROBLEM_SENTENCE_CSV_FIELDS,
            extrasaction="ignore",
        )
        problem_csv_writer.writeheader()

    try:
        if config.jobs <= 1:
            for index, pdf_path in enumerate(files, 1):
                reports = scan_pdf_multi(pdf_path, loaders, config)
                report_count += _consume_batch_reports(
                    reports,
                    summary_rows,
                    jsonl_handle,
                    keep_rows,
                    findings_csv_writer,
                    problem_csv_writer,
                    problem_seen,
                )
                _progress(args, index, len(files), pdf_path)
        else:
            jobs = min(config.jobs, len(files))
            with ProcessPoolExecutor(max_workers=jobs) as executor:
                futures = {
                    executor.submit(_scan_worker, pdf_path, tuple(loaders), config): pdf_path
                    for pdf_path in files
                }
                for index, future in enumerate(as_completed(futures), 1):
                    pdf_path = futures[future]
                    try:
                        reports = future.result()
                    except Exception as exc:
                        reports = [_error_report(pdf_path, loader, str(exc)) for loader in loaders]
                    report_count += _consume_batch_reports(
                        reports,
                        summary_rows,
                        jsonl_handle,
                        keep_rows,
                        findings_csv_writer,
                        problem_csv_writer,
                        problem_seen,
                    )
                    _progress(args, index, len(files), pdf_path)
    finally:
        if jsonl_handle is not None:
            jsonl_handle.close()
        if findings_csv_handle is not None:
            findings_csv_handle.close()
        if problem_csv_handle is not None:
            problem_csv_handle.close()

    if args.output_csv:
        write_csv_rows(summary_rows, args.output_csv)
    if print_summary_stdout:
        write_summary_csv(summary_rows)
    if not args.quiet:
        print(
            f"Scanned {len(files)} PDF file(s), produced {report_count} report row(s).",
            file=sys.stderr,
        )
    return 0


def _scan_worker(pdf_path: str, loaders: Tuple[str, ...], config: ScanConfig) -> List[Dict[str, Any]]:
    return scan_pdf_multi(pdf_path, loaders, config)


def _consume_batch_reports(
    reports: Iterable[Dict[str, Any]],
    summary_rows: List[Dict[str, Any]],
    jsonl_handle: Any,
    keep_rows: bool,
    findings_csv_writer: Any = None,
    problem_csv_writer: Any = None,
    problem_seen: set[tuple[str, str, str, str]] | None = None,
) -> int:
    report_list = list(reports)
    if jsonl_handle is not None:
        for report in report_list:
            jsonl_handle.write(dumps_json(report, pretty=False))
            jsonl_handle.write("\n")
    if findings_csv_writer is not None:
        for report in report_list:
            rows = finding_rows(report)
            if rows:
                findings_csv_writer.writerows(rows)
            elif report.get("errors"):
                findings_csv_writer.writerow(error_finding_row(report))
    if problem_csv_writer is not None:
        seen = problem_seen if problem_seen is not None else set()
        for report in report_list:
            for row in problem_sentence_rows(report):
                key = (
                    str(row.get("path") or ""),
                    str(row.get("page_id") or ""),
                    str(row.get("sentence") or ""),
                    str(row.get("matched_phrases") or ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                problem_csv_writer.writerow(row)
    if keep_rows:
        summary_rows.extend(summary_row(report) for report in report_list)
    return len(report_list)


def _error_report(pdf_path: str, loader: str, message: str) -> Dict[str, Any]:
    abs_path = os.path.abspath(pdf_path)
    return {
        "file": {"path": abs_path, "sha256": None, "size_bytes": None, "page_count": None, "encrypted": None},
        "loader": loader,
        "summary": {
            "object_count": 0,
            "finding_count": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "max_risk_score": 0.0,
            "scan_time_ms": 0,
        },
        "object_stats": {},
        "findings": [],
        "errors": [{"stage": "worker", "message": message}],
    }


def _config_from_args(args: argparse.Namespace, *, include_objects: bool = False) -> ScanConfig:
    return ScanConfig().with_overrides(
        min_score=args.min_score,
        emit_all=args.emit_all,
        fail_fast=args.fail_fast,
        include_objects=include_objects,
        jobs=getattr(args, "jobs", 1),
        extract_pypdf_text=args.include_pypdf_text,
        enable_texttrace_visibility=not args.disable_texttrace_visibility,
    )


def _parse_loaders(args: argparse.Namespace) -> List[str]:
    if getattr(args, "loaders", None):
        loaders = [item.strip() for item in args.loaders.split(",") if item.strip()]
    else:
        loaders = [args.loader]
    for loader in loaders:
        get_loader_profile(loader)
    return loaders


def _progress(args: argparse.Namespace, index: int, total: int, pdf_path: str) -> None:
    if args.quiet:
        return
    if index == total or index == 1 or index % max(1, args.progress_every) == 0:
        print(f"[{index}/{total}] {pdf_path}", file=sys.stderr)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-static-scan",
        description="Fast static PDF implicit-injection scanner for LLM document pipelines.",
    )
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="Scan one PDF and write a simple CSV findings table.")
    scan.add_argument("--input", required=True, help="Input PDF path.")
    scan.add_argument("--loader", default="generic_t1", choices=sorted(PROFILES), help="Loader profile.")
    scan.add_argument("--loaders", help="Comma-separated loader profiles; extracts objects once and evaluates each profile.")
    scan.add_argument("--output", help="Output path. Use .csv for simple findings CSV; other suffixes write JSON.")
    scan.add_argument("--output-csv", help="Output simple findings CSV path.")
    scan.add_argument("--output-problem-csv", help="Deduplicated suspicious sentence CSV path.")
    scan.add_argument("--dump-objects", help="Write extracted objects JSON for debugging.")
    _add_common_args(scan)
    scan.set_defaults(command="scan")

    batch = sub.add_parser("batch", help="Scan a directory and write JSONL/CSV outputs.")
    batch.add_argument("--input-dir", required=True, help="Directory containing PDF files.")
    batch.add_argument("--loader", default="generic_t1", choices=sorted(PROFILES), help="Loader profile.")
    batch.add_argument("--loaders", help="Comma-separated loader profiles; extracts each PDF once.")
    batch.add_argument("--output-jsonl", help="Batch JSONL output path.")
    batch.add_argument("--output-csv", help="Simple CSV summary output path.")
    batch.add_argument("--output-findings-csv", help="Control-intent finding CSV output path.")
    batch.add_argument(
        "--output-problem-csv",
        help="Deduplicated CSV of which PDF contains which suspicious sentence.",
    )
    batch.add_argument("--jobs", type=int, default=1, help="Parallel worker count.")
    batch.add_argument("--no-recursive", action="store_true", help="Only scan direct children of --input-dir.")
    batch.add_argument("--limit", type=int, help="Scan only the first N PDF files.")
    batch.add_argument("--progress-every", type=int, default=100, help="Progress log interval.")
    batch.add_argument("--quiet", action="store_true", help="Suppress progress logs.")
    _add_common_args(batch)
    batch.set_defaults(command="batch")
    return parser


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--min-score", type=float, default=0.40, help="Minimum score to emit a finding.")
    parser.add_argument("--emit-all", action="store_true", help="Emit all evaluated objects, including low scores.")
    parser.add_argument("--fail-fast", action="store_true", help="Abort on first parser/extractor error.")
    parser.add_argument(
        "--include-pypdf-text",
        action="store_true",
        help="Also extract page text with pypdf and add it only when it differs from PyMuPDF spans.",
    )
    parser.add_argument(
        "--disable-texttrace-visibility",
        action="store_true",
        help="Skip PyMuPDF get_texttrace() visibility hints for maximum throughput.",
    )
