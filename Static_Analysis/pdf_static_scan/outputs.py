from __future__ import annotations

import csv
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, TextIO

from .utils import dumps_json, write_json

CONTROL_INTENT_CSV_MIN_SCORE = 0.4

FINDING_CSV_FIELDS = [
    "path",
    "sha256",
    "loader",
    "page_id",
    "object_type",
    "source",
    "control_intent_score",
    "text_preview",
    "matched_phrases",
    "matched_actions",
    "matched_roles",
    "error",
]

PROBLEM_SENTENCE_CSV_FIELDS = [
    "path",
    "sha256",
    "loader",
    "page_id",
    "sentence",
    "control_intent_score",
    "matched_phrases",
    "matched_actions",
    "matched_roles",
    "object_id",
    "object_type",
]


def write_json_report(report: Dict[str, Any] | List[Dict[str, Any]], output_path: str) -> None:
    write_json(output_path, report, pretty=True)


def append_jsonl_reports(reports: Iterable[Dict[str, Any]], output_path: str) -> int:
    count = 0
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for report in reports:
            handle.write(dumps_json(report, pretty=False))
            handle.write("\n")
            count += 1
    return count


def write_csv_summary(reports: Iterable[Dict[str, Any]], output_path: str) -> None:
    write_csv_rows([summary_row(report) for report in reports], output_path)


def write_csv_rows(rows: Iterable[Dict[str, Any]], output_path: str) -> None:
    row_list = list(rows)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        write_summary_csv(row_list, handle)


def write_summary_csv(rows: Iterable[Dict[str, Any]], handle: TextIO | None = None) -> None:
    fieldnames = [
        "path",
        "sha256",
        "page_count",
        "size_bytes",
        "loader",
        "scan_time_ms",
        "object_count",
        "text_span_count",
        "metadata_count",
        "annotation_count",
        "form_count",
        "ocg_count",
        "embedded_file_count",
        "signature_present",
        "finding_count",
        "critical_count",
        "high_count",
        "medium_count",
        "low_count",
        "max_risk_score",
        "risk_types",
        "error",
    ]
    output = handle or sys.stdout
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)


def write_findings_csv(reports: Iterable[Dict[str, Any]], output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        write_findings_csv_stream(reports, handle)


def write_findings_csv_stream(reports: Iterable[Dict[str, Any]], handle: TextIO | None = None) -> None:
    output = handle or sys.stdout
    writer = csv.DictWriter(output, fieldnames=FINDING_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for report in reports:
        rows = finding_rows(report)
        if rows:
            writer.writerows(rows)
        elif report.get("errors"):
            writer.writerow(error_finding_row(report))


def write_problem_sentences_csv(reports: Iterable[Dict[str, Any]], output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        write_problem_sentences_csv_stream(reports, handle)


def write_problem_sentences_csv_stream(reports: Iterable[Dict[str, Any]], handle: TextIO | None = None) -> None:
    output = handle or sys.stdout
    writer = csv.DictWriter(output, fieldnames=PROBLEM_SENTENCE_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    seen: set[tuple[str, str, str, str]] = set()
    for report in reports:
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
            writer.writerow(row)


def summary_row(report: Dict[str, Any]) -> Dict[str, Any]:
    file_info = report.get("file", {})
    summary = report.get("summary", {})
    stats = report.get("object_stats", {})
    findings = [item for item in report.get("findings", []) if _is_control_intent_output_row(item)]
    severity_counts: Dict[str, int] = {}
    for finding in findings:
        severity = str(finding.get("severity") or "")
        if severity:
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
    risk_types = sorted({str(item.get("risk_type")) for item in findings if item.get("risk_type")})
    errors = report.get("errors", [])
    return {
        "path": file_info.get("path"),
        "sha256": file_info.get("sha256"),
        "page_count": file_info.get("page_count"),
        "size_bytes": file_info.get("size_bytes"),
        "loader": report.get("loader"),
        "scan_time_ms": summary.get("scan_time_ms"),
        "object_count": summary.get("object_count"),
        "text_span_count": stats.get("text_span", 0),
        "metadata_count": stats.get("metadata", 0),
        "annotation_count": stats.get("annotation", 0),
        "form_count": stats.get("form", 0),
        "ocg_count": stats.get("ocg", 0),
        "embedded_file_count": stats.get("embedded_file", 0),
        "signature_present": stats.get("signature", 0) > 0,
        "finding_count": len(findings),
        "critical_count": severity_counts.get("critical", 0),
        "high_count": severity_counts.get("high", 0),
        "medium_count": severity_counts.get("medium", 0),
        "low_count": severity_counts.get("low", 0),
        "max_risk_score": max((_float_or_zero(item.get("risk_score")) for item in findings), default=0.0),
        "risk_types": ";".join(risk_types),
        "error": "; ".join(f"{err.get('stage')}: {err.get('message')}" for err in errors),
    }


def finding_rows(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    file_info = report.get("file", {})
    rows: List[Dict[str, Any]] = []
    for finding in report.get("findings", []):
        if not _is_control_intent_output_row(finding):
            continue
        control_score = _float_or_zero(finding.get("control_intent_score"))
        control = finding.get("evidence", {}).get("control_intent", {})
        rows.append(
            {
                "path": file_info.get("path"),
                "sha256": file_info.get("sha256"),
                "loader": report.get("loader"),
                "page_id": finding.get("page_id"),
                "object_type": finding.get("object_type"),
                "source": finding.get("source"),
                "control_intent_score": control_score,
                "text_preview": finding.get("text_preview"),
                "matched_phrases": ";".join(control.get("matched_phrases", [])),
                "matched_actions": ";".join(control.get("matched_actions", [])),
                "matched_roles": ";".join(control.get("matched_roles", [])),
                "error": "",
            }
        )
    return rows


def problem_sentence_rows(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    file_info = report.get("file", {})
    rows: List[Dict[str, Any]] = []
    for finding in report.get("findings", []):
        if not _is_control_intent_output_row(finding):
            continue
        control_score = _float_or_zero(finding.get("control_intent_score"))
        sentence = str(finding.get("text_preview") or "").strip()
        if not sentence:
            continue
        control = finding.get("evidence", {}).get("control_intent", {})
        rows.append(
            {
                "path": file_info.get("path"),
                "sha256": file_info.get("sha256"),
                "loader": report.get("loader"),
                "page_id": finding.get("page_id"),
                "sentence": sentence,
                "control_intent_score": control_score,
                "matched_phrases": ";".join(control.get("matched_phrases", [])),
                "matched_actions": ";".join(control.get("matched_actions", [])),
                "matched_roles": ";".join(control.get("matched_roles", [])),
                "object_id": finding.get("object_id"),
                "object_type": finding.get("object_type"),
            }
        )
    return rows


def error_finding_row(report: Dict[str, Any]) -> Dict[str, Any]:
    file_info = report.get("file", {})
    errors = report.get("errors", [])
    return {
        "path": file_info.get("path"),
        "sha256": file_info.get("sha256"),
        "loader": report.get("loader"),
        "page_id": "",
        "object_type": "",
        "source": "",
        "control_intent_score": "",
        "text_preview": "",
        "matched_phrases": "",
        "matched_actions": "",
        "matched_roles": "",
        "error": "; ".join(f"{err.get('stage')}: {err.get('message')}" for err in errors),
    }


def _float_or_zero(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _is_control_intent_output_row(finding: Dict[str, Any]) -> bool:
    control_score = _float_or_zero(finding.get("control_intent_score"))
    if control_score < CONTROL_INTENT_CSV_MIN_SCORE:
        return False
    control = finding.get("evidence", {}).get("control_intent", {})
    return bool(
        control.get("matched_phrases")
        or control.get("matched_actions")
        or control.get("matched_roles")
        or control.get("matched_format_terms")
    )
