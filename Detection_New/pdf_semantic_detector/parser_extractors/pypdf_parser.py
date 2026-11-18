from __future__ import annotations

from typing import List

from ..models import ParserSpan
from ..pdf_analysis.normalization import normalize_text, split_long_line, split_text_lines


def _require_pypdf():
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pypdf is required for parser 'pypdf'. Install with: pip install pypdf") from exc
    return PdfReader


def extract(pdf_path: str) -> List[ParserSpan]:
    PdfReader = _require_pypdf()
    reader = PdfReader(pdf_path)
    spans: List[ParserSpan] = []
    order = 0
    for page_index, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        for line in split_text_lines(page_text):
            for chunk in split_long_line(line):
                spans.append(
                    ParserSpan(
                        span_id=f"s{order + 1:05d}",
                        parser_name="pypdf",
                        page=page_index + 1,
                        text=chunk,
                        normalized_text=normalize_text(chunk),
                        order=order,
                    )
                )
                order += 1
    return spans
