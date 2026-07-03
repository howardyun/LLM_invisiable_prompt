from __future__ import annotations

from typing import List, Optional

from ..models import ParserSpan


def extract_parser_spans(pdf_path: str, parser_name: str = "pypdf") -> List[ParserSpan]:
    name = parser_name.lower().strip()
    if name == "pymupdf":
        from .pymupdf_parser import extract

        return extract(pdf_path)
    if name == "pypdf":
        from .pypdf_parser import extract

        return extract(pdf_path)
    raise ValueError(f"Unsupported parser '{parser_name}'. Available parsers: pypdf, pymupdf")
