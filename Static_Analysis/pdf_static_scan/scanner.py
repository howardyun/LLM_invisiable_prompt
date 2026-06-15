from __future__ import annotations

import os
import logging
import time
from collections import Counter
from typing import Any, Dict, Iterable, List, Sequence

from .analyzers import (
    analyze_control_intent,
    analyze_object_anomalies,
    analyze_visibility,
    classify_risk_type,
    compute_risk_score,
    severity_from_score,
    should_emit_finding,
)
from .config import ScanConfig
from .extractors import (
    extract_annotations,
    extract_embedded_files,
    extract_fonts,
    extract_forms,
    extract_metadata,
    extract_ocg,
    extract_pypdf_page_text,
    extract_signatures,
    extract_text_spans,
)
from .loader_profiles import get_loader_profile, map_consumption
from .schema import ExtractedPDF, Finding, PDFObject, ScanError, to_jsonable
from .utils import flatten_errors, sha256_file, text_preview


def scan_pdf(pdf_path: str, loader_name: str = "generic_t1", config: ScanConfig | None = None) -> Dict[str, Any]:
    reports = scan_pdf_multi(pdf_path, [loader_name], config)
    return reports[0]


def scan_pdf_multi(
    pdf_path: str,
    loader_names: Sequence[str] | None = None,
    config: ScanConfig | None = None,
) -> List[Dict[str, Any]]:
    cfg = config or ScanConfig()
    loaders = list(loader_names or ["generic_t1"])
    start = time.perf_counter()
    extracted = extract_pdf(pdf_path, cfg)
    scan_time_ms = int((time.perf_counter() - start) * 1000)
    return [_evaluate_pdf(extracted, loader_name, cfg, scan_time_ms) for loader_name in loaders]


def extract_pdf(pdf_path: str, config: ScanConfig) -> ExtractedPDF:
    file_info: Dict[str, Any] = {
        "path": os.path.abspath(pdf_path),
        "size_bytes": None,
        "sha256": None,
        "page_count": None,
        "encrypted": None,
    }
    objects: List[PDFObject] = []
    errors: List[ScanError] = []
    fitz_doc = None
    reader = None

    try:
        file_info["size_bytes"] = os.path.getsize(pdf_path)
        file_info["sha256"] = sha256_file(pdf_path)
    except Exception as exc:
        errors.append(ScanError("file_info", str(exc)))
        if config.fail_fast:
            raise

    try:
        fitz_doc = _open_fitz_doc(pdf_path)
    except Exception as exc:
        errors.append(ScanError("open_pymupdf", str(exc)))
        if config.fail_fast:
            raise

    try:
        reader = _open_pdf_reader(pdf_path)
        encrypted = bool(getattr(reader, "is_encrypted", False))
        file_info["encrypted"] = encrypted
        if encrypted:
            try:
                reader.decrypt("")
            except Exception:
                pass
    except Exception as exc:
        errors.append(ScanError("open_pypdf", str(exc)))
        if config.fail_fast:
            raise

    file_info["page_count"] = _page_count(fitz_doc, reader)
    if file_info["encrypted"] is None and fitz_doc is not None:
        file_info["encrypted"] = bool(getattr(fitz_doc, "needs_pass", False))

    text_objects = _run_stage("text_spans", lambda: extract_text_spans(fitz_doc, config), errors, config)
    objects.extend(text_objects)
    if config.extract_pypdf_text:
        objects.extend(
            _run_stage("pypdf_page_text", lambda: extract_pypdf_page_text(reader, text_objects), errors, config)
        )

    stages = [
        ("metadata", lambda: extract_metadata(reader, config)),
        ("annotations", lambda: extract_annotations(reader, fitz_doc)),
        ("forms", lambda: extract_forms(reader)),
        ("ocg", lambda: extract_ocg(reader)),
    ]
    if config.extract_fonts:
        stages.append(("fonts", lambda: extract_fonts(reader)))
    if config.extract_embedded_files:
        stages.append(("embedded_files", lambda: extract_embedded_files(reader)))
    if config.extract_signatures:
        stages.append(("signatures", lambda: extract_signatures(pdf_path, reader, config)))

    for stage, func in stages:
        objects.extend(_run_stage(stage, func, errors, config))

    if fitz_doc is not None:
        try:
            fitz_doc.close()
        except Exception:
            pass

    object_stats = dict(Counter(obj.object_type for obj in objects))
    return ExtractedPDF(file_info=file_info, objects=objects, object_stats=object_stats, errors=errors)


def _run_stage(stage: str, func: Any, errors: List[ScanError], config: ScanConfig) -> List[PDFObject]:
    try:
        return list(func())
    except Exception as exc:
        errors.append(ScanError(stage, str(exc)))
        if config.fail_fast:
            raise
        return []


def _evaluate_pdf(
    extracted: ExtractedPDF,
    loader_name: str,
    config: ScanConfig,
    scan_time_ms: int,
) -> Dict[str, Any]:
    profile = get_loader_profile(loader_name)
    findings: List[Finding] = []
    visibility_counts: Counter[str] = Counter()
    finding_risk_counts: Counter[str] = Counter()
    file_sha = str(extracted.file_info.get("sha256") or "")
    for obj in extracted.objects:
        consumed = map_consumption(obj, profile)
        visibility, visibility_reasons, visibility_flags = analyze_visibility(obj, config)
        visibility_counts[visibility] += 1
        visibility_details = _pop_visibility_details(visibility_flags)
        control_score, control_evidence = analyze_control_intent(obj.text, config)
        anomaly_flags = analyze_object_anomalies(obj, visibility_flags)
        score = compute_risk_score(consumed, visibility, control_score, anomaly_flags)
        risk_type = classify_risk_type(obj, consumed, visibility, control_score, anomaly_flags)
        if not should_emit_finding(score, risk_type, config):
            continue
        finding_risk_counts[risk_type] += 1
        evidence = {
            "why_loader_consumed": _loader_evidence(consumed, obj.object_type, loader_name),
            "visibility_reasons": visibility_reasons,
            "visibility_details": visibility_details,
            "anomaly_flags": anomaly_flags,
            "control_intent": control_evidence,
            "object_attrs": obj.attrs,
        }
        finding_id = f"f{len(findings) + 1:04d}"
        findings.append(
            Finding(
                finding_id=finding_id,
                file_sha256=file_sha,
                object_id=obj.object_id,
                object_type=obj.object_type,
                source=obj.source,
                page_id=obj.page_id,
                bbox=obj.bbox,
                loader=loader_name,
                loader_consumed=consumed,
                visibility_state=visibility,
                risk_type=risk_type,
                severity=severity_from_score(score, config),
                risk_score=score,
                control_intent_score=round(control_score, 6),
                text_preview=text_preview(obj.text, config.max_text_preview_len),
                evidence=evidence,
            )
        )

    severity_counts = Counter(f.severity for f in findings)
    summary = {
        "object_count": len(extracted.objects),
        "finding_count": len(findings),
        "critical": severity_counts.get("critical", 0),
        "high": severity_counts.get("high", 0),
        "medium": severity_counts.get("medium", 0),
        "low": severity_counts.get("low", 0),
        "max_risk_score": max((f.risk_score for f in findings), default=0.0),
        "visibility_counts": dict(visibility_counts),
        "risk_type_counts": dict(finding_risk_counts),
        "scan_time_ms": scan_time_ms,
    }
    report: Dict[str, Any] = {
        "file": extracted.file_info,
        "loader": loader_name,
        "summary": summary,
        "object_stats": extracted.object_stats,
        "findings": [to_jsonable(item) for item in findings],
        "errors": flatten_errors(extracted.errors),
    }
    if config.include_objects:
        report["objects"] = [to_jsonable(obj) for obj in extracted.objects]
    return report


def _open_fitz_doc(pdf_path: str) -> Any:
    try:
        import fitz  # type: ignore
    except Exception as exc:
        raise RuntimeError("PyMuPDF is required for text span extraction. Install with: pip install pymupdf") from exc
    return fitz.open(pdf_path)


def _pop_visibility_details(flags: Dict[str, Any]) -> Dict[str, Any]:
    details: Dict[str, Any] = {}
    for key in list(flags):
        if key.startswith("_detail_"):
            details[key.removeprefix("_detail_")] = flags.pop(key)
    return details


def _open_pdf_reader(pdf_path: str) -> Any:
    logging.getLogger("pypdf").setLevel(logging.CRITICAL)
    logging.getLogger("PyPDF2").setLevel(logging.CRITICAL)
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception as exc:
            raise RuntimeError("pypdf is required for metadata/forms/object extraction. Install with: pip install pypdf") from exc
    return PdfReader(pdf_path, strict=False)


def _page_count(fitz_doc: Any, reader: Any) -> int | None:
    if fitz_doc is not None:
        try:
            return len(fitz_doc)
        except Exception:
            pass
    if reader is not None:
        try:
            return len(reader.pages)
        except Exception:
            pass
    return None


def _loader_evidence(consumed: str, object_type: str, loader_name: str) -> str:
    if consumed == "yes":
        return f"{loader_name} profile marks {object_type} as consumed."
    if consumed == "no":
        return f"{loader_name} profile normally does not consume {object_type}."
    return f"{loader_name} profile has uncertain consumption for {object_type}."
