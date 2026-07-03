"""OCR verification for pre-screen candidates only."""

from __future__ import annotations

import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import fitz


ROOT_DIR = Path(__file__).resolve().parents[1]
PARALLEL_DIR = ROOT_DIR / "detection_detail_parallel"
if str(PARALLEL_DIR) not in sys.path:
    sys.path.insert(0, str(PARALLEL_DIR))

from batch_ocr import RapidOCRBatchRegionalOCR  # noqa: E402
from rapidfuzz import fuzz  # noqa: E402
try:
    from .prescreen_patterns import compute_partial_similarity, compute_similarity, normalize_text  # noqa: E402
except ImportError:
    from prescreen_patterns import compute_partial_similarity, compute_similarity, normalize_text  # noqa: E402


OCR_CSV_FIELDS = [
    "candidate_id",
    "page_no",
    "kind",
    "candidate_score",
    "ocr_similarity",
    "visible_in_ocr",
    "verified_hidden",
    "text",
    "ocr_text",
    "patch_path",
    "bbox",
    "reason",
]


def verify_candidates_with_ocr(
    pdf_path: Path,
    candidates: list[dict[str, Any]],
    out_dir: Path,
    recognizer: RapidOCRBatchRegionalOCR | None,
    device: str = "cuda",
    dpi: int = 180,
    padding: float = 3.0,
    cls_batch_size: int = 32,
    rec_batch_size: int = 64,
    max_candidates: int = 50,
) -> tuple[dict[str, Any], RapidOCRBatchRegionalOCR]:
    """Crop and OCR only selected pre-screen candidates."""

    started = time.time()
    selected = [item for item in candidates if item.get("needs_ocr")]
    selected = sorted(selected, key=lambda item: float(item.get("score") or 0.0), reverse=True)[:max_candidates]
    out_dir.mkdir(parents=True, exist_ok=True)
    patches_dir = out_dir / "ocr_candidate_patches"
    patches_dir.mkdir(parents=True, exist_ok=True)

    if recognizer is None:
        recognizer = RapidOCRBatchRegionalOCR(
            device=device,
            cls_batch_size=cls_batch_size,
            rec_batch_size=rec_batch_size,
        )

    crop_records = _crop_candidate_patches(pdf_path, selected, patches_dir, dpi, padding)
    ready = [record for record in crop_records if record.get("patch_path")]
    patch_paths = [Path(record["patch_path"]) for record in ready]
    ocr_results, ocr_stats = recognizer.recognize_many(patch_paths) if patch_paths else ([], {})

    rows: list[dict[str, Any]] = []
    for record, result in zip(ready, ocr_results):
        candidate = record["candidate"]
        target_text = _target_text(candidate)
        similarity = _ocr_similarity(target_text, result.ocr_text)
        visible = similarity >= 0.72
        has_control = bool(candidate.get("control_snippets"))
        verified_hidden = has_control and not visible
        rows.append(
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
                "patch_path": record.get("patch_path"),
                "bbox": record.get("bbox"),
                "reason": candidate.get("reason") or [],
                "ocr_error": result.ocr_error,
            }
        )

    failed_crops = [record for record in crop_records if not record.get("patch_path")]
    for record in failed_crops:
        candidate = record["candidate"]
        rows.append(
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

    verified_hidden_count = sum(bool(row.get("verified_hidden")) for row in rows)
    report = {
        "pdf_path": str(Path(pdf_path).resolve()),
        "mode": "ocr_candidate_verification",
        "elapsed_seconds": round(time.time() - started, 4),
        "candidate_count": len(selected),
        "verified_hidden_count": verified_hidden_count,
        "visible_count": sum(bool(row.get("visible_in_ocr")) for row in rows),
        "risk_level": "High" if verified_hidden_count else ("Medium" if rows else "Low"),
        "ocr_stats": ocr_stats,
        "results": rows,
    }
    write_ocr_outputs(out_dir, report)
    return report, recognizer


def write_ocr_outputs(out_dir: Path, report: dict[str, Any]) -> None:
    (out_dir / "ocr_verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (out_dir / "ocr_verification.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OCR_CSV_FIELDS)
        writer.writeheader()
        for row in report.get("results", []):
            writer.writerow(
                {
                    "candidate_id": row.get("candidate_id", ""),
                    "page_no": row.get("page_no", ""),
                    "kind": row.get("kind", ""),
                    "candidate_score": row.get("candidate_score", ""),
                    "ocr_similarity": row.get("ocr_similarity", ""),
                    "visible_in_ocr": row.get("visible_in_ocr", ""),
                    "verified_hidden": row.get("verified_hidden", ""),
                    "text": _csv_text(row.get("text", "")),
                    "ocr_text": _csv_text(row.get("ocr_text", "")),
                    "patch_path": row.get("patch_path", ""),
                    "bbox": json.dumps(row.get("bbox"), ensure_ascii=False),
                    "reason": _csv_text(" | ".join(str(item) for item in row.get("reason", []))),
                }
            )


def _crop_candidate_patches(
    pdf_path: Path,
    candidates: list[dict[str, Any]],
    patches_dir: Path,
    dpi: int,
    padding: float,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    scale = dpi / 72.0
    by_page: dict[int, list[dict[str, Any]]] = {}
    for candidate in candidates:
        page_no = int(candidate.get("page_no") or 0)
        if page_no > 0:
            by_page.setdefault(page_no, []).append(candidate)

    with fitz.open(pdf_path) as doc:
        for page_no, page_candidates in by_page.items():
            if page_no < 1 or page_no > len(doc):
                for candidate in page_candidates:
                    records.append({"candidate": candidate, "error": "page out of range"})
                continue
            page = doc[page_no - 1]
            matrix = fitz.Matrix(scale, scale)
            for candidate in page_candidates:
                try:
                    rect = _candidate_rect(candidate, page.rect, padding)
                    pix = page.get_pixmap(matrix=matrix, clip=rect, alpha=False)
                    patch_path = patches_dir / f"{candidate.get('candidate_id')}_p{page_no}.png"
                    pix.save(patch_path)
                    records.append(
                        {
                            "candidate": candidate,
                            "patch_path": patch_path.as_posix(),
                            "bbox": [round(rect.x0, 3), round(rect.y0, 3), round(rect.x1, 3), round(rect.y1, 3)],
                        }
                    )
                except Exception as exc:
                    records.append({"candidate": candidate, "error": f"{type(exc).__name__}: {exc}"})
    return records


def _candidate_rect(candidate: dict[str, Any], page_rect: fitz.Rect, padding: float) -> fitz.Rect:
    bbox = candidate.get("bbox")
    if isinstance(bbox, list) and len(bbox) == 4:
        rect = fitz.Rect(*[float(value) for value in bbox])
    else:
        rect = fitz.Rect(page_rect)
    rect = fitz.Rect(
        rect.x0 - padding,
        rect.y0 - padding,
        rect.x1 + padding,
        rect.y1 + padding,
    )
    rect = rect & page_rect
    if rect.is_empty or rect.is_infinite:
        rect = fitz.Rect(page_rect)
    return rect


def _target_text(candidate: dict[str, Any]) -> str:
    snippets = candidate.get("control_snippets") or []
    snippet_text = " ".join(str(item.get("text") or "") for item in snippets if isinstance(item, dict)).strip()
    if snippet_text:
        return snippet_text
    return re.sub(r"\s+", " ", str(candidate.get("text") or "")).strip()


def _ocr_similarity(target_text: str, ocr_text: str) -> float:
    if not target_text and not ocr_text:
        return 1.0
    if not target_text or not ocr_text:
        return 0.0

    target_norm = normalize_text(target_text)
    ocr_norm = normalize_text(ocr_text)
    if target_norm and target_norm in ocr_norm:
        return 1.0

    target_tokens = target_norm.split()
    ocr_tokens = ocr_norm.split()
    if len(target_tokens) >= 3 and ocr_tokens:
        return _ordered_window_similarity(target_tokens, ocr_tokens)

    return max(compute_similarity(target_text, ocr_text), compute_partial_similarity(target_text, ocr_text))


def _ordered_window_similarity(target_tokens: list[str], ocr_tokens: list[str]) -> float:
    target = " ".join(target_tokens)
    target_len = len(target_tokens)
    best = 0.0
    min_window = max(1, target_len - 1)
    max_window = min(len(ocr_tokens), target_len + 3)
    for window_size in range(min_window, max_window + 1):
        for start in range(0, len(ocr_tokens) - window_size + 1):
            window = " ".join(ocr_tokens[start : start + window_size])
            score = fuzz.ratio(target, window) / 100.0
            if score > best:
                best = score
    return best


def _csv_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()
