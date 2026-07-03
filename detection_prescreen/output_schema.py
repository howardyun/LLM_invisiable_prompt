"""Flat CSV output schema for large-scale PDF pre-screen batches."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


DOCUMENT_FIELDS = [
    "batch_index",
    "doc_id",
    "pdf_name",
    "pdf_path",
    "relative_path",
    "file_size_bytes",
    "file_mtime_epoch",
    "status",
    "error",
    "mode",
    "page_count_scanned",
    "ocg_count",
    "risk_level",
    "risk_score",
    "should_run_ocr",
    "candidate_count",
    "ocr_candidate_count",
    "verified_hidden_count",
    "visible_ocr_count",
    "candidate_kinds",
    "candidate_sources",
    "control_groups",
    "candidate_pages",
    "top_candidate_id",
    "top_candidate_page",
    "top_candidate_kind",
    "top_candidate_score",
    "top_candidate_needs_ocr",
    "top_candidate_source",
    "top_candidate_control_groups",
    "top_candidate_reason",
    "top_candidate_text",
    "prescreen_elapsed_seconds",
    "ocr_elapsed_seconds",
    "total_elapsed_seconds",
    "report_path",
    "ocr_report_path",
]


DETECTION_FIELDS = [
    "batch_index",
    "doc_id",
    "pdf_name",
    "pdf_path",
    "relative_path",
    "candidate_global_id",
    "candidate_id",
    "page_no",
    "kind",
    "source",
    "score",
    "needs_ocr",
    "control_group_count",
    "control_groups",
    "control_snippets",
    "reason",
    "text",
    "bbox",
    "font_size",
    "font",
    "color_rgb",
    "alpha",
    "hidden_style_span_count",
    "ocr_ran",
    "ocr_similarity",
    "visible_in_ocr",
    "verified_hidden",
    "ocr_text",
    "patch_path",
    "ocr_error",
]


PAGE_FIELDS = [
    "batch_index",
    "doc_id",
    "pdf_name",
    "pdf_path",
    "relative_path",
    "page_no",
    "candidate_count",
    "text_chars",
    "text_words",
]


class CsvTableWriter:
    """Small append-only CSV writer with a stable header."""

    def __init__(self, path: Path, fieldnames: list[str]):
        self.path = Path(path)
        self.fieldnames = fieldnames
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8-sig", newline="")
        self._writer = csv.DictWriter(self._handle, fieldnames=self.fieldnames)
        self._writer.writeheader()

    def writerow(self, row: dict[str, Any]) -> None:
        self._writer.writerow({field: row.get(field, "") for field in self.fieldnames})
        self._handle.flush()

    def writerows(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self._writer.writerow({field: row.get(field, "") for field in self.fieldnames})
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> "CsvTableWriter":
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self.close()


def make_doc_id(index: int) -> str:
    return f"doc_{index:08d}"


def should_save_per_pdf(output_layout: str) -> bool:
    return output_layout in {"legacy", "both"}


def relative_path_for(pdf_path: Path, input_dir: Path) -> str:
    try:
        return Path(pdf_path).resolve().relative_to(Path(input_dir).resolve()).as_posix()
    except Exception:
        return Path(pdf_path).name


def build_document_row(
    *,
    index: int,
    doc_id: str,
    pdf_path: Path,
    input_dir: Path,
    status: str,
    error: str = "",
    report: dict[str, Any] | None = None,
    ocr_report: dict[str, Any] | None = None,
    prescreen_elapsed_seconds: Any = "",
    ocr_elapsed_seconds: Any = "",
    total_elapsed_seconds: Any = "",
    report_path: str = "",
    ocr_report_path: str = "",
) -> dict[str, Any]:
    pdf_path = Path(pdf_path).expanduser().resolve()
    stat = _safe_stat(pdf_path)
    candidates = list((report or {}).get("candidates", []) or [])
    top = _top_candidate(candidates)
    ocr_report = ocr_report or {}
    return {
        "batch_index": index,
        "doc_id": doc_id,
        "pdf_name": pdf_path.name,
        "pdf_path": str(pdf_path),
        "relative_path": relative_path_for(pdf_path, input_dir),
        "file_size_bytes": stat.get("size", ""),
        "file_mtime_epoch": stat.get("mtime", ""),
        "status": status,
        "error": error,
        "mode": (report or {}).get("mode", ""),
        "page_count_scanned": (report or {}).get("page_count_scanned", ""),
        "ocg_count": (report or {}).get("ocg_count", ""),
        "risk_level": (report or {}).get("risk_level", ""),
        "risk_score": (report or {}).get("risk_score", ""),
        "should_run_ocr": (report or {}).get("should_run_ocr", ""),
        "candidate_count": (report or {}).get("candidate_count", 0 if report else ""),
        "ocr_candidate_count": (report or {}).get("ocr_candidate_count", 0 if report else ""),
        "verified_hidden_count": ocr_report.get("verified_hidden_count", 0 if report else ""),
        "visible_ocr_count": ocr_report.get("visible_count", 0 if report else ""),
        "candidate_kinds": _counted_values(candidate.get("kind") for candidate in candidates),
        "candidate_sources": _counted_values(candidate.get("source") for candidate in candidates),
        "control_groups": _joined_unique(_control_groups(candidates)),
        "candidate_pages": _joined_unique(candidate.get("page_no") for candidate in candidates if candidate.get("page_no")),
        "top_candidate_id": top.get("candidate_id", ""),
        "top_candidate_page": top.get("page_no", ""),
        "top_candidate_kind": top.get("kind", ""),
        "top_candidate_score": top.get("score", ""),
        "top_candidate_needs_ocr": top.get("needs_ocr", ""),
        "top_candidate_source": top.get("source", ""),
        "top_candidate_control_groups": _joined_unique(_control_groups([top])) if top else "",
        "top_candidate_reason": _csv_text(" | ".join(str(item) for item in top.get("reason", []) or [])),
        "top_candidate_text": _csv_text(top.get("text", ""), limit=1200),
        "prescreen_elapsed_seconds": prescreen_elapsed_seconds or (report or {}).get("elapsed_seconds", ""),
        "ocr_elapsed_seconds": ocr_elapsed_seconds or ocr_report.get("elapsed_seconds", ""),
        "total_elapsed_seconds": total_elapsed_seconds,
        "report_path": report_path,
        "ocr_report_path": ocr_report_path,
    }


def build_detection_rows(
    *,
    index: int,
    doc_id: str,
    pdf_path: Path,
    input_dir: Path,
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    pdf_path = Path(pdf_path).expanduser().resolve()
    base = {
        "batch_index": index,
        "doc_id": doc_id,
        "pdf_name": pdf_path.name,
        "pdf_path": str(pdf_path),
        "relative_path": relative_path_for(pdf_path, input_dir),
    }
    rows: list[dict[str, Any]] = []
    for candidate in report.get("candidates", []) or []:
        candidate_id = str(candidate.get("candidate_id") or "")
        groups = _control_groups([candidate])
        rows.append(
            {
                **base,
                "candidate_global_id": f"{doc_id}:{candidate_id}",
                "candidate_id": candidate_id,
                "page_no": candidate.get("page_no", ""),
                "kind": candidate.get("kind", ""),
                "source": candidate.get("source", ""),
                "score": candidate.get("score", ""),
                "needs_ocr": candidate.get("needs_ocr", ""),
                "control_group_count": len(set(groups)),
                "control_groups": _joined_unique(groups),
                "control_snippets": _csv_text(
                    " | ".join(
                        str(item.get("text") or "")
                        for item in candidate.get("control_snippets", []) or []
                        if isinstance(item, dict)
                    ),
                    limit=1500,
                ),
                "reason": _csv_text(" | ".join(str(item) for item in candidate.get("reason", []) or []), limit=1200),
                "text": _csv_text(candidate.get("text", ""), limit=1500),
                "bbox": _json_cell(candidate.get("bbox")),
                "font_size": candidate.get("font_size", ""),
                "font": candidate.get("font", ""),
                "color_rgb": _json_cell(candidate.get("color_rgb")),
                "alpha": candidate.get("alpha", ""),
                "hidden_style_span_count": (candidate.get("extra") or {}).get("hidden_style_span_count", ""),
                "ocr_ran": False,
                "ocr_similarity": "",
                "visible_in_ocr": "",
                "verified_hidden": "",
                "ocr_text": "",
                "patch_path": "",
                "ocr_error": "",
            }
        )
    return rows


def merge_ocr_into_detection_rows(
    detection_rows: list[dict[str, Any]],
    ocr_report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not ocr_report:
        return detection_rows
    by_candidate_id = {
        str(row.get("candidate_id")): row
        for row in ocr_report.get("results", []) or []
        if row.get("candidate_id") is not None
    }
    merged: list[dict[str, Any]] = []
    for row in detection_rows:
        out = dict(row)
        ocr = by_candidate_id.get(str(row.get("candidate_id")))
        if ocr:
            out.update(
                {
                    "ocr_ran": True,
                    "ocr_similarity": ocr.get("ocr_similarity", ""),
                    "visible_in_ocr": ocr.get("visible_in_ocr", ""),
                    "verified_hidden": ocr.get("verified_hidden", ""),
                    "ocr_text": _csv_text(ocr.get("ocr_text", ""), limit=1500),
                    "patch_path": ocr.get("patch_path", ""),
                    "ocr_error": ocr.get("ocr_error", ""),
                }
            )
        merged.append(out)
    return merged


def build_page_rows(
    *,
    index: int,
    doc_id: str,
    pdf_path: Path,
    input_dir: Path,
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    pdf_path = Path(pdf_path).expanduser().resolve()
    base = {
        "batch_index": index,
        "doc_id": doc_id,
        "pdf_name": pdf_path.name,
        "pdf_path": str(pdf_path),
        "relative_path": relative_path_for(pdf_path, input_dir),
    }
    return [{**base, **page} for page in report.get("page_stats", []) or []]


def _safe_stat(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
        return {"size": stat.st_size, "mtime": int(stat.st_mtime)}
    except Exception:
        return {}


def _top_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if not candidates:
        return {}
    return max(candidates, key=lambda item: float(item.get("score") or 0.0))


def _control_groups(candidates: list[dict[str, Any]]) -> list[Any]:
    groups: list[Any] = []
    for candidate in candidates:
        for snippet in candidate.get("control_snippets", []) or []:
            if isinstance(snippet, dict):
                groups.append(snippet.get("group"))
    return groups


def _counted_values(values: Any) -> str:
    counts: dict[str, int] = {}
    for value in values:
        if value in (None, ""):
            continue
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return " | ".join(f"{key}:{counts[key]}" for key in sorted(counts))


def _joined_unique(values: Any) -> str:
    normalized = sorted({str(value) for value in values if value not in (None, "")})
    return " | ".join(normalized)


def _json_cell(value: Any) -> str:
    if value in (None, ""):
        return ""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _csv_text(text: Any, limit: int = 2000) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."
