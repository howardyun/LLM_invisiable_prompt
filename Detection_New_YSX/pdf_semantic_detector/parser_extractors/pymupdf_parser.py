from __future__ import annotations

from typing import Any, List

from ..models import ParserSpan
from ..pdf_analysis.geometry import normalize_bbox, union_bbox
from ..pdf_analysis.normalization import normalize_text, split_long_line


def _require_fitz():
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PyMuPDF is required for parser 'pymupdf'.") from exc
    return fitz


def _line_records(page: Any) -> List[tuple[str, object]]:
    text_dict = page.get_text("dict", sort=False)
    records: List[tuple[str, object]] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            parts = [str(span.get("text") or "") for span in line.get("spans", [])]
            text = "".join(parts).strip()
            boxes = [normalize_bbox(span.get("bbox")) for span in line.get("spans", [])]
            boxes = [b for b in boxes if b is not None]
            bbox = union_bbox(boxes) if boxes else normalize_bbox(line.get("bbox"))
            if text:
                records.append((text, bbox))
    return records


def extract(pdf_path: str) -> List[ParserSpan]:
    fitz = _require_fitz()
    doc = fitz.open(pdf_path)
    spans: List[ParserSpan] = []
    order = 0
    try:
        for page_index in range(len(doc)):
            page_num = page_index + 1
            for line, bbox in _line_records(doc.load_page(page_index)):
                for chunk in split_long_line(line):
                    spans.append(
                        ParserSpan(
                            span_id=f"s{order + 1:05d}",
                            parser_name="pymupdf",
                            page=page_num,
                            text=chunk,
                            normalized_text=normalize_text(chunk),
                            order=order,
                            bbox=bbox,
                        )
                    )
                    order += 1
    finally:
        doc.close()
    return spans
