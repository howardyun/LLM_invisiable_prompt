from __future__ import annotations

from typing import Dict, Optional

from .config import DetectionConfig
from .mapping import map_parser_spans
from .parser_extractors import aggregate_parser_spans, extract_parser_spans
from .pdf_analysis import build_structure_blocks, detect_font_encoding_issues, extract_pdf_regions
from .reporting import build_report
from .risk import build_encoding_findings, build_findings


def detect_pdf_implicit_injection(
    pdf_path: str,
    parser_name: str = "pypdf",
    config: Optional[DetectionConfig] = None,
) -> Dict[str, object]:
    config = config or DetectionConfig()
    regions = extract_pdf_regions(pdf_path, config)
    blocks = build_structure_blocks(regions, config)
    raw_parser_spans = extract_parser_spans(pdf_path, parser_name)
    parser_spans = aggregate_parser_spans(raw_parser_spans, blocks, config)
    mappings = map_parser_spans(parser_spans, regions, config, blocks)
    findings = build_findings(parser_spans, mappings, regions, config, blocks)
    encoding_issues = detect_font_encoding_issues(pdf_path, config, regions)
    findings.extend(build_encoding_findings(encoding_issues, len(findings)))
    return build_report(pdf_path, parser_name, regions, parser_spans, mappings, findings, config, blocks)
