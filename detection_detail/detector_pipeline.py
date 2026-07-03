"""End-to-end orchestration for the regional PDF detector.

The pipeline is intentionally split into small functions. The important idea is:
Docling proposes visual layout regions, PyMuPDF supplies PDF text/word geometry,
Docling RapidOCR checks what is visible, formula regions get a formula-OCR branch,
and PyMuPDF-only gaps get a second tight OCR pass before they become findings.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from detector_config import FORMULA_LABELS, PICTURE_LABELS
from detector_docling import DoclingRegionalOCR, parse_docling_layout
from detector_formula import analyze_formula_region
from detector_images import crop_region_patches, draw_visualizations, measure_visible_ink, render_pages
from detector_io import write_dicts_csv, write_json, write_results_csv
from detector_matching import build_gap_result, build_report, make_region_result, verify_region_gaps
from detector_models import LayoutRegion, RegionalResult
from detector_picture import analyze_picture_region
from detector_pymupdf import add_pymupdf_only_regions, collect_pymupdf_structures, extract_pymupdf_region_text
from detector_table import analyze_table_region, build_table_contexts, table_context_for_region
from detector_text import (
    extract_control_snippets,
    extract_parser_only_gaps,
    inline_math_gap_metrics,
    is_inline_math_gap,
)


TABLE_DEBUG_CSV_FIELDS = [
    "region_id",
    "page_no",
    "source",
    "label",
    "risk_type",
    "risk_score",
    "table_mode",
    "table_context",
    "table_text_metrics",
    "pymupdf_text",
    "docling_ocr_text",
    "similarity_debug_only",
    "length_ratio_debug_only",
    "intent_score",
    "parser_control_snippets",
    "ocr_control_snippets",
    "patch_path",
    "ocr_error",
    "reason",
]


GAP_VERIFICATION_CSV_FIELDS = [
    "parent_region_id",
    "gap_region_id",
    "page_no",
    "parent_label",
    "gap_status",
    "gap_text",
    "gap_reason",
    "missing_token_count",
    "inline_math_suppressed",
    "inline_math_metrics",
    "visible_ink_suppressed",
    "visible_ink_metrics",
    "visible_after_second_pass",
    "verify_similarity",
    "verify_ocr_text",
    "verify_ocr_error",
    "verify_patch_path",
    "verify_bbox",
    "word_location",
    "crop_meta",
    "parent_patch_path",
    "parent_pymupdf_text",
    "parent_ocr_text",
]


def _resolve_pdf_path(raw_path: str) -> Path:
    """Resolve and validate the input PDF path."""

    pdf_path = Path(raw_path).expanduser().resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    return pdf_path


def _prepare_run_dirs(output_root: str, pdf_path: Path) -> tuple[Path, Path, Path, Path]:
    """Create the output folder layout for one PDF scan."""

    run_dir = Path(output_root).expanduser().resolve() / pdf_path.stem
    pages_dir = run_dir / "pages"
    patches_dir = run_dir / "patches"
    visual_dir = run_dir / "visualization"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, pages_dir, patches_dir, visual_dir


def _is_formula_region(region: LayoutRegion) -> bool:
    """Return whether this region should use formula-specific comparison."""

    return region.source == "docling_region" and region.label.lower() in FORMULA_LABELS


def _is_picture_region(region: LayoutRegion) -> bool:
    """Return whether this region should use picture-specific skip handling."""

    return region.source == "docling_region" and region.label.lower() in PICTURE_LABELS


def _enrich_ocr_records(region: LayoutRegion, ocr_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach parent region metadata to raw OCR records for debugging."""

    enriched_records: list[dict[str, Any]] = []
    for record in ocr_records:
        enriched = dict(record)
        enriched.update(
            {
                "region_id": region.region_id,
                "source": region.source,
                "label": region.label,
                "page_no": region.page_no,
                "region_bbox": region.bbox,
                "patch_path": region.patch_path,
                "patch_pdf_bbox": region.extra.get("patch_pdf_bbox"),
                "patch_pixel_bbox": region.extra.get("patch_pixel_bbox"),
                "patch_size_px": region.extra.get("patch_size_px"),
            }
        )
        enriched_records.append(enriched)
    return enriched_records


def _attach_second_pass_summary(result: RegionalResult, records: list[dict[str, Any]]) -> None:
    """Copy second-pass OCR evidence onto the parent result row."""

    if not records:
        return
    texts = [str(item.get("verify_ocr_text") or "").strip() for item in records if item.get("verify_ocr_text")]
    similarities = [float(item.get("verify_similarity") or 0.0) for item in records]
    result.verify_ocr_text = " | ".join(texts)
    result.verify_similarity = round(max(similarities), 4) if similarities else None
    result.visible_after_second_pass = any(bool(item.get("visible_after_second_pass")) for item in records)


def _mark_parent_as_context_row(
    result: RegionalResult,
    still_missing: bool,
    inline_math_suppressed: bool = False,
    visible_ink_suppressed: bool = False,
) -> None:
    """Keep the parent row as context once gap rows carry the actual risk."""

    result.risk_type = "trusted"
    result.risk_score = 0.05
    if still_missing:
        result.reason = (
            "Region-level context is recorded here; missing PyMuPDF text is emitted "
            "separately as source=pymupdf_only after second-pass OCR verification."
        )
    elif inline_math_suppressed:
        result.reason = (
            "Region-level OCR missed inline math/formula symbols, but every still-missing "
            "gap was math-like and had no control-like instruction, so it was kept in "
            "debug output instead of suspicious results."
        )
    elif visible_ink_suppressed:
        result.reason = (
            "Region-level OCR missed text, but the tight verification crop visibly "
            "contains foreground ink and has no control-like instruction, so it was "
            "kept in debug output instead of suspicious results."
        )
    else:
        result.reason = (
            "Region-level OCR initially missed text, but a PyMuPDF-located tight "
            "second OCR pass verified the text as visible."
        )


def _partition_suppressed_gaps(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Split still-missing gaps into reportable and debug-only suppressions."""

    reportable: list[dict[str, Any]] = []
    suppressed_inline_math: list[dict[str, Any]] = []
    suppressed_visible_ink: list[dict[str, Any]] = []
    for record in records:
        text = str(record.get("text") or "")
        enriched = dict(record)
        control_snippets = extract_control_snippets(text)
        metrics = inline_math_gap_metrics(text)
        enriched["inline_math_metrics"] = metrics
        enriched["inline_math_suppressed"] = False
        enriched["visible_ink_suppressed"] = False

        if is_inline_math_gap(text):
            enriched["inline_math_suppressed"] = True
            enriched["suppression_reason"] = (
                "Still missing after second-pass OCR, but the gap is mostly inline "
                "math/formula notation and has no control-like instruction."
            )
            suppressed_inline_math.append(enriched)
            continue

        verify_patch_path = record.get("verify_patch_path")
        if verify_patch_path and not control_snippets:
            try:
                ink_metrics = measure_visible_ink(Path(verify_patch_path))
            except Exception as exc:
                ink_metrics = {"visible_ink": False, "visible_ink_error": f"{type(exc).__name__}: {exc}"}
            enriched["visible_ink_metrics"] = ink_metrics
            if ink_metrics.get("visible_ink"):
                enriched["visible_ink_suppressed"] = True
                enriched["suppression_reason"] = (
                    "Still missing after second-pass OCR, but the tight verification "
                    "crop contains visible foreground ink and the gap has no control-like instruction."
                )
                suppressed_visible_ink.append(enriched)
                continue

        reportable.append(enriched)
    return reportable, suppressed_inline_math, suppressed_visible_ink


def _verify_docling_region_gaps(
    region: LayoutRegion,
    region_result: RegionalResult,
    ocr_text: str,
    all_words: list[dict],
    page_images: dict[int, Path],
    patches_dir: Path,
    dpi: int,
    padding: float,
    ocr: DoclingRegionalOCR,
) -> tuple[list[RegionalResult], dict[str, Any] | None]:
    """Find and verify PyMuPDF-only spans inside a Docling layout region.

    Formula regions are intentionally not passed here; they use formula OCR and
    formula-token comparison instead of normal text gap matching.
    """

    parser_text = region.pymupdf_text or region.docling_text
    initial_gaps = extract_parser_only_gaps(parser_text, ocr_text)
    if not initial_gaps:
        return [], None

    verified_visible, still_missing = verify_region_gaps(
        region=region,
        gaps=initial_gaps,
        all_words=all_words,
        page_images=page_images,
        patches_dir=patches_dir,
        dpi=dpi,
        padding_points=padding,
        ocr=ocr,
    )

    reportable_missing, suppressed_inline_math, suppressed_visible_ink = _partition_suppressed_gaps(still_missing)

    _attach_second_pass_summary(region_result, verified_visible + reportable_missing + suppressed_inline_math + suppressed_visible_ink)
    _mark_parent_as_context_row(
        region_result,
        still_missing=bool(reportable_missing),
        inline_math_suppressed=bool(suppressed_inline_math),
        visible_ink_suppressed=bool(suppressed_visible_ink),
    )

    emitted_results: list[RegionalResult] = []
    if reportable_missing:
        emitted_results.append(build_gap_result(region, reportable_missing, reportable_missing))

    debug_record = {
        "parent_region_id": region.region_id,
        "page_no": region.page_no,
        "parent_label": region.label,
        "parent_bbox": region.bbox,
        "patch_path": region.patch_path,
        "initial_gaps": initial_gaps,
        "verified_visible_gaps": verified_visible,
        "suppressed_inline_math_gaps": suppressed_inline_math,
        "suppressed_visible_ink_gaps": suppressed_visible_ink,
        "still_missing_gaps": reportable_missing,
        "control_snippets": extract_control_snippets(" | ".join(gap["text"] for gap in reportable_missing)),
        "pymupdf_text": parser_text,
        "ocr_text": ocr_text,
        "emitted_gap_region_ids": [item.region_id for item in emitted_results],
    }
    return emitted_results, debug_record


def _run_regional_ocr_and_matching(
    regions: list[LayoutRegion],
    pymupdf_words: list[dict],
    page_images: dict[int, Path],
    patches_dir: Path,
    dpi: int,
    padding: float,
    device: str,
    num_threads: int,
) -> tuple[
    list[RegionalResult],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    str,
]:
    """OCR every patch, compare against PyMuPDF text, and verify OCR gaps."""

    patch_regions = [region for region in regions if region.patch_path]
    table_contexts = build_table_contexts(patch_regions)
    print(f"[5/7] Docling regional OCR: {len(patch_regions)} patches")
    ocr = DoclingRegionalOCR(device, num_threads)

    formula_regions_exist = any(_is_formula_region(region) for region in patch_regions)
    formula_recognizer = None
    if formula_regions_exist:
        print("      Formula mode: intent-only scan; TeX/formula semantic comparison disabled")
    picture_regions_exist = any(_is_picture_region(region) for region in patch_regions)
    if picture_regions_exist:
        print("      Picture mode: picture-like regions are trusted/debug-only in this version")
    if table_contexts:
        print(f"      Table mode: {len(table_contexts)} table bbox(es); table cells are control-only suspicious")

    results: list[RegionalResult] = []
    ocr_items: list[dict[str, Any]] = []
    gap_debug: list[dict[str, Any]] = []
    formula_debug: list[dict[str, Any]] = []
    picture_debug: list[dict[str, Any]] = []
    table_debug: list[dict[str, Any]] = []

    for index, region in enumerate(patch_regions, start=1):
        ocr_text, ocr_error, ocr_records = ocr.recognize_one(Path(region.patch_path))
        ocr_items.extend(_enrich_ocr_records(region, ocr_records))
        table_context = table_context_for_region(region, table_contexts)

        if _is_formula_region(region):
            region_result, formula_record = analyze_formula_region(region, ocr_text, ocr_error, formula_recognizer)
            results.append(region_result)
            formula_debug.append(formula_record)
        elif _is_picture_region(region):
            region_result, picture_record = analyze_picture_region(region, ocr_text, ocr_error)
            results.append(region_result)
            picture_debug.append(picture_record)
        elif table_context:
            region_result, table_record = analyze_table_region(region, ocr_text, ocr_error, table_context)
            results.append(region_result)
            table_debug.append(table_record)
        else:
            region_result = make_region_result(region, ocr_text, ocr_error)
            results.append(region_result)

            if region.source == "docling_region":
                gap_results, debug_record = _verify_docling_region_gaps(
                    region=region,
                    region_result=region_result,
                    ocr_text=ocr_text,
                    all_words=pymupdf_words,
                    page_images=page_images,
                    patches_dir=patches_dir,
                    dpi=dpi,
                    padding=padding,
                    ocr=ocr,
                )
                results.extend(gap_results)
                if debug_record:
                    gap_debug.append(debug_record)

        if index == 1 or index % 10 == 0 or index == len(patch_regions):
            print(f"      OCR progress: {index}/{len(patch_regions)}")

    return results, ocr_items, gap_debug, formula_debug, picture_debug, table_debug, ocr.device_summary


def _flatten_gap_verification_rows(gap_debug: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten visible and still-missing second-pass OCR records into CSV rows."""

    rows: list[dict[str, Any]] = []
    for parent in gap_debug:
        for status, key in (
            ("verified_visible", "verified_visible_gaps"),
            ("suppressed_inline_math", "suppressed_inline_math_gaps"),
            ("suppressed_visible_ink", "suppressed_visible_ink_gaps"),
            ("still_missing", "still_missing_gaps"),
        ):
            for record in parent.get(key, []) or []:
                rows.append(
                    {
                        "parent_region_id": parent.get("parent_region_id"),
                        "gap_region_id": "",
                        "page_no": parent.get("page_no"),
                        "parent_label": parent.get("parent_label"),
                        "gap_status": status,
                        "gap_text": record.get("text"),
                        "gap_reason": record.get("gap_reason"),
                        "missing_token_count": record.get("missing_token_count"),
                        "inline_math_suppressed": record.get("inline_math_suppressed"),
                        "inline_math_metrics": record.get("inline_math_metrics"),
                        "visible_ink_suppressed": record.get("visible_ink_suppressed"),
                        "visible_ink_metrics": record.get("visible_ink_metrics"),
                        "visible_after_second_pass": record.get("visible_after_second_pass"),
                        "verify_similarity": record.get("verify_similarity"),
                        "verify_ocr_text": record.get("verify_ocr_text"),
                        "verify_ocr_error": record.get("verify_ocr_error"),
                        "verify_patch_path": record.get("verify_patch_path"),
                        "verify_bbox": record.get("verify_bbox"),
                        "word_location": record.get("word_location"),
                        "crop_meta": record.get("crop_meta"),
                        "parent_patch_path": parent.get("patch_path"),
                        "parent_pymupdf_text": parent.get("pymupdf_text"),
                        "parent_ocr_text": parent.get("ocr_text"),
                    }
                )
    return rows


def _write_final_outputs(
    run_dir: Path,
    pdf_path: Path,
    results: list[RegionalResult],
    ocr_items: list[dict[str, Any]],
    gap_debug: list[dict[str, Any]],
    formula_debug: list[dict[str, Any]],
    picture_debug: list[dict[str, Any]],
    table_debug: list[dict[str, Any]],
    added_orphans: int,
    elapsed_seconds: float,
    device_summary: str,
) -> Path:
    """Write JSON, CSV, and the final report."""

    print("[6/7] Writing JSON and CSV outputs")
    write_json(run_dir / "ocr_items.json", ocr_items)
    write_json(
        run_dir / "matching_debug.json",
        {
            "pymupdf_blocks_file": "pymupdf_blocks.json",
            "pymupdf_words_file": "pymupdf_words.json",
            "ocr_items_file": "ocr_items.json",
            "layout_regions_file": "layout_regions.json",
            "gap_verification_results_file": "gap_verification_results.csv",
            "pymupdf_only_outside_docling_count": added_orphans,
            "gap_debug_count": len(gap_debug),
            "initial_gap_count": sum(len(item["initial_gaps"]) for item in gap_debug),
            "second_pass_verified_visible_count": sum(len(item["verified_visible_gaps"]) for item in gap_debug),
            "inline_math_suppressed_gap_count": sum(len(item.get("suppressed_inline_math_gaps", [])) for item in gap_debug),
            "visible_ink_suppressed_gap_count": sum(len(item.get("suppressed_visible_ink_gaps", [])) for item in gap_debug),
            "still_missing_gap_count": sum(len(item["still_missing_gaps"]) for item in gap_debug),
            "formula_debug_count": len(formula_debug),
            "picture_debug_count": len(picture_debug),
            "table_debug_count": len(table_debug),
            "formula_comparison_rule": "Compromise mode: Docling formula regions are scanned only for control-like instructions; TeX semantic comparison is disabled.",
            "picture_comparison_rule": "Compromise mode: Docling picture-like regions are trusted/debug-only unless overlaid PyMuPDF/Docling text contains control-like instructions that OCR does not recover.",
            "table_comparison_rule": "Compromise mode: Docling table regions and child cells are debug-only unless parser text contains hidden control-like instructions.",
            "gap_verification_rule": "PyMuPDF word bbox -> tight crop -> Docling OCR; visible gaps, inline-math-only gaps, and visible-ink OCR misses are suppressed.",
            "visible_ink_suppression_rule": "A still-missing gap with visible foreground ink in the tight crop and no control-like instruction is kept in debug as suppressed_visible_ink, not emitted as suspicious.",
            "inline_math_suppression_rule": "A still-missing gap with mostly math/formula symbols and no control-like instruction is kept in debug as suppressed_inline_math, not emitted as suspicious.",
            "formula_regions": formula_debug,
            "picture_regions": picture_debug,
            "table_regions": table_debug,
            "gap_candidates": gap_debug,
        },
    )
    write_dicts_csv(run_dir / "table_debug.csv", table_debug, TABLE_DEBUG_CSV_FIELDS)
    write_dicts_csv(
        run_dir / "gap_verification_results.csv",
        _flatten_gap_verification_rows(gap_debug),
        GAP_VERIFICATION_CSV_FIELDS,
    )
    write_json(run_dir / "regional_ocr_results.json", [asdict(item) for item in results])
    write_results_csv(run_dir / "regional_ocr_results.csv", results)
    write_results_csv(
        run_dir / "suspicious_regions.csv",
        [item for item in results if item.risk_type != "trusted"],
    )

    report = build_report(pdf_path, results, elapsed_seconds, device_summary)
    report_path = run_dir / "report.json"
    write_json(report_path, report)
    print(f"[7/7] Done: {report_path}")
    print(f"      Risk: {report['risk_level']} ({report['risk_score']:.4f})")
    return report_path


def scan_pdf(args: argparse.Namespace) -> Path:
    """Run the full PDF scan and return the report path."""

    started = time.time()
    pdf_path = _resolve_pdf_path(args.pdf)
    run_dir, pages_dir, patches_dir, visual_dir = _prepare_run_dirs(args.out, pdf_path)

    print(f"[1/7] Docling extracting layout regions: {pdf_path.name}")
    regions = parse_docling_layout(
        pdf_path=pdf_path,
        output_dir=run_dir,
        max_pages=args.max_pages,
        device=args.device,
        num_threads=args.num_threads,
    )

    print(f"[2/7] PyMuPDF extracting text inside {len(regions)} Docling regions")
    extract_pymupdf_region_text(pdf_path, regions)
    docling_regions = [region for region in regions if region.source == "docling_region"]
    pymupdf_blocks, pymupdf_words = collect_pymupdf_structures(pdf_path, docling_regions, args.max_pages)
    write_json(run_dir / "pymupdf_blocks.json", pymupdf_blocks)
    write_json(run_dir / "pymupdf_words.json", pymupdf_words)

    added_orphans = add_pymupdf_only_regions(pdf_path, regions, args.max_pages)
    print(f"      Added {added_orphans} PyMuPDF-only text candidates outside Docling regions")
    print(f"      Recorded {len(pymupdf_blocks)} PyMuPDF blocks and {len(pymupdf_words)} words")

    print(f"[3/7] Rendering pages and cropping {len(regions)} regions at {args.dpi} DPI")
    page_images = render_pages(pdf_path, pages_dir, args.dpi, args.max_pages)
    crop_region_patches(regions, page_images, patches_dir, args.dpi, args.padding)
    write_json(run_dir / "layout_regions.json", [asdict(region) for region in regions])

    if args.draw_bboxes:
        print("[4/7] Drawing bbox visualizations")
        draw_visualizations(regions, page_images, visual_dir, args.dpi)
    else:
        print("[4/7] Bbox visualization skipped")

    results, ocr_items, gap_debug, formula_debug, picture_debug, table_debug, device_summary = _run_regional_ocr_and_matching(
        regions=regions,
        pymupdf_words=pymupdf_words,
        page_images=page_images,
        patches_dir=patches_dir,
        dpi=args.dpi,
        padding=args.padding,
        device=args.device,
        num_threads=args.num_threads,
    )

    return _write_final_outputs(
        run_dir=run_dir,
        pdf_path=pdf_path,
        results=results,
        ocr_items=ocr_items,
        gap_debug=gap_debug,
        formula_debug=formula_debug,
        picture_debug=picture_debug,
        table_debug=table_debug,
        added_orphans=added_orphans,
        elapsed_seconds=time.time() - started,
        device_summary=device_summary,
    )

