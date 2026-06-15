from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

try:
    from pdf_static_scan.config import ScanConfig
    from pdf_static_scan.loader_profiles import PROFILES, get_loader_profile
    from pdf_static_scan.outputs import (
        FINDING_CSV_FIELDS,
        PROBLEM_SENTENCE_CSV_FIELDS,
        error_finding_row,
        finding_rows,
        problem_sentence_rows,
        summary_row,
        write_csv_rows,
    )
    from pdf_static_scan.scanner import scan_pdf_multi
except ImportError:
    from Static_Analysis.pdf_static_scan.config import ScanConfig
    from Static_Analysis.pdf_static_scan.loader_profiles import PROFILES, get_loader_profile
    from Static_Analysis.pdf_static_scan.outputs import (
        FINDING_CSV_FIELDS,
        PROBLEM_SENTENCE_CSV_FIELDS,
        error_finding_row,
        finding_rows,
        problem_sentence_rows,
        summary_row,
        write_csv_rows,
    )
    from Static_Analysis.pdf_static_scan.scanner import scan_pdf_multi


@dataclass(frozen=True, slots=True)
class DayTask:
    layout: str
    group: str
    date_label: str
    year: str
    month: str
    day: str
    input_dir: Path
    output_dir: Path
    pdfs: Tuple[Path, ...]


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_root = Path(args.input_root).resolve()
    output_root = Path(args.output_root).resolve()
    loaders = parse_loaders(args)
    config = ScanConfig().with_overrides(
        min_score=args.min_score,
        fail_fast=args.fail_fast,
        jobs=args.jobs,
        extract_pypdf_text=args.include_pypdf_text,
        enable_texttrace_visibility=not args.disable_texttrace_visibility,
    )

    tasks = discover_day_tasks(
        input_root=input_root,
        output_root=output_root,
        layout=args.layout,
        recursive_within_day=args.recursive_within_day,
        include_empty=args.write_empty,
    )
    if not tasks:
        print(f"No day folders with PDF files found under {input_root}", file=sys.stderr)
        return 1

    manifest_rows: List[Dict[str, Any]] = []
    started = time.perf_counter()
    for index, task in enumerate(tasks, 1):
        if not args.quiet:
            print(
                f"[{index}/{len(tasks)}] {task.group}/{task.date_label}: "
                f"{len(task.pdfs)} PDF(s)",
                file=sys.stderr,
            )
        row = scan_one_day(task, loaders, config, args)
        manifest_rows.append(row)

    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "manifest.csv"
    write_manifest(manifest_rows, manifest_path)
    elapsed = time.perf_counter() - started
    if not args.quiet:
        print(
            f"Finished {len(tasks)} day folder(s) in {elapsed:.1f}s. "
            f"Manifest: {manifest_path}",
            file=sys.stderr,
        )
    return 0


def scan_one_day(
    task: DayTask,
    loaders: Sequence[str],
    config: ScanConfig,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    task.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = task.output_dir / "summary.csv"
    findings_path = task.output_dir / "findings.csv"
    problem_path = task.output_dir / "problem_sentences.csv"

    summary_rows: List[Dict[str, Any]] = []
    total_reports = 0
    total_errors = 0
    started = time.perf_counter()

    with findings_path.open("w", encoding="utf-8", newline="") as findings_handle, problem_path.open(
        "w", encoding="utf-8", newline=""
    ) as problem_handle:
        findings_writer = csv.DictWriter(findings_handle, fieldnames=FINDING_CSV_FIELDS, extrasaction="ignore")
        problem_writer = csv.DictWriter(problem_handle, fieldnames=PROBLEM_SENTENCE_CSV_FIELDS, extrasaction="ignore")
        findings_writer.writeheader()
        problem_writer.writeheader()
        problem_seen: set[tuple[str, str, str, str]] = set()

        if config.jobs <= 1 or len(task.pdfs) <= 1:
            for pdf_path in task.pdfs:
                reports = scan_pdf_multi(str(pdf_path), loaders, config)
                total_reports += consume_reports(reports, summary_rows, findings_writer, problem_writer, problem_seen)
        else:
            workers = min(config.jobs, len(task.pdfs))
            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(scan_pdf_worker, str(pdf_path), tuple(loaders), config): pdf_path
                    for pdf_path in task.pdfs
                }
                for future in as_completed(futures):
                    pdf_path = futures[future]
                    try:
                        reports = future.result()
                    except Exception as exc:
                        reports = [error_report(str(pdf_path), loader, str(exc)) for loader in loaders]
                    total_reports += consume_reports(
                        reports,
                        summary_rows,
                        findings_writer,
                        problem_writer,
                        problem_seen,
                    )

    write_csv_rows(summary_rows, str(summary_path))
    for row in summary_rows:
        if row.get("error"):
            total_errors += 1

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    finding_count = sum(int(row.get("finding_count") or 0) for row in summary_rows)
    max_score = max((float(row.get("max_risk_score") or 0.0) for row in summary_rows), default=0.0)
    return {
        "layout": task.layout,
        "group": task.group,
        "date_label": task.date_label,
        "year": task.year,
        "month": task.month,
        "day": task.day,
        "input_dir": str(task.input_dir),
        "output_dir": str(task.output_dir),
        "pdf_count": len(task.pdfs),
        "report_rows": total_reports,
        "finding_count": finding_count,
        "max_risk_score": max_score,
        "error_rows": total_errors,
        "elapsed_ms": elapsed_ms,
        "summary_csv": str(summary_path),
        "findings_csv": str(findings_path),
        "problem_sentences_csv": str(problem_path),
    }


def consume_reports(
    reports: Iterable[Dict[str, Any]],
    summary_rows: List[Dict[str, Any]],
    findings_writer: csv.DictWriter,
    problem_writer: csv.DictWriter,
    problem_seen: set[tuple[str, str, str, str]],
) -> int:
    count = 0
    for report in reports:
        count += 1
        summary_rows.append(summary_row(report))

        rows = finding_rows(report)
        if rows:
            findings_writer.writerows(rows)
        elif report.get("errors"):
            findings_writer.writerow(error_finding_row(report))

        for row in problem_sentence_rows(report):
            key = (
                str(row.get("path") or ""),
                str(row.get("page_id") or ""),
                str(row.get("sentence") or ""),
                str(row.get("matched_phrases") or ""),
            )
            if key in problem_seen:
                continue
            problem_seen.add(key)
            problem_writer.writerow(row)
    return count


def discover_day_tasks(
    input_root: Path,
    output_root: Path,
    layout: str,
    recursive_within_day: bool,
    include_empty: bool,
) -> List[DayTask]:
    if not input_root.exists():
        raise FileNotFoundError(f"Input root does not exist: {input_root}")

    tasks: List[DayTask] = []
    if layout in {"auto", "month-date-pdfs"}:
        tasks.extend(
            discover_month_date_pdfs_tasks(
                input_root=input_root,
                output_root=output_root,
                recursive_within_day=recursive_within_day,
                include_empty=include_empty,
            )
        )
    if layout in {"auto", "year-month-day"}:
        tasks.extend(
            discover_year_month_day_tasks(
                input_root=input_root,
                output_root=output_root,
                recursive_within_day=recursive_within_day,
                include_empty=include_empty,
                skip_inputs={task.input_dir.resolve() for task in tasks},
            )
        )
    return sorted(tasks, key=lambda task: (task.output_dir.as_posix(), task.input_dir.as_posix()))


def discover_month_date_pdfs_tasks(
    input_root: Path,
    output_root: Path,
    recursive_within_day: bool,
    include_empty: bool,
) -> List[DayTask]:
    tasks: List[DayTask] = []
    for month_bucket_dir in sorted(path for path in input_root.iterdir() if path.is_dir()):
        for date_dir in sorted(path for path in month_bucket_dir.iterdir() if path.is_dir()):
            pdf_dir = date_dir / "pdfs"
            if not pdf_dir.is_dir():
                continue
            pdfs = tuple(iter_day_pdfs(pdf_dir, recursive=recursive_within_day))
            if not pdfs and not include_empty:
                continue
            year, month, day = split_date_label(date_dir.name)
            tasks.append(
                DayTask(
                    layout="month-date-pdfs",
                    group=month_bucket_dir.name,
                    date_label=date_dir.name,
                    year=year,
                    month=month,
                    day=day,
                    input_dir=pdf_dir,
                    output_dir=output_root / month_bucket_dir.name / date_dir.name,
                    pdfs=pdfs,
                )
            )
    return tasks


def discover_year_month_day_tasks(
    input_root: Path,
    output_root: Path,
    recursive_within_day: bool,
    include_empty: bool,
    skip_inputs: set[Path],
) -> List[DayTask]:
    tasks: List[DayTask] = []
    for year_dir in sorted(path for path in input_root.iterdir() if path.is_dir()):
        for month_dir in sorted(path for path in year_dir.iterdir() if path.is_dir()):
            for day_dir in sorted(path for path in month_dir.iterdir() if path.is_dir()):
                if day_dir.resolve() in skip_inputs:
                    continue
                pdfs = tuple(iter_day_pdfs(day_dir, recursive=recursive_within_day))
                if not pdfs and not include_empty:
                    continue
                tasks.append(
                    DayTask(
                        layout="year-month-day",
                        group=year_dir.name,
                        date_label=f"{year_dir.name}-{month_dir.name}-{day_dir.name}",
                        year=year_dir.name,
                        month=month_dir.name,
                        day=day_dir.name,
                        input_dir=day_dir,
                        output_dir=output_root / year_dir.name / month_dir.name / day_dir.name,
                        pdfs=pdfs,
                    )
                )
    return tasks


def split_date_label(value: str) -> Tuple[str, str, str]:
    parts = value.replace("_", "-").split("-")
    if len(parts) >= 3 and parts[0].isdigit():
        return parts[0], parts[1], parts[2]
    return "", "", value


def iter_day_pdfs(day_dir: Path, recursive: bool) -> Iterable[Path]:
    iterator = day_dir.rglob("*.pdf") if recursive else day_dir.glob("*.pdf")
    return sorted(path.resolve() for path in iterator if path.is_file())


def scan_pdf_worker(pdf_path: str, loaders: Tuple[str, ...], config: ScanConfig) -> List[Dict[str, Any]]:
    return scan_pdf_multi(pdf_path, loaders, config)


def error_report(pdf_path: str, loader: str, message: str) -> Dict[str, Any]:
    return {
        "file": {"path": os.path.abspath(pdf_path), "sha256": None, "size_bytes": None, "page_count": None, "encrypted": None},
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


def write_manifest(rows: List[Dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "layout",
        "group",
        "date_label",
        "year",
        "month",
        "day",
        "input_dir",
        "output_dir",
        "pdf_count",
        "report_rows",
        "finding_count",
        "max_risk_score",
        "error_rows",
        "elapsed_ms",
        "summary_csv",
        "findings_csv",
        "problem_sentences_csv",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_loaders(args: argparse.Namespace) -> List[str]:
    if args.loaders:
        loaders = [item.strip() for item in args.loaders.split(",") if item.strip()]
    else:
        loaders = [args.loader]
    for loader in loaders:
        get_loader_profile(loader)
    return loaders


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan date-organized PDF folders and write one summary.csv per date."
    )
    parser.add_argument("--input-root", required=True, help="Root date folder, e.g. G:\\arxiv_pdf")
    parser.add_argument(
        "--output-root",
        default=str(Path("Static_Analysis") / "daily_scan_output"),
        help="Output root. For month-date-pdfs, results are output-root/month_bucket/date/*.csv",
    )
    parser.add_argument(
        "--layout",
        default="auto",
        choices=["auto", "month-date-pdfs", "year-month-day"],
        help="Input layout. Use month-date-pdfs for May_2026/2026-05-10/pdfs.",
    )
    parser.add_argument("--loader", default="generic_t1", choices=sorted(PROFILES), help="Loader profile.")
    parser.add_argument("--loaders", help="Comma-separated loader profiles.")
    parser.add_argument("--jobs", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 1)), help="Parallel workers per day.")
    parser.add_argument("--min-score", type=float, default=0.40, help="Scanner minimum score.")
    parser.add_argument("--fail-fast", action="store_true", help="Abort a file on first parser/extractor error.")
    parser.add_argument("--include-pypdf-text", action="store_true", help="Enable optional pypdf page text channel.")
    parser.add_argument(
        "--disable-texttrace-visibility",
        action="store_true",
        help="Skip PyMuPDF get_texttrace() hints for higher throughput.",
    )
    parser.add_argument(
        "--recursive-within-day",
        action="store_true",
        help="Recursively scan PDFs under each day folder.",
    )
    parser.add_argument("--write-empty", action="store_true", help="Write empty CSVs for day folders without PDFs.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
