"""Small IO helpers for JSON/CSV output."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from detector_config import CSV_FIELDS
from detector_models import RegionalResult


def write_json(path: Path, data: Any) -> None:
    """Write UTF-8 JSON with stable indentation."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def compact_csv_text(text: str | None) -> str:
    """Keep CSV cells readable by collapsing newlines/extra spaces."""

    return re.sub(r"\s+", " ", text or "").strip()


def write_dicts_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    """Write arbitrary dictionaries as an Excel-friendly UTF-8-BOM CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            cleaned: dict[str, Any] = {}
            for key in fieldnames:
                value = row.get(key, "")
                if isinstance(value, (dict, list)):
                    cleaned[key] = json.dumps(value, ensure_ascii=False)
                elif isinstance(value, str):
                    cleaned[key] = compact_csv_text(value)
                else:
                    cleaned[key] = value
            writer.writerow(cleaned)


def write_results_csv(path: Path, results: list[RegionalResult]) -> None:
    """Write result rows as an Excel-friendly UTF-8-BOM CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    text_fields = {
        "pymupdf_text",
        "ocr_text",
        "verify_ocr_text",
        "formula_visual_latex",
        "formula_parser_latex",
        "formula_error",
        "docling_text",
        "reason",
        "ocr_error",
        "debug_note",
    }
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in results:
            row = asdict(item)
            row["bbox"] = json.dumps(item.bbox, ensure_ascii=False)
            for key in text_fields:
                row[key] = compact_csv_text(row.get(key))
            writer.writerow({key: row.get(key, "") for key in CSV_FIELDS})
