"""Patch-level parallel orchestration for the regional PDF detector.

This module intentionally reuses the original detection_detail detector modules
and output writers.  The refactor is limited to orchestration: regional OCR
patches and second-pass gap verification patches are executed concurrently, then
merged back in the original region order for deterministic JSON/CSV output.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image


LEGACY_DIR = Path(__file__).resolve().parents[1] / "detection_detail"
if not LEGACY_DIR.is_dir():
    raise RuntimeError(f"Original detector folder not found: {LEGACY_DIR}")
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

from detector_docling import DoclingRegionalOCR, parse_docling_layout  # noqa: E402
from detector_formula import analyze_formula_region  # noqa: E402
from detector_images import (  # noqa: E402
    crop_pdf_bbox_to_image,
    draw_visualizations,
    render_pages,
)
from detector_io import compact_csv_text, write_json  # noqa: E402
from detector_matching import build_gap_result, make_region_result  # noqa: E402
from detector_models import LayoutRegion, RegionalResult  # noqa: E402
from detector_picture import analyze_picture_region  # noqa: E402
from detector_pipeline import (  # noqa: E402
    _attach_second_pass_summary,
    _flatten_gap_verification_rows,
    _is_formula_region,
    _is_picture_region,
    _mark_parent_as_context_row,
    _partition_suppressed_gaps,
    _prepare_run_dirs,
    _resolve_pdf_path,
    _write_final_outputs,
)
from detector_pymupdf import (  # noqa: E402
    add_pymupdf_only_regions,
    collect_pymupdf_structures,
    extract_pymupdf_region_text,
    locate_gap_bbox_from_words,
)
from detector_table import analyze_table_region, build_table_contexts, table_context_for_region  # noqa: E402
from detector_text import extract_control_snippets, extract_parser_only_gaps, ocr_verifies_gap  # noqa: E402
from batch_ocr import RapidOCRBatchRegionalOCR  # noqa: E402


@dataclass(frozen=True)
class ParallelPlan:
    """Resolved parallel execution settings for one scan."""

    patch_workers: int
    gap_workers: int
    ocr_threads_per_worker: int


@dataclass
class PendingGapParent:
    """A parent region whose parser-only spans need second-pass OCR."""

    entry: dict[str, Any]
    region: LayoutRegion
    region_result: RegionalResult
    ocr_text: str
    initial_gaps: list[dict[str, Any]]


@dataclass(frozen=True)
class GapTask:
    """One tight verification crop/OCR task."""

    parent_index: int
    gap_index: int
    gap: dict[str, Any]
    region_id: str
    page_path: Path
    verify_bbox: list[float]
    verify_patch: Path
    location: dict[str, Any]
    dpi: int
    padding_points: float
    device: str
    ocr_threads_per_worker: int


_OCR_STATE = threading.local()


def _auto_worker_count(requested: int | None, task_count: int, device: str) -> int:
    """Resolve requested/auto worker counts without exceeding task count."""

    if task_count <= 0:
        return 0
    if requested and requested > 0:
        return min(requested, task_count)

    cpu_count = os.cpu_count() or 4
    if device == "cuda":
        # CUDA model replicas can consume a lot of VRAM.  Keep auto conservative;
        # callers can raise --patch-workers explicitly after checking memory.
        default_workers = 1
    else:
        default_workers = min(8, max(1, cpu_count // 2))
    return min(default_workers, task_count)


def _resolve_parallel_plan(args: argparse.Namespace, patch_count: int) -> ParallelPlan:
    """Derive worker counts and per-worker thread budgets from CLI args."""

    patch_workers = _auto_worker_count(getattr(args, "patch_workers", 0), patch_count, args.device)
    gap_workers_requested = getattr(args, "gap_workers", 0)
    gap_workers = _auto_worker_count(gap_workers_requested, patch_count, args.device)

    explicit_threads = getattr(args, "ocr_threads_per_worker", None)
    if explicit_threads and explicit_threads > 0:
        per_worker_threads = explicit_threads
    elif args.device == "cuda":
        per_worker_threads = max(1, int(args.num_threads))
    else:
        per_worker_threads = max(1, int(args.num_threads) // max(1, patch_workers))

    return ParallelPlan(
        patch_workers=max(1, patch_workers),
        gap_workers=max(1, gap_workers),
        ocr_threads_per_worker=per_worker_threads,
    )


def _get_worker_ocr(device: str, num_threads: int) -> DoclingRegionalOCR:
    """Return a thread-local OCR recognizer for this worker."""

    cache = getattr(_OCR_STATE, "cache", None)
    if cache is None:
        cache = {}
        _OCR_STATE.cache = cache
    key = (device, num_threads)
    if key not in cache:
        cache[key] = DoclingRegionalOCR(device, num_threads)
    return cache[key]


def _recognize_patch_worker(
    index: int,
    patch_path: str,
    device: str,
    ocr_threads_per_worker: int,
) -> dict[str, Any]:
    """OCR one already-cropped region patch inside a worker thread."""

    started = time.time()
    ocr = _get_worker_ocr(device, ocr_threads_per_worker)
    ocr_text, ocr_error, ocr_records = ocr.recognize_one(Path(patch_path))
    return {
        "index": index,
        "patch_path": patch_path,
        "ocr_text": ocr_text,
        "ocr_error": ocr_error,
        "ocr_records": ocr_records,
        "device_summary": ocr.device_summary,
        "elapsed_seconds": round(time.time() - started, 4),
    }


def _progress_interval(total: int) -> int:
    """Return a human-friendly progress print cadence."""

    if total <= 20:
        return 5
    return max(10, total // 10)


def _ocr_region_patches_parallel(
    patch_regions: list[LayoutRegion],
    plan: ParallelPlan,
    device: str,
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    """Run primary OCR over region patches in parallel and restore order."""

    total = len(patch_regions)
    if not total:
        return [], device, {"primary_ocr_seconds": 0.0}

    print(
        "      Patch OCR workers: "
        f"{plan.patch_workers}; OCR threads/worker: {plan.ocr_threads_per_worker}"
    )
    started = time.time()
    done = 0
    interval = _progress_interval(total)
    results_by_index: dict[int, dict[str, Any]] = {}
    device_summary = device

    with ThreadPoolExecutor(max_workers=plan.patch_workers, thread_name_prefix="patch-ocr") as executor:
        futures = {
            executor.submit(
                _recognize_patch_worker,
                index,
                str(region.patch_path),
                device,
                plan.ocr_threads_per_worker,
            ): (index, region)
            for index, region in enumerate(patch_regions, start=1)
        }
        for future in as_completed(futures):
            index, region = futures[future]
            record = future.result()
            record["region"] = region
            results_by_index[index] = record
            if record.get("device_summary"):
                device_summary = record["device_summary"]
            done += 1
            if done == 1 or done % interval == 0 or done == total:
                print(f"      Primary OCR progress: {done}/{total}")

    ordered = [results_by_index[index] for index in range(1, total + 1)]
    stats = {"primary_ocr_seconds": round(time.time() - started, 3)}
    return ordered, device_summary, stats


def _ocr_region_patches_batched(
    patch_regions: list[LayoutRegion],
    recognizer: RapidOCRBatchRegionalOCR,
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    """Run primary OCR through one RapidOCR model with batched recognition."""

    total = len(patch_regions)
    if not total:
        return [], recognizer.device_summary, {"primary_ocr_seconds": 0.0, "ocr_mode": "batch"}

    print(
        "      Batch OCR mode: "
        f"one RapidOCR model; cls_batch={recognizer.cls_batch_size}; "
        f"rec_batch={recognizer.rec_batch_size}; patches={total}"
    )
    started = time.time()
    patch_paths = [Path(region.patch_path) for region in patch_regions if region.patch_path]
    batch_results, batch_stats = recognizer.recognize_many(patch_paths)

    results_by_index: dict[int, dict[str, Any]] = {}
    for result, region in zip(batch_results, patch_regions):
        record = asdict(result)
        record["region"] = region
        results_by_index[result.index] = record

    ordered = [results_by_index[index] for index in range(1, total + 1)]
    stats: dict[str, Any] = {"primary_ocr_seconds": round(time.time() - started, 3)}
    for key, value in batch_stats.items():
        if key in {"ocr_mode", "ocr_cls_batch_size", "ocr_rec_batch_size"}:
            stats[key] = value
        else:
            stats[f"primary_{key}"] = value
    print(
        "      Primary batch OCR complete: "
        f"{total} patches, {batch_stats.get('batch_line_count', 0)} text lines"
    )
    return ordered, recognizer.device_summary, stats
def _crop_bbox_from_open_image(
    image: Image.Image,
    bbox: list[float],
    output_path: Path,
    dpi: int,
    padding_points: float,
) -> dict[str, Any]:
    """Crop a PDF-point bbox from an already-open rendered page image."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72.0
    left = max(0, int((bbox[0] - padding_points) * scale))
    top = max(0, int((bbox[1] - padding_points) * scale))
    right = min(image.width, int((bbox[2] + padding_points) * scale + 0.999))
    bottom = min(image.height, int((bbox[3] + padding_points) * scale + 0.999))
    if right <= left or bottom <= top:
        raise ValueError(f"Empty crop bbox: {bbox}")
    image.crop((left, top, right, bottom)).save(output_path)
    return {
        "patch_pixel_bbox": [left, top, right, bottom],
        "patch_pdf_bbox": [
            round(left / scale, 3),
            round(top / scale, 3),
            round(right / scale, 3),
            round(bottom / scale, 3),
        ],
        "patch_size_px": [right - left, bottom - top],
        "render_dpi": dpi,
    }


def crop_region_patches_fast(
    regions: list[LayoutRegion],
    page_images: dict[int, Path],
    patches_dir: Path,
    dpi: int,
    padding_points: float,
) -> None:
    """Crop region patches while opening each rendered page only once."""

    patches_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[int, list[LayoutRegion]] = {}
    for region in regions:
        grouped.setdefault(region.page_no, []).append(region)

    for page_no in sorted(grouped):
        page_path = page_images.get(page_no)
        if not page_path:
            continue
        with Image.open(page_path) as image:
            for region in grouped[page_no]:
                safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "_", region.label)
                patch_path = patches_dir / f"{region.region_id}_p{region.page_no}_{safe_label}.png"
                try:
                    meta = _crop_bbox_from_open_image(image, region.bbox, patch_path, dpi, padding_points)
                except ValueError:
                    continue
                region.patch_path = patch_path.as_posix()
                region.extra.update(meta)


def _recognize_gap_worker(task: GapTask) -> dict[str, Any]:
    """Crop and OCR one tight parser-only gap patch."""

    try:
        crop_meta = crop_pdf_bbox_to_image(
            task.page_path,
            task.verify_bbox,
            task.verify_patch,
            task.dpi,
            task.padding_points,
        )
        ocr = _get_worker_ocr(task.device, task.ocr_threads_per_worker)
        verify_ocr_text, verify_error, _records = ocr.recognize_one(task.verify_patch)
    except Exception as exc:
        verify_ocr_text, verify_error, crop_meta = "", f"{type(exc).__name__}: {exc}", {}

    visible, verify_similarity = ocr_verifies_gap(task.gap["text"], verify_ocr_text)
    record = {
        **task.gap,
        "verify_bbox": task.verify_bbox,
        "verify_patch_path": task.verify_patch.as_posix(),
        "verify_ocr_text": compact_csv_text(verify_ocr_text),
        "verify_ocr_error": verify_error,
        "verify_similarity": verify_similarity,
        "visible_after_second_pass": visible,
        "word_location": {
            "match_strategy": task.location.get("match_strategy"),
            "search_scope": task.location.get("search_scope"),
            "word_window_similarity": task.location.get("word_window_similarity"),
            "matched_word_count": len(task.location.get("matched_words") or []),
        },
        "crop_meta": crop_meta,
    }
    return {
        "parent_index": task.parent_index,
        "gap_index": task.gap_index,
        "visible": visible,
        "record": record,
    }


def _make_locate_error_record(gap: dict[str, Any], error: str) -> dict[str, Any]:
    """Return a still-missing gap record when bbox lookup cannot complete."""

    return {
        **gap,
        "verify_bbox": None,
        "verify_patch_path": "",
        "verify_ocr_text": "",
        "verify_ocr_error": error,
        "verify_similarity": 0.0,
        "visible_after_second_pass": False,
        "word_location": {"error": error},
        "crop_meta": {},
    }


def _verify_gap_parents_parallel(
    parents: list[PendingGapParent],
    all_words: list[dict[str, Any]],
    page_images: dict[int, Path],
    patches_dir: Path,
    dpi: int,
    padding: float,
    plan: ParallelPlan,
    device: str,
) -> tuple[dict[int, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    """Run second-pass OCR for every parser-only gap as patch-level tasks."""

    started = time.time()
    empty = {
        index: {"verified_visible": [], "still_missing": []}
        for index in range(len(parents))
    }
    tasks: list[GapTask] = []

    for parent_index, parent in enumerate(parents):
        page_path = page_images.get(parent.region.page_no)
        if not page_path:
            empty[parent_index]["still_missing"].extend(parent.initial_gaps)
            continue
        for gap_index, gap in enumerate(parent.initial_gaps, start=1):
            try:
                location = locate_gap_bbox_from_words(all_words, parent.region, gap["text"])
                verify_bbox = [round(float(value), 3) for value in location["bbox"]]
            except Exception as exc:
                empty[parent_index]["still_missing"].append(
                    _make_locate_error_record(gap, f"{type(exc).__name__}: {exc}")
                )
                continue

            verify_patch = patches_dir / f"{parent.region.region_id}_gap{gap_index:02d}_verify.png"
            tasks.append(
                GapTask(
                    parent_index=parent_index,
                    gap_index=gap_index,
                    gap=gap,
                    region_id=parent.region.region_id,
                    page_path=page_path,
                    verify_bbox=verify_bbox,
                    verify_patch=verify_patch,
                    location=location,
                    dpi=dpi,
                    padding_points=padding,
                    device=device,
                    ocr_threads_per_worker=plan.ocr_threads_per_worker,
                )
            )

    total = len(tasks)
    if not total:
        return empty, {"gap_ocr_seconds": round(time.time() - started, 3), "gap_ocr_tasks": 0}

    gap_workers = min(plan.gap_workers, total)
    print(f"      Gap OCR workers: {gap_workers}; tight gap patches: {total}")
    done = 0
    interval = _progress_interval(total)

    with ThreadPoolExecutor(max_workers=gap_workers, thread_name_prefix="gap-ocr") as executor:
        futures = {executor.submit(_recognize_gap_worker, task): task for task in tasks}
        for future in as_completed(futures):
            result = future.result()
            parent_index = result["parent_index"]
            key = "verified_visible" if result["visible"] else "still_missing"
            empty[parent_index][key].append((result["gap_index"], result["record"]))
            done += 1
            if done == 1 or done % interval == 0 or done == total:
                print(f"      Gap OCR progress: {done}/{total}")

    ordered: dict[int, dict[str, list[dict[str, Any]]]] = {}
    for parent_index, data in empty.items():
        ordered[parent_index] = {
            "verified_visible": [
                record for _gap_index, record in sorted(data["verified_visible"], key=lambda item: item[0])
            ],
            "still_missing": [
                record if isinstance(record, dict) else record[1]
                for record in sorted(
                    data["still_missing"],
                    key=lambda item: item[0] if isinstance(item, tuple) else 0,
                )
            ],
        }
    stats = {
        "gap_ocr_seconds": round(time.time() - started, 3),
        "gap_ocr_tasks": total,
    }
    return ordered, stats


def _order_gap_verifications(
    raw: dict[int, dict[str, list[Any]]],
) -> dict[int, dict[str, list[dict[str, Any]]]]:
    """Normalize gap verification rows back into deterministic parent order."""

    ordered: dict[int, dict[str, list[dict[str, Any]]]] = {}
    for parent_index, data in raw.items():
        ordered[parent_index] = {
            "verified_visible": [
                record for _gap_index, record in sorted(data["verified_visible"], key=lambda item: item[0])
            ],
            "still_missing": [
                record if isinstance(record, dict) else record[1]
                for record in sorted(
                    data["still_missing"],
                    key=lambda item: item[0] if isinstance(item, tuple) else 0,
                )
            ],
        }
    return ordered


def _verify_gap_parents_batched(
    parents: list[PendingGapParent],
    all_words: list[dict[str, Any]],
    page_images: dict[int, Path],
    patches_dir: Path,
    dpi: int,
    padding: float,
    recognizer: RapidOCRBatchRegionalOCR,
) -> tuple[dict[int, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    """Run second-pass tight gap OCR with the same batched RapidOCR instance."""

    started = time.time()
    raw: dict[int, dict[str, list[Any]]] = {
        index: {"verified_visible": [], "still_missing": []}
        for index in range(len(parents))
    }
    tasks: list[GapTask] = []

    for parent_index, parent in enumerate(parents):
        page_path = page_images.get(parent.region.page_no)
        if not page_path:
            raw[parent_index]["still_missing"].extend(parent.initial_gaps)
            continue
        for gap_index, gap in enumerate(parent.initial_gaps, start=1):
            try:
                location = locate_gap_bbox_from_words(all_words, parent.region, gap["text"])
                verify_bbox = [round(float(value), 3) for value in location["bbox"]]
            except Exception as exc:
                raw[parent_index]["still_missing"].append(
                    _make_locate_error_record(gap, f"{type(exc).__name__}: {exc}")
                )
                continue

            verify_patch = patches_dir / f"{parent.region.region_id}_gap{gap_index:02d}_verify.png"
            tasks.append(
                GapTask(
                    parent_index=parent_index,
                    gap_index=gap_index,
                    gap=gap,
                    region_id=parent.region.region_id,
                    page_path=page_path,
                    verify_bbox=verify_bbox,
                    verify_patch=verify_patch,
                    location=location,
                    dpi=dpi,
                    padding_points=padding,
                    device=recognizer.device,
                    ocr_threads_per_worker=1,
                )
            )

    total = len(tasks)
    if not total:
        return _order_gap_verifications(raw), {
            "gap_ocr_seconds": round(time.time() - started, 3),
            "gap_ocr_tasks": 0,
        }

    print(f"      Gap batch OCR: tight gap patches={total}; shared RapidOCR model")
    crop_started = time.time()
    crop_metas: dict[tuple[int, int], dict[str, Any]] = {}
    crop_errors: dict[tuple[int, int], str] = {}
    grouped: dict[Path, list[GapTask]] = {}
    for task in tasks:
        grouped.setdefault(task.page_path, []).append(task)

    for page_path, page_tasks in grouped.items():
        try:
            with Image.open(page_path) as image:
                for task in page_tasks:
                    key = (task.parent_index, task.gap_index)
                    try:
                        crop_metas[key] = _crop_bbox_from_open_image(
                            image,
                            task.verify_bbox,
                            task.verify_patch,
                            task.dpi,
                            task.padding_points,
                        )
                    except Exception as exc:
                        crop_errors[key] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            for task in page_tasks:
                crop_errors[(task.parent_index, task.gap_index)] = f"{type(exc).__name__}: {exc}"

    ready_tasks = [
        task for task in tasks
        if (task.parent_index, task.gap_index) not in crop_errors
    ]
    for task in tasks:
        key = (task.parent_index, task.gap_index)
        if key not in crop_errors:
            continue
        record = {
            **task.gap,
            "verify_bbox": task.verify_bbox,
            "verify_patch_path": task.verify_patch.as_posix(),
            "verify_ocr_text": "",
            "verify_ocr_error": crop_errors[key],
            "verify_similarity": 0.0,
            "visible_after_second_pass": False,
            "word_location": {
                "match_strategy": task.location.get("match_strategy"),
                "search_scope": task.location.get("search_scope"),
                "word_window_similarity": task.location.get("word_window_similarity"),
                "matched_word_count": len(task.location.get("matched_words") or []),
            },
            "crop_meta": {},
        }
        raw[task.parent_index]["still_missing"].append((task.gap_index, record))

    crop_seconds = time.time() - crop_started
    batch_stats: dict[str, Any] = {}
    batch_results = []
    if ready_tasks:
        batch_results, batch_stats = recognizer.recognize_many([task.verify_patch for task in ready_tasks])

    for task, result in zip(ready_tasks, batch_results):
        visible, verify_similarity = ocr_verifies_gap(task.gap["text"], result.ocr_text)
        key = (task.parent_index, task.gap_index)
        record = {
            **task.gap,
            "verify_bbox": task.verify_bbox,
            "verify_patch_path": task.verify_patch.as_posix(),
            "verify_ocr_text": compact_csv_text(result.ocr_text),
            "verify_ocr_error": result.ocr_error,
            "verify_similarity": verify_similarity,
            "visible_after_second_pass": visible,
            "word_location": {
                "match_strategy": task.location.get("match_strategy"),
                "search_scope": task.location.get("search_scope"),
                "word_window_similarity": task.location.get("word_window_similarity"),
                "matched_word_count": len(task.location.get("matched_words") or []),
            },
            "crop_meta": crop_metas.get(key, {}),
        }
        target = "verified_visible" if visible else "still_missing"
        raw[task.parent_index][target].append((task.gap_index, record))

    stats: dict[str, Any] = {
        "gap_ocr_seconds": round(time.time() - started, 3),
        "gap_crop_seconds": round(crop_seconds, 3),
        "gap_ocr_tasks": total,
        "gap_ocr_ready_tasks": len(ready_tasks),
    }
    for key, value in batch_stats.items():
        if key not in {"ocr_mode", "ocr_cls_batch_size", "ocr_rec_batch_size"}:
            stats[f"gap_{key}"] = value
    return _order_gap_verifications(raw), stats
def _finalize_gap_parent(
    parent: PendingGapParent,
    verification: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Update one parent row and return its debug record."""

    verified_visible = verification.get("verified_visible", [])
    still_missing = verification.get("still_missing", [])
    reportable, suppressed_inline_math, suppressed_visible_ink = _partition_suppressed_gaps(still_missing)

    _attach_second_pass_summary(
        parent.region_result,
        verified_visible + reportable + suppressed_inline_math + suppressed_visible_ink,
    )
    _mark_parent_as_context_row(
        parent.region_result,
        still_missing=bool(reportable),
        inline_math_suppressed=bool(suppressed_inline_math),
        visible_ink_suppressed=bool(suppressed_visible_ink),
    )

    emitted_results: list[RegionalResult] = []
    if reportable:
        emitted_results.append(build_gap_result(parent.region, reportable, reportable))
    parent.entry["results"].extend(emitted_results)

    return {
        "parent_region_id": parent.region.region_id,
        "page_no": parent.region.page_no,
        "parent_label": parent.region.label,
        "parent_bbox": parent.region.bbox,
        "patch_path": parent.region.patch_path,
        "initial_gaps": parent.initial_gaps,
        "verified_visible_gaps": verified_visible,
        "suppressed_inline_math_gaps": suppressed_inline_math,
        "suppressed_visible_ink_gaps": suppressed_visible_ink,
        "still_missing_gaps": reportable,
        "control_snippets": extract_control_snippets(" | ".join(gap["text"] for gap in reportable)),
        "pymupdf_text": parent.region.pymupdf_text or parent.region.docling_text,
        "ocr_text": parent.ocr_text,
        "emitted_gap_region_ids": [item.region_id for item in emitted_results],
    }


def _run_regional_ocr_and_matching_parallel(
    regions: list[LayoutRegion],
    pymupdf_words: list[dict[str, Any]],
    page_images: dict[int, Path],
    patches_dir: Path,
    dpi: int,
    padding: float,
    device: str,
    plan: ParallelPlan,
    ocr_mode: str = "batch",
    ocr_cls_batch_size: int = 32,
    ocr_rec_batch_size: int = 64,
    batch_recognizer: RapidOCRBatchRegionalOCR | None = None,
) -> tuple[
    list[RegionalResult],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    str,
    dict[str, Any],
]:
    """OCR patches concurrently, compare, then verify gap patches concurrently."""

    patch_regions = [region for region in regions if region.patch_path]
    table_contexts = build_table_contexts(patch_regions)
    print(f"[5/7] Patch-parallel regional OCR: {len(patch_regions)} patches")

    if any(_is_formula_region(region) for region in patch_regions):
        print("      Formula mode: intent-only scan; TeX/formula semantic comparison disabled")
    if any(_is_picture_region(region) for region in patch_regions):
        print("      Picture mode: picture-like regions are trusted/debug-only in this version")
    if table_contexts:
        print(f"      Table mode: {len(table_contexts)} table bbox(es); table cells are control-only suspicious")

    ocr_init_seconds = 0.0
    if ocr_mode == "batch":
        if batch_recognizer is None:
            init_started = time.time()
            batch_recognizer = RapidOCRBatchRegionalOCR(
                device=device,
                cls_batch_size=ocr_cls_batch_size,
                rec_batch_size=ocr_rec_batch_size,
            )
            ocr_init_seconds = time.time() - init_started
        ocr_results, device_summary, ocr_stats = _ocr_region_patches_batched(
            patch_regions,
            batch_recognizer,
        )
    else:
        ocr_results, device_summary, ocr_stats = _ocr_region_patches_parallel(patch_regions, plan, device)

    ordered_entries: list[dict[str, Any]] = []
    pending_gap_parents: list[PendingGapParent] = []
    ocr_items: list[dict[str, Any]] = []
    gap_debug: list[dict[str, Any]] = []
    formula_debug: list[dict[str, Any]] = []
    picture_debug: list[dict[str, Any]] = []
    table_debug: list[dict[str, Any]] = []
    formula_recognizer = None

    for record in ocr_results:
        region = record["region"]
        ocr_text = record["ocr_text"]
        ocr_error = record["ocr_error"]
        ocr_items.extend(_enrich_ocr_records_local(region, record["ocr_records"]))
        table_context = table_context_for_region(region, table_contexts)

        if _is_formula_region(region):
            region_result, formula_record = analyze_formula_region(region, ocr_text, ocr_error, formula_recognizer)
            entry = {"results": [region_result]}
            ordered_entries.append(entry)
            formula_debug.append(formula_record)
        elif _is_picture_region(region):
            region_result, picture_record = analyze_picture_region(region, ocr_text, ocr_error)
            entry = {"results": [region_result]}
            ordered_entries.append(entry)
            picture_debug.append(picture_record)
        elif table_context:
            region_result, table_record = analyze_table_region(region, ocr_text, ocr_error, table_context)
            entry = {"results": [region_result]}
            ordered_entries.append(entry)
            table_debug.append(table_record)
        else:
            region_result = make_region_result(region, ocr_text, ocr_error)
            entry = {"results": [region_result]}
            ordered_entries.append(entry)

            if region.source == "docling_region":
                parser_text = region.pymupdf_text or region.docling_text
                initial_gaps = extract_parser_only_gaps(parser_text, ocr_text)
                if initial_gaps:
                    pending_gap_parents.append(
                        PendingGapParent(
                            entry=entry,
                            region=region,
                            region_result=region_result,
                            ocr_text=ocr_text,
                            initial_gaps=initial_gaps,
                        )
                    )

    if batch_recognizer is not None:
        gap_verifications, gap_stats = _verify_gap_parents_batched(
            pending_gap_parents,
            all_words=pymupdf_words,
            page_images=page_images,
            patches_dir=patches_dir,
            dpi=dpi,
            padding=padding,
            recognizer=batch_recognizer,
        )
    else:
        gap_verifications, gap_stats = _verify_gap_parents_parallel(
            pending_gap_parents,
            all_words=pymupdf_words,
            page_images=page_images,
            patches_dir=patches_dir,
            dpi=dpi,
            padding=padding,
            plan=plan,
            device=device,
        )
    for index, parent in enumerate(pending_gap_parents):
        gap_debug.append(_finalize_gap_parent(parent, gap_verifications[index]))

    results = [result for entry in ordered_entries for result in entry["results"]]
    if ocr_mode == "batch":
        ocr_stats["ocr_init_seconds"] = round(ocr_init_seconds, 3)

    stats = {
        **ocr_stats,
        **gap_stats,
        "patch_workers": plan.patch_workers,
        "gap_workers": plan.gap_workers,
        "ocr_threads_per_worker": plan.ocr_threads_per_worker,
        "ocr_mode": ocr_mode,
        "primary_patch_count": len(patch_regions),
        "gap_parent_count": len(pending_gap_parents),
    }
    if ocr_mode == "batch":
        device_summary = (
            f"{device_summary}; ocr_mode=batch; cls_batch={ocr_cls_batch_size}; "
            f"rec_batch={ocr_rec_batch_size}"
        )
    else:
        device_summary = (
            f"{device_summary}; patch_workers={plan.patch_workers}; "
            f"gap_workers={plan.gap_workers}; ocr_threads_per_worker={plan.ocr_threads_per_worker}"
        )
    return results, ocr_items, gap_debug, formula_debug, picture_debug, table_debug, device_summary, stats


def _enrich_ocr_records_local(region: LayoutRegion, ocr_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach region metadata to OCR records.

    Kept local to avoid importing the original private helper through more of
    detector_pipeline than necessary.
    """

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


def scan_pdf_parallel(args: argparse.Namespace, batch_recognizer: RapidOCRBatchRegionalOCR | None = None) -> Path:
    """Run the patch-parallel PDF scan and return the report path."""

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

    plan = _resolve_parallel_plan(args, len(regions))
    print(
        "      Parallel plan: "
        f"patch_workers={plan.patch_workers}, gap_workers={plan.gap_workers}, "
        f"ocr_threads_per_worker={plan.ocr_threads_per_worker}"
    )

    print(f"[3/7] Rendering pages and fast-cropping {len(regions)} regions at {args.dpi} DPI")
    page_images = render_pages(pdf_path, pages_dir, args.dpi, args.max_pages)
    crop_region_patches_fast(regions, page_images, patches_dir, args.dpi, args.padding)
    write_json(run_dir / "layout_regions.json", [asdict(region) for region in regions])

    if args.draw_bboxes:
        print("[4/7] Drawing bbox visualizations")
        draw_visualizations(regions, page_images, visual_dir, args.dpi)
    else:
        print("[4/7] Bbox visualization skipped")

    (
        results,
        ocr_items,
        gap_debug,
        formula_debug,
        picture_debug,
        table_debug,
        device_summary,
        runtime_stats,
    ) = _run_regional_ocr_and_matching_parallel(
        regions=regions,
        pymupdf_words=pymupdf_words,
        page_images=page_images,
        patches_dir=patches_dir,
        dpi=args.dpi,
        padding=args.padding,
        device=args.device,
        plan=plan,
        ocr_mode=getattr(args, "ocr_mode", "batch"),
        ocr_cls_batch_size=getattr(args, "ocr_cls_batch_size", 32),
        ocr_rec_batch_size=getattr(args, "ocr_rec_batch_size", 64),
        batch_recognizer=batch_recognizer,
    )
    runtime_stats["total_elapsed_before_write_seconds"] = round(time.time() - started, 3)
    write_json(run_dir / "parallel_runtime.json", runtime_stats)

    report_path = _write_final_outputs(
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
    if getattr(args, "ocr_mode", "batch") == "batch":
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["regional_ocr"] = "RapidOCR direct batch inference (torch backend)"
        report["gap_verification"] = "PyMuPDF word bbox -> tight crop -> second-pass RapidOCR batch inference"
        write_json(report_path, report)
    return report_path

