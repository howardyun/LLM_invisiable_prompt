#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from pdf_semantic_detector import DetectionConfig
from pdf_semantic_detector.mapping import map_parser_spans
from pdf_semantic_detector.models import to_serializable
from pdf_semantic_detector.parser_extractors import aggregate_parser_spans, extract_parser_spans
from pdf_semantic_detector.pdf_analysis import build_structure_blocks, detect_font_encoding_issues, extract_pdf_regions
from pdf_semantic_detector.reporting import write_html_report, write_json_report
from pdf_semantic_detector.reporting.debug_preview import (
    write_parser_block_alignment_preview,
    write_rendered_text_preview,
    write_structure_blocks_preview,
)
from pdf_semantic_detector.risk import build_encoding_findings, build_findings
from pdf_semantic_detector.reporting.json_report import build_report


BASE_DIR = Path(__file__).resolve().parent

# Debug entrypoint: set this to True and edit FILE_CONFIG, then run this file directly.
RUN_WITH_FILE_CONFIG = True


FILE_CONFIG = {
    "pdf_dir": BASE_DIR.parent / "Detection" / "testData" / "Arixv",
    "batch_recursive": False,
    "target_parser": "pypdf",
    "out": BASE_DIR / "batch_report.json",
    "html": None,
    "debug_dir": None,
    "include_debug": False,
}
# FILE_CONFIG = {
#     # Batch mode: set "pdf_dir" and comment out "pdf".
#     "pdf_dir": BASE_DIR.parent / "Detection" / "testData" / "Arixv",
#     "batch_recursive": False,
#     "out": BASE_DIR / "batch_report.json",
#
#     # "pdf": BASE_DIR.parent / "Detection" / "testData" / 'org' /"pdf_migrate.pdf",
#     # "pdf": BASE_DIR.parent / "Detection" / "testData" / 'Arixv' /"2212.08983v2.pdf",
#     # "pdf": BASE_DIR.parent / "Detection" / "testData" / 'Arixv' /"2403.08142v2.pdf",
#     # "pdf": BASE_DIR.parent / "Detection" / "testData" / 'org' /"pdf_poc.pdf",
#
#     "target_parser": "pypdf",  # pypdf | pymupdf
#     "out": BASE_DIR / "report.json",
#     "html": BASE_DIR / "report.html",
#     "debug_dir": BASE_DIR / "debug",
#     "min_font_size": 5.0,
#     "tiny_font_size": 3.0,
#     "low_contrast_threshold": 30.0,
#     "match_threshold": 0.75,
#     "risk_threshold": 0.40,
#     "enable_occlusion": False,
#     "enable_font_encoding_analysis": True,
#     "enable_block_mapping": True,
#     "enable_parser_aggregation": True,
#     "include_debug": False,
# }


@dataclass(slots=True)
class RunParams:
    pdf: Optional[str] = None
    pdf_dir: Optional[str] = None
    batch_recursive: bool = False
    target_parser: str = "pypdf"
    out: Optional[str] = None
    html: Optional[str] = None
    debug_dir: Optional[str] = None
    min_font_size: float = 5.0
    tiny_font_size: float = 3.0
    low_contrast_threshold: float = 30.0
    match_threshold: float = 0.75
    risk_threshold: float = 0.40
    enable_occlusion: bool = False
    enable_font_encoding_analysis: bool = True
    enable_block_mapping: bool = True
    enable_parser_aggregation: bool = True
    include_debug: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect PDF implicit prompt injection with RRSD descriptors.")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--pdf", help="Input PDF path.")
    input_group.add_argument("--pdf-dir", help="Scan a directory of PDFs and record only PDFs with findings.")
    parser.add_argument("--batch-recursive", action="store_true", help="Recursively scan --pdf-dir.")
    parser.add_argument("--target-parser", default="pypdf", choices=["pypdf", "pymupdf"], help="Parser output to verify.")
    parser.add_argument("--out", help="JSON report path. In batch mode, this is the batch report path.")
    parser.add_argument("--html", help="Optional HTML report path for single-PDF mode.")
    parser.add_argument("--debug-dir", help="Write debug files for single-PDF mode.")
    parser.add_argument("--min-font-size", type=float, default=5.0)
    parser.add_argument("--tiny-font-size", type=float, default=3.0)
    parser.add_argument("--low-contrast-threshold", type=float, default=30.0)
    parser.add_argument("--match-threshold", type=float, default=0.75)
    parser.add_argument("--risk-threshold", type=float, default=0.40)
    parser.add_argument("--enable-occlusion", action="store_true")
    parser.add_argument("--disable-font-encoding-analysis", action="store_true")
    parser.add_argument("--disable-block-mapping", action="store_true")
    parser.add_argument("--disable-parser-aggregation", action="store_true")
    parser.add_argument("--include-debug", action="store_true", help="Embed regions/spans/mappings in the JSON report.")
    return parser.parse_args()


def params_from_file_config() -> RunParams:
    cfg = dict(FILE_CONFIG)
    for key in ("pdf", "pdf_dir", "out", "html", "debug_dir"):
        if cfg.get(key) is not None:
            cfg[key] = str(cfg[key])
    return RunParams(**cfg)


def params_from_cli() -> RunParams:
    args = parse_args()
    return RunParams(
        pdf=args.pdf,
        pdf_dir=args.pdf_dir,
        batch_recursive=args.batch_recursive,
        target_parser=args.target_parser,
        out=args.out,
        html=args.html,
        debug_dir=args.debug_dir,
        min_font_size=args.min_font_size,
        tiny_font_size=args.tiny_font_size,
        low_contrast_threshold=args.low_contrast_threshold,
        match_threshold=args.match_threshold,
        risk_threshold=args.risk_threshold,
        enable_occlusion=args.enable_occlusion,
        enable_font_encoding_analysis=not args.disable_font_encoding_analysis,
        enable_block_mapping=not args.disable_block_mapping,
        enable_parser_aggregation=not args.disable_parser_aggregation,
        include_debug=args.include_debug,
    )


def build_config(params: RunParams) -> DetectionConfig:
    return DetectionConfig(
        min_font_size=params.min_font_size,
        tiny_font_size=params.tiny_font_size,
        low_contrast_threshold=params.low_contrast_threshold,
        match_threshold=params.match_threshold,
        risk_threshold=params.risk_threshold,
        enable_occlusion=params.enable_occlusion,
        enable_font_encoding_analysis=params.enable_font_encoding_analysis,
        enable_block_mapping=params.enable_block_mapping,
        enable_parser_aggregation=params.enable_parser_aggregation,
        include_debug=params.include_debug,
    )


def analyze_pdf_details(pdf_path: str, parser_name: str, config: DetectionConfig) -> dict:
    regions = extract_pdf_regions(pdf_path, config)
    blocks = build_structure_blocks(regions, config)
    raw_spans = extract_parser_spans(pdf_path, parser_name)
    spans = aggregate_parser_spans(raw_spans, blocks, config)
    mappings = map_parser_spans(spans, regions, config, blocks)
    findings = build_findings(spans, mappings, regions, config, blocks)
    encoding_issues = detect_font_encoding_issues(pdf_path, config, regions)
    findings.extend(build_encoding_findings(encoding_issues, len(findings)))
    report = build_report(pdf_path, parser_name, regions, spans, mappings, findings, config, blocks)
    return {
        "report": report,
        "regions": regions,
        "blocks": blocks,
        "raw_spans": raw_spans,
        "spans": spans,
        "mappings": mappings,
        "encoding_issues": encoding_issues,
    }


def run_detection(params: RunParams) -> dict:
    if not params.pdf:
        raise ValueError("Single-PDF mode requires params.pdf.")

    config = build_config(params)
    analysis = analyze_pdf_details(params.pdf, params.target_parser, config)
    report = analysis["report"]
    regions = analysis["regions"]
    blocks = analysis["blocks"]
    raw_spans = analysis["raw_spans"]
    spans = analysis["spans"]
    mappings = analysis["mappings"]
    encoding_issues = analysis["encoding_issues"]

    if params.debug_dir:
        debug_dir = Path(params.debug_dir)
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / "regions.json").write_text(
            json.dumps([to_serializable(r) for r in regions], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (debug_dir / "parser_spans.json").write_text(
            json.dumps([to_serializable(s) for s in spans], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (debug_dir / "raw_parser_spans.json").write_text(
            json.dumps([to_serializable(s) for s in raw_spans], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (debug_dir / "structure_blocks.json").write_text(
            json.dumps([to_serializable(b) for b in blocks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (debug_dir / "mapping_results.json").write_text(
            json.dumps([to_serializable(m) for m in mappings], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (debug_dir / "font_encoding_issues.json").write_text(
            json.dumps([to_serializable(i) for i in encoding_issues], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_rendered_text_preview(params.pdf, regions, str(debug_dir / "rendered_text_preview.html"))
        write_structure_blocks_preview(params.pdf, blocks, str(debug_dir / "structure_blocks.html"))
        write_parser_block_alignment_preview(
            spans,
            mappings,
            blocks,
            regions,
            str(debug_dir / "parser_block_alignment.html"),
        )

    if params.out:
        write_json_report(report, params.out)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if params.html:
        write_html_report(report, params.html)

    return report


def find_pdf_files(pdf_dir: str, recursive: bool = False) -> List[Path]:
    root = Path(pdf_dir)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"PDF directory does not exist or is not a directory: {pdf_dir}")
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(path for path in root.glob(pattern) if path.is_file())


def finding_summary(report: dict) -> dict:
    findings = report.get("findings") or []
    risk_level_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for finding in findings:
        level = str(finding.get("risk_level", "unknown"))
        risk_level_counts[level] = risk_level_counts.get(level, 0) + 1
        for category in finding.get("categories", []):
            category = str(category)
            category_counts[category] = category_counts.get(category, 0) + 1
    return {
        "findings": len(findings),
        "high_or_above": sum(1 for finding in findings if finding.get("risk_level") in {"high", "critical"}),
        "risk_level_counts": risk_level_counts,
        "category_counts": category_counts,
    }


def run_batch_detection(params: RunParams) -> dict:
    if not params.pdf_dir:
        raise ValueError("Batch mode requires params.pdf_dir.")

    config = build_config(params)
    config.include_debug = False
    pdf_files = find_pdf_files(params.pdf_dir, params.batch_recursive)
    problematic: List[dict] = []
    errors: List[dict] = []

    for index, pdf_path in enumerate(pdf_files, start=1):
        try:
            analysis = analyze_pdf_details(str(pdf_path), params.target_parser, config)
            report = analysis["report"]
            findings = report.get("findings") or []
            if findings:
                problematic.append(
                    {
                        "pdf": str(pdf_path),
                        "summary": report.get("summary", {}),
                        "finding_summary": finding_summary(report),
                        "findings": findings,
                    }
                )
                print(f"[{index}/{len(pdf_files)}] FINDINGS {len(findings)}  {pdf_path}")
            else:
                print(f"[{index}/{len(pdf_files)}] ok  {pdf_path}")
        except Exception as exc:
            errors.append({"pdf": str(pdf_path), "error": f"{type(exc).__name__}: {exc}"})
            print(f"[{index}/{len(pdf_files)}] ERROR  {pdf_path}: {type(exc).__name__}: {exc}")

    batch_report = {
        "mode": "batch",
        "pdf_dir": str(Path(params.pdf_dir)),
        "recursive": params.batch_recursive,
        "parser": params.target_parser,
        "summary": {
            "scanned": len(pdf_files),
            "problematic": len(problematic),
            "errors": len(errors),
        },
        "problematic_pdfs": problematic,
        "errors": errors,
    }

    if params.out:
        write_json_report(batch_report, params.out)
    else:
        print(json.dumps(batch_report, ensure_ascii=False, indent=2))
    return batch_report


def main() -> None:
    params = params_from_file_config() if RUN_WITH_FILE_CONFIG and len(sys.argv) == 1 else params_from_cli()
    if params.pdf_dir:
        report = run_batch_detection(params)
        print(json.dumps(report.get("summary", {}), ensure_ascii=False, indent=2))
        if params.out:
            print(f"Batch JSON report written to: {params.out}")
        return

    report = run_detection(params)
    summary = report.get("summary", {})
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if params.out:
        print(f"JSON report written to: {params.out}")
    if params.html:
        print(f"HTML report written to: {params.html}")
    if params.debug_dir:
        print(f"Debug files written to: {params.debug_dir}")


if __name__ == "__main__":
    main()
