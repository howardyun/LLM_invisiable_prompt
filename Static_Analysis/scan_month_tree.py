from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

try:
    from pdf_static_scan.config import ScanConfig
    from pdf_static_scan.loader_profiles import PROFILES, get_loader_profile
    from scan_date_tree import DayTask, iter_day_pdfs, scan_one_day, split_date_label, write_manifest
except ImportError:
    from Static_Analysis.pdf_static_scan.config import ScanConfig
    from Static_Analysis.pdf_static_scan.loader_profiles import PROFILES, get_loader_profile
    from Static_Analysis.scan_date_tree import DayTask, iter_day_pdfs, scan_one_day, split_date_label, write_manifest


@dataclass(frozen=True, slots=True)
class MonthResult:
    month: str
    input_dir: Path
    output_dir: Path
    day_count: int
    skipped_day_count: int
    pdf_count: int
    report_rows: int
    finding_count: int
    max_risk_score: float
    error_rows: int
    elapsed_ms: int
    month_manifest_csv: Path


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_root = Path(args.input_root).resolve()
    output_root = Path(args.output_root).resolve()
    if not input_root.exists():
        print(f"Input root does not exist: {input_root}", file=sys.stderr)
        return 1

    if args.list_months:
        for month_dir in list_month_dirs(input_root):
            print(month_dir.name)
        return 0

    month_names = parse_month_names(args)
    if not month_names:
        print("No month selected. Use --month May_2026 or --all-months.", file=sys.stderr)
        return 2

    loaders = parse_loaders(args)
    config = ScanConfig().with_overrides(
        min_score=args.min_score,
        fail_fast=args.fail_fast,
        jobs=args.jobs,
        extract_pypdf_text=args.include_pypdf_text,
        enable_texttrace_visibility=not args.disable_texttrace_visibility,
    )

    output_root.mkdir(parents=True, exist_ok=True)
    results: List[MonthResult] = []
    started = time.perf_counter()
    for index, month_name in enumerate(month_names, 1):
        month_dir = input_root / month_name
        if not month_dir.is_dir():
            print(f"[{index}/{len(month_names)}] missing month folder: {month_dir}", file=sys.stderr)
            continue
        if not args.quiet:
            print(f"[{index}/{len(month_names)}] scanning month {month_name}", file=sys.stderr)
        result = scan_one_month(month_dir, output_root / month_name, loaders, config, args)
        results.append(result)

    months_manifest = output_root / "months_manifest.csv"
    write_months_manifest(results, months_manifest)
    elapsed = time.perf_counter() - started
    if not args.quiet:
        print(
            f"Finished {len(results)} month(s) in {elapsed:.1f}s. "
            f"Months manifest: {months_manifest}",
            file=sys.stderr,
        )
    return 0 if results else 1


def scan_one_month(
    month_dir: Path,
    month_output_dir: Path,
    loaders: Sequence[str],
    config: ScanConfig,
    args: argparse.Namespace,
) -> MonthResult:
    month_output_dir.mkdir(parents=True, exist_ok=True)
    tasks = discover_month_day_tasks(
        month_dir=month_dir,
        month_output_dir=month_output_dir,
        recursive_within_day=args.recursive_within_day,
        include_empty=args.write_empty,
    )
    if args.days:
        wanted = {item.strip() for item in args.days.split(",") if item.strip()}
        tasks = [task for task in tasks if task.date_label in wanted or task.day in wanted]

    skipped = 0
    manifest_rows: List[Dict[str, Any]] = []
    pdf_count = 0
    report_rows = 0
    finding_count = 0
    max_risk_score = 0.0
    error_rows = 0
    started = time.perf_counter()
    month_manifest = month_output_dir / "month_manifest.csv"
    existing_rows = read_manifest_rows(month_manifest)
    existing_by_date = {str(row.get("date_label") or ""): row for row in existing_rows}

    for index, task in enumerate(tasks, 1):
        summary_path = task.output_dir / "summary.csv"
        if args.skip_existing_days and summary_path.exists():
            skipped += 1
            if not args.quiet:
                print(f"  [{index}/{len(tasks)}] skip existing {task.date_label}", file=sys.stderr)
            existing = existing_by_date.get(task.date_label)
            if existing:
                manifest_rows.append(existing)
                pdf_count += int(float(existing.get("pdf_count") or 0))
                report_rows += int(float(existing.get("report_rows") or 0))
                finding_count += int(float(existing.get("finding_count") or 0))
                max_risk_score = max(max_risk_score, float(existing.get("max_risk_score") or 0.0))
                error_rows += int(float(existing.get("error_rows") or 0))
            continue

        if not args.quiet:
            print(f"  [{index}/{len(tasks)}] {task.date_label}: {len(task.pdfs)} PDF(s)", file=sys.stderr)
        row = scan_one_day(task, loaders, config, args)
        manifest_rows.append(row)
        pdf_count += int(row.get("pdf_count") or 0)
        report_rows += int(row.get("report_rows") or 0)
        finding_count += int(row.get("finding_count") or 0)
        max_risk_score = max(max_risk_score, float(row.get("max_risk_score") or 0.0))
        error_rows += int(row.get("error_rows") or 0)

    write_manifest(manifest_rows, month_manifest)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return MonthResult(
        month=month_dir.name,
        input_dir=month_dir,
        output_dir=month_output_dir,
        day_count=len(tasks),
        skipped_day_count=skipped,
        pdf_count=pdf_count,
        report_rows=report_rows,
        finding_count=finding_count,
        max_risk_score=max_risk_score,
        error_rows=error_rows,
        elapsed_ms=elapsed_ms,
        month_manifest_csv=month_manifest,
    )


def read_manifest_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def discover_month_day_tasks(
    month_dir: Path,
    month_output_dir: Path,
    recursive_within_day: bool,
    include_empty: bool,
) -> List[DayTask]:
    tasks: List[DayTask] = []
    for date_dir in sorted(path for path in month_dir.iterdir() if path.is_dir()):
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
                group=month_dir.name,
                date_label=date_dir.name,
                year=year,
                month=month,
                day=day,
                input_dir=pdf_dir,
                output_dir=month_output_dir / date_dir.name,
                pdfs=pdfs,
            )
        )
    return tasks


def list_month_dirs(input_root: Path) -> List[Path]:
    return sorted(path for path in input_root.iterdir() if path.is_dir())


def parse_month_names(args: argparse.Namespace) -> List[str]:
    if args.all_months:
        return [path.name for path in list_month_dirs(Path(args.input_root).resolve())]
    names: List[str] = []
    for value in args.month or []:
        names.extend(item.strip() for item in value.split(",") if item.strip())
    return list(dict.fromkeys(names))


def parse_loaders(args: argparse.Namespace) -> List[str]:
    if args.loaders:
        loaders = [item.strip() for item in args.loaders.split(",") if item.strip()]
    else:
        loaders = [args.loader]
    for loader in loaders:
        get_loader_profile(loader)
    return loaders


def write_months_manifest(results: List[MonthResult], path: Path) -> None:
    fieldnames = [
        "month",
        "input_dir",
        "output_dir",
        "day_count",
        "skipped_day_count",
        "pdf_count",
        "report_rows",
        "finding_count",
        "max_risk_score",
        "error_rows",
        "elapsed_ms",
        "month_manifest_csv",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "month": result.month,
                    "input_dir": str(result.input_dir),
                    "output_dir": str(result.output_dir),
                    "day_count": result.day_count,
                    "skipped_day_count": result.skipped_day_count,
                    "pdf_count": result.pdf_count,
                    "report_rows": result.report_rows,
                    "finding_count": result.finding_count,
                    "max_risk_score": result.max_risk_score,
                    "error_rows": result.error_rows,
                    "elapsed_ms": result.elapsed_ms,
                    "month_manifest_csv": str(result.month_manifest_csv),
                }
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan one or more month folders like May_2026/2026-05-10/pdfs."
    )
    parser.add_argument("--input-root", required=True, help="Root folder containing month buckets, e.g. G:\\arxiv_pdf")
    parser.add_argument(
        "--output-root",
        default=str(Path("Static_Analysis") / "monthly_scan_output"),
        help="Output root. Results are written as output-root/month/date/*.csv",
    )
    parser.add_argument("--month", action="append", help="Month folder to scan, e.g. May_2026. Can be repeated or comma-separated.")
    parser.add_argument("--all-months", action="store_true", help="Scan every month folder under --input-root.")
    parser.add_argument("--list-months", action="store_true", help="List available month folders and exit.")
    parser.add_argument("--days", help="Optional comma-separated date folders inside the selected month, e.g. 2026-05-10.")
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
    parser.add_argument("--recursive-within-day", action="store_true", help="Recursively scan PDFs under each pdfs folder.")
    parser.add_argument("--write-empty", action="store_true", help="Write empty CSVs for dates without PDFs.")
    parser.add_argument("--skip-existing-days", action="store_true", help="Skip a date if output summary.csv already exists.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
