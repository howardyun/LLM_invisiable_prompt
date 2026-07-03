from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from ..config import DetectionConfig
from ..models import BlockDescriptor, MappingResult, ParserSpan, RegionDescriptor, RiskFinding, to_serializable


def build_report(
    pdf_path: str,
    parser_name: str,
    regions: List[RegionDescriptor],
    spans: List[ParserSpan],
    mappings: List[MappingResult],
    findings: List[RiskFinding],
    config: DetectionConfig,
    blocks: Optional[List[BlockDescriptor]] = None,
) -> Dict[str, object]:
    blocks = blocks or []
    pages = sorted({r.page for r in regions} | {s.page for s in spans if s.page is not None})
    high_or_above = sum(1 for f in findings if f.risk_level in {"high", "critical"})
    raw_parser_span_ids = {
        raw_id
        for span in spans
        for raw_id in (span.raw_span_ids or [span.span_id])
    }
    report: Dict[str, object] = {
        "pdf": str(pdf_path),
        "parser": parser_name,
        "summary": {
            "pages": len(pages),
            "regions": len(regions),
            "blocks": len(blocks),
            "text_regions": sum(1 for r in regions if r.region_type == "text"),
            "parser_spans": len(spans),
            "raw_parser_spans": len(raw_parser_span_ids),
            "findings": len(findings),
            "high_or_above": high_or_above,
            "support_status_counts": dict(Counter(m.support_status for m in mappings)),
            "block_role_counts": dict(Counter(b.block_role for b in blocks)),
            "visibility_status_counts": dict(Counter(r.visibility_status for r in regions if r.region_type == "text")),
        },
        "findings": [to_serializable(f) for f in findings],
    }
    if config.include_debug:
        report["regions"] = [to_serializable(r) for r in regions]
        report["structure_blocks"] = [to_serializable(b) for b in blocks]
        report["parser_spans"] = [to_serializable(s) for s in spans]
        report["mapping_results"] = [to_serializable(m) for m in mappings]
    return report


def write_json_report(report: Dict[str, object], path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
