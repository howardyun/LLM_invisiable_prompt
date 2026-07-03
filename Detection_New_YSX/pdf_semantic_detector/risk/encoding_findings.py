from __future__ import annotations

from typing import List

from ..models import MappingResult, ParserSpan, RiskFinding
from ..pdf_analysis.font_encoding import FontEncodingIssue


def build_encoding_findings(
    issues: List[FontEncodingIssue],
    start_index: int = 0,
) -> List[RiskFinding]:
    findings: List[RiskFinding] = []
    for issue in issues:
        span = ParserSpan(
            span_id=issue.issue_id,
            parser_name="font_encoding_analysis",
            page=issue.page,
            text=issue.text,
            normalized_text=issue.text.lower(),
            order=start_index + len(findings),
        )
        mapping = MappingResult(
            span_id=span.span_id,
            matched_region_id=None,
            match_score=0.0,
            text_score=0.0,
            geo_score=None,
            source_score=None,
            visibility_score=1.0,
            support_status="encoding_untrusted_supported",
            reasons=issue.reasons,
        )
        risk_level = "high" if issue.risk_score >= 0.70 else "medium"
        findings.append(
            RiskFinding(
                finding_id=f"f{start_index + len(findings) + 1:05d}",
                page=issue.page,
                parser_span=span,
                mapping=mapping,
                risk_level=risk_level,
                risk_score=issue.risk_score,
                categories=["font_encoding_mismatch", "glyph_semantic_drift"],
                evidence=issue.evidence,
            )
        )
    return findings
