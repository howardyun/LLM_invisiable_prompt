from __future__ import annotations

import html
from pathlib import Path
from typing import Dict


def _badge(level: str) -> str:
    colors = {
        "critical": "#9f1239",
        "high": "#b45309",
        "medium": "#0369a1",
        "low": "#475569",
    }
    return f'<span class="badge" style="background:{colors.get(level, "#475569")}">{html.escape(level)}</span>'


def write_html_report(report: Dict[str, object], path: str) -> None:
    findings = report.get("findings") or []
    rows = []
    for finding in findings:  # type: ignore[assignment]
        span = finding.get("parser_span", {})
        mapping = finding.get("mapping", {})
        evidence = finding.get("evidence", {})
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(finding.get('finding_id', '')))}</td>"
            f"<td>{_badge(str(finding.get('risk_level', 'low')))}</td>"
            f"<td>{finding.get('risk_score', '')}</td>"
            f"<td>{html.escape(str(finding.get('page', '')))}</td>"
            f"<td><code>{html.escape(str(mapping.get('support_status', '')))}</code>"
            f"<div>{html.escape(str(evidence.get('block_role', mapping.get('mapping_scope', ''))))}</div></td>"
            f"<td>{html.escape(', '.join(finding.get('categories', [])))}</td>"
            f"<td>{html.escape(str(span.get('text', '')))}</td>"
            f"<td>{html.escape(str(evidence.get('visibility_reasons', [])))}</td>"
            "</tr>"
        )

    summary = report.get("summary", {})
    body = "\n".join(rows) if rows else '<tr><td colspan="8">No findings</td></tr>'
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>PDF Semantic Detection Report</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 32px; color: #111827; }}
    h1 {{ font-size: 24px; margin-bottom: 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 18px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; vertical-align: top; font-size: 13px; }}
    th {{ background: #f3f4f6; text-align: left; }}
    code {{ white-space: nowrap; }}
    .badge {{ color: white; border-radius: 4px; padding: 2px 6px; font-size: 12px; }}
    .summary {{ color: #374151; }}
  </style>
</head>
<body>
  <h1>PDF Semantic Detection Report</h1>
  <div class="summary">
    <div><strong>PDF:</strong> {html.escape(str(report.get("pdf", "")))}</div>
    <div><strong>Parser:</strong> {html.escape(str(report.get("parser", "")))}</div>
    <div><strong>Summary:</strong> {html.escape(str(summary))}</div>
  </div>
  <table>
    <thead>
      <tr>
        <th>ID</th><th>Risk</th><th>Score</th><th>Page</th>
        <th>Support</th><th>Categories</th><th>Parser Text</th><th>Visibility Evidence</th>
      </tr>
    </thead>
    <tbody>{body}</tbody>
  </table>
</body>
</html>
"""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
