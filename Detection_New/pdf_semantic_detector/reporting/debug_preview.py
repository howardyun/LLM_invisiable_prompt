from __future__ import annotations

import html
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from ..models import BBox, BlockDescriptor, MappingResult, ParserSpan, RegionDescriptor


def _require_fitz():
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PyMuPDF is required to build the debug preview.") from exc
    return fitz


def _page_sizes(pdf_path: str) -> Dict[int, Tuple[float, float]]:
    fitz = _require_fitz()
    doc = fitz.open(pdf_path)
    try:
        return {
            page_index + 1: (float(doc[page_index].rect.width), float(doc[page_index].rect.height))
            for page_index in range(len(doc))
        }
    finally:
        doc.close()


def _region_text(region: RegionDescriptor) -> str:
    return region.rendered_text_estimate or region.text or ""


def _short(text: str, limit: int = 160) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


def _is_drift(region: RegionDescriptor) -> bool:
    if region.parser_text is None or region.rendered_text_estimate is None:
        return False
    return region.parser_text != region.rendered_text_estimate


def _is_line(region: RegionDescriptor) -> bool:
    return region.text_semantic_source == "glyph_shape_line"


def _svg_text(region: RegionDescriptor) -> str:
    x0, y0, x1, y1 = region.bbox
    text = _region_text(region)
    if not text.strip():
        return ""

    font_size = region.font_size or max(8.0, min(18.0, (y1 - y0) * 0.85))
    font_size = max(5.0, min(24.0, float(font_size)))
    color = "#0f766e"
    fill_opacity = "1"
    stroke = "#14b8a6"
    stroke_width = "0.6"
    if _is_drift(region):
        color = "#b45309"
        stroke = "#f59e0b"
        stroke_width = "1.0"
    if _is_line(region):
        color = "#7c2d12"
        stroke = "#ea580c"
        stroke_width = "1.4"

    title_parts = [
        f"region: {region.region_id}",
        f"source: {region.text_semantic_source}",
        f"rendered: {region.rendered_text_estimate or region.text or ''}",
    ]
    if region.parser_text is not None:
        title_parts.append(f"parser: {region.parser_text}")
    if region.rendered_text_confidence is not None:
        title_parts.append(f"confidence: {region.rendered_text_confidence:.3f}")
    title = html.escape("\n".join(title_parts))

    rect = (
        f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{max(0.5, x1 - x0):.2f}" '
        f'height="{max(0.5, y1 - y0):.2f}" fill="none" stroke="{stroke}" '
        f'stroke-width="{stroke_width}" />'
    )
    escaped = html.escape(_short(text, 220))
    baseline = y1 - max(1.0, font_size * 0.16)
    return (
        f'<g class="region {"drift" if _is_drift(region) else "normal"}">'
        f"<title>{title}</title>"
        f"{rect}"
        f'<text x="{x0:.2f}" y="{baseline:.2f}" font-size="{font_size:.2f}" '
        f'fill="{color}" fill-opacity="{fill_opacity}">{escaped}</text>'
        "</g>"
    )


def _page_svg(page_num: int, width: float, height: float, regions: List[RegionDescriptor]) -> str:
    body = "\n".join(_svg_text(region) for region in regions if _region_text(region).strip())
    return f"""
<section class="page-section">
  <h2>Page {page_num}</h2>
  <div class="page-meta">{len(regions)} text regions</div>
  <svg class="page" viewBox="0 0 {width:.2f} {height:.2f}" width="{width:.0f}" height="{height:.0f}">
    <rect x="0" y="0" width="{width:.2f}" height="{height:.2f}" fill="white" stroke="#cbd5e1" />
    {body}
  </svg>
</section>
"""


def _drift_rows(regions: Iterable[RegionDescriptor]) -> str:
    rows: List[str] = []
    for region in regions:
        if not _is_drift(region):
            continue
        rows.append(
            "<tr>"
            f"<td>{html.escape(region.region_id)}</td>"
            f"<td>{region.page}</td>"
            f"<td>{html.escape(region.text_semantic_source)}</td>"
            f"<td>{html.escape(str(region.bbox))}</td>"
            f"<td>{html.escape(_short(region.parser_text or '', 220))}</td>"
            f"<td>{html.escape(_short(region.rendered_text_estimate or '', 220))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="6">No semantic drift regions</td></tr>'


def write_rendered_text_preview(pdf_path: str, regions: List[RegionDescriptor], path: str) -> None:
    page_sizes = _page_sizes(pdf_path)
    pages: Dict[int, List[RegionDescriptor]] = {}
    for region in regions:
        if region.region_type != "text":
            continue
        pages.setdefault(region.page, []).append(region)

    page_svgs = []
    for page_num in sorted(pages):
        width, height = page_sizes.get(page_num, (612.0, 792.0))
        page_regions = sorted(pages[page_num], key=lambda r: (r.bbox[1], r.bbox[0]))
        page_svgs.append(_page_svg(page_num, width, height, page_regions))

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Rendered Text Debug Preview</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #0f172a; background: #f8fafc; }}
    h1 {{ font-size: 24px; margin: 0 0 8px; }}
    h2 {{ font-size: 18px; margin: 24px 0 4px; }}
    .hint {{ color: #475569; margin-bottom: 16px; }}
    .legend {{ display: flex; gap: 18px; margin: 12px 0 18px; font-size: 13px; }}
    .swatch {{ display: inline-block; width: 12px; height: 12px; vertical-align: -1px; margin-right: 5px; border: 1px solid #94a3b8; }}
    .normal-swatch {{ background: #0f766e; }}
    .drift-swatch {{ background: #b45309; }}
    .line-swatch {{ background: #7c2d12; }}
    .page-section {{ margin-bottom: 28px; }}
    .page-meta {{ color: #64748b; font-size: 12px; margin-bottom: 8px; }}
    svg.page {{ display: block; max-width: 100%; height: auto; background: white; box-shadow: 0 1px 4px rgba(15, 23, 42, 0.18); }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin-top: 24px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 7px; font-size: 12px; vertical-align: top; }}
    th {{ background: #e2e8f0; text-align: left; }}
  </style>
</head>
<body>
  <h1>Rendered Text Debug Preview</h1>
  <div class="hint">
    This preview places <code>rendered_text_estimate</code> back onto page coordinates before PDF rasterization.
    Hover text boxes to compare parser text and estimated rendered text.
  </div>
  <div class="legend">
    <span><span class="swatch normal-swatch"></span>normal text estimate</span>
    <span><span class="swatch drift-swatch"></span>parser/rendered drift</span>
    <span><span class="swatch line-swatch"></span>aggregated glyph-shape line</span>
  </div>
  {''.join(page_svgs)}
  <h2>Semantic Drift Table</h2>
  <table>
    <thead>
      <tr><th>Region</th><th>Page</th><th>Source</th><th>BBox</th><th>Parser Text</th><th>Rendered Estimate</th></tr>
    </thead>
    <tbody>
      {_drift_rows(regions)}
    </tbody>
  </table>
</body>
</html>
"""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")


def _block_color(role: str) -> str:
    colors = {
        "paragraph": "#2563eb",
        "formula": "#9333ea",
        "table": "#16a34a",
        "caption": "#0891b2",
        "header_footer": "#64748b",
        "hidden_or_overlay_text": "#dc2626",
        "glyph_drift_text": "#ea580c",
        "heading": "#0f766e",
    }
    return colors.get(role, "#475569")


def _block_svg(block: BlockDescriptor) -> str:
    x0, y0, x1, y1 = block.bbox
    color = _block_color(block.block_role)
    label = f"{block.block_id} {block.block_role} {block.block_role_confidence:.2f}"
    title = html.escape(
        "\n".join(
            [
                f"block: {block.block_id}",
                f"role: {block.block_role}",
                f"confidence: {block.block_role_confidence:.3f}",
                f"regions: {len(block.region_ids)}",
                f"text: {_short(block.text, 260)}",
                f"features: {block.features}",
            ]
        )
    )
    return (
        f'<g class="block role-{html.escape(block.block_role)}">'
        f"<title>{title}</title>"
        f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{max(0.5, x1 - x0):.2f}" '
        f'height="{max(0.5, y1 - y0):.2f}" fill="none" stroke="{color}" '
        f'stroke-width="1.6" stroke-dasharray="4 3" />'
        f'<text x="{x0:.2f}" y="{max(8.0, y0 - 3.0):.2f}" font-size="8.5" fill="{color}">'
        f"{html.escape(label)}</text>"
        "</g>"
    )


def _block_page_svg(page_num: int, width: float, height: float, blocks: List[BlockDescriptor]) -> str:
    body = "\n".join(_block_svg(block) for block in blocks)
    return f"""
<section class="page-section">
  <h2>Page {page_num}</h2>
  <div class="page-meta">{len(blocks)} structure blocks</div>
  <svg class="page" viewBox="0 0 {width:.2f} {height:.2f}" width="{width:.0f}" height="{height:.0f}">
    <rect x="0" y="0" width="{width:.2f}" height="{height:.2f}" fill="white" stroke="#cbd5e1" />
    {body}
  </svg>
</section>
"""


def _block_rows(blocks: Iterable[BlockDescriptor]) -> str:
    rows: List[str] = []
    for block in blocks:
        rows.append(
            "<tr>"
            f"<td>{html.escape(block.block_id)}</td>"
            f"<td>{block.page}</td>"
            f"<td>{html.escape(block.block_role)}</td>"
            f"<td>{block.block_role_confidence:.3f}</td>"
            f"<td>{html.escape(str(block.bbox))}</td>"
            f"<td>{len(block.region_ids)}</td>"
            f"<td>{html.escape(_short(block.text, 260))}</td>"
            f"<td><pre>{html.escape(str(block.features))}</pre></td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="8">No structure blocks</td></tr>'


def _legend_roles(blocks: Iterable[BlockDescriptor]) -> str:
    roles = sorted({block.block_role for block in blocks})
    return "\n".join(
        f'<span><span class="swatch" style="background:{_block_color(role)}"></span>{html.escape(role)}</span>'
        for role in roles
    )


def write_structure_blocks_preview(pdf_path: str, blocks: List[BlockDescriptor], path: str) -> None:
    page_sizes = _page_sizes(pdf_path)
    pages: Dict[int, List[BlockDescriptor]] = {}
    for block in blocks:
        pages.setdefault(block.page, []).append(block)

    page_svgs = []
    for page_num in sorted(pages):
        width, height = page_sizes.get(page_num, (612.0, 792.0))
        page_blocks = sorted(pages[page_num], key=lambda block: (block.bbox[1], block.bbox[0]))
        page_svgs.append(_block_page_svg(page_num, width, height, page_blocks))

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Structure Blocks Debug Preview</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #0f172a; background: #f8fafc; }}
    h1 {{ font-size: 24px; margin: 0 0 8px; }}
    h2 {{ font-size: 18px; margin: 24px 0 4px; }}
    .hint {{ color: #475569; margin-bottom: 16px; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 14px; margin: 12px 0 18px; font-size: 13px; }}
    .swatch {{ display: inline-block; width: 12px; height: 12px; vertical-align: -1px; margin-right: 5px; border: 1px solid #94a3b8; }}
    .page-section {{ margin-bottom: 28px; }}
    .page-meta {{ color: #64748b; font-size: 12px; margin-bottom: 8px; }}
    svg.page {{ display: block; max-width: 100%; height: auto; background: white; box-shadow: 0 1px 4px rgba(15, 23, 42, 0.18); }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin-top: 24px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 7px; font-size: 12px; vertical-align: top; }}
    th {{ background: #e2e8f0; text-align: left; }}
    pre {{ margin: 0; white-space: pre-wrap; font-family: Consolas, monospace; font-size: 11px; }}
  </style>
</head>
<body>
  <h1>Structure Blocks Debug Preview</h1>
  <div class="hint">
    This is the intermediate layer between low-level PDF regions and parser-span semantic mapping.
    Hover a block rectangle to inspect its role, source regions, text, and structural features.
  </div>
  <div class="legend">{_legend_roles(blocks)}</div>
  {''.join(page_svgs)}
  <h2>Block Table</h2>
  <table>
    <thead>
      <tr><th>Block</th><th>Page</th><th>Role</th><th>Conf.</th><th>BBox</th><th>Regions</th><th>Text</th><th>Features</th></tr>
    </thead>
    <tbody>
      {_block_rows(blocks)}
    </tbody>
  </table>
</body>
</html>
"""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")


def _status_class(status: str) -> str:
    if status == "render_supported":
        return "supported"
    if status == "render_unsupported":
        return "unsupported"
    if status == "low_visibility_supported":
        return "low-visibility"
    if status == "ambiguous":
        return "ambiguous"
    return "other"


def _target_text(
    mapping: MappingResult,
    block_by_id: Dict[str, BlockDescriptor],
    region_by_id: Dict[str, RegionDescriptor],
) -> Tuple[str, str, str, str]:
    block = block_by_id.get(mapping.matched_block_id or "")
    if block is not None:
        rendered = block.rendered_text_estimate or block.text or ""
        parser_side = block.parser_text or ""
        meta = (
            f"{block.block_id} / {block.block_role} / conf={block.block_role_confidence:.3f} / "
            f"bbox={block.bbox} / regions={len(block.region_ids)}"
        )
        features = str(block.features)
        return meta, rendered, parser_side, features

    region = region_by_id.get(mapping.matched_region_id or "")
    if region is not None:
        rendered = region.rendered_text_estimate or region.text or ""
        parser_side = region.parser_text or region.text or ""
        meta = (
            f"{region.region_id} / {region.text_semantic_source} / bbox={region.bbox} / "
            f"block={region.block_id or ''}"
        )
        features = f"visibility={region.visibility_score}; reasons={region.visibility_reasons}"
        return meta, rendered, parser_side, features

    return "no matched visual target", "", "", ""


def _alignment_rows(
    spans: Iterable[ParserSpan],
    mappings: Iterable[MappingResult],
    blocks: Iterable[BlockDescriptor],
    regions: Iterable[RegionDescriptor],
) -> str:
    span_by_id = {span.span_id: span for span in spans}
    block_by_id = {block.block_id: block for block in blocks}
    region_by_id = {region.region_id: region for region in regions}
    rows: List[str] = []
    for mapping in mappings:
        span = span_by_id.get(mapping.span_id)
        if span is None:
            continue
        target_meta, rendered_text, target_parser_text, features = _target_text(mapping, block_by_id, region_by_id)
        cls = _status_class(mapping.support_status)
        score_text = (
            f"match={mapping.match_score:.3f}<br>"
            f"text={mapping.text_score:.3f}<br>"
            f"geo={mapping.geo_score:.3f}" if mapping.geo_score is not None else
            f"match={mapping.match_score:.3f}<br>text={mapping.text_score:.3f}<br>geo=n/a"
        )
        rows.append(
            f'<tr class="{cls}">'
            f"<td><strong>{html.escape(span.span_id)}</strong><br>page={html.escape(str(span.page))}<br>"
            f"order={span.order}<br>level={html.escape(span.aggregation_level)}<br>"
            f"raw={html.escape(','.join(span.raw_span_ids or [span.span_id]))}<br>"
            f"{html.escape(span.source_hint or '')}</td>"
            f"<td><code>{html.escape(mapping.support_status)}</code><br>"
            f"scope={html.escape(mapping.mapping_scope)}<br>{score_text}<br>"
            f"reasons={html.escape(str(mapping.reasons))}</td>"
            f"<td>{html.escape(target_meta)}<details><summary>features</summary>"
            f"<pre>{html.escape(features)}</pre></details></td>"
            f"<td><pre>{html.escape(span.text)}</pre></td>"
            f"<td><pre>{html.escape(rendered_text)}</pre></td>"
            f"<td><pre>{html.escape(target_parser_text)}</pre></td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="6">No parser/block alignment rows</td></tr>'


def write_parser_block_alignment_preview(
    spans: List[ParserSpan],
    mappings: List[MappingResult],
    blocks: List[BlockDescriptor],
    regions: List[RegionDescriptor],
    path: str,
) -> None:
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Parser To Visual Block Alignment</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #0f172a; background: #f8fafc; }}
    h1 {{ font-size: 24px; margin: 0 0 8px; }}
    .hint {{ color: #475569; margin-bottom: 16px; max-width: 980px; line-height: 1.45; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 14px; margin: 12px 0 18px; font-size: 13px; }}
    .swatch {{ display: inline-block; width: 12px; height: 12px; vertical-align: -1px; margin-right: 5px; border: 1px solid #94a3b8; }}
    table {{ border-collapse: collapse; width: 100%; background: white; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 7px; font-size: 12px; vertical-align: top; }}
    th {{ background: #e2e8f0; text-align: left; position: sticky; top: 0; z-index: 1; }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; font-family: Consolas, monospace; font-size: 11px; line-height: 1.35; }}
    code {{ white-space: nowrap; }}
    tr.supported {{ background: #f0fdf4; }}
    tr.unsupported {{ background: #fff7ed; }}
    tr.low-visibility {{ background: #fef2f2; }}
    tr.ambiguous {{ background: #eff6ff; }}
    details {{ margin-top: 5px; }}
    summary {{ cursor: pointer; color: #334155; }}
  </style>
</head>
<body>
  <h1>Parser To Visual Block Alignment</h1>
  <div class="hint">
    Each row compares one target parser span with the visual block selected by the detector.
    The visual column is the detector's pre-render estimate of what the PDF would draw.
    <code>geo</code> is only available when the parser provides a bbox; for the default pypdf path, matching is text-first.
  </div>
  <div class="legend">
    <span><span class="swatch" style="background:#f0fdf4"></span>render supported</span>
    <span><span class="swatch" style="background:#fff7ed"></span>render unsupported</span>
    <span><span class="swatch" style="background:#fef2f2"></span>low visibility</span>
    <span><span class="swatch" style="background:#eff6ff"></span>ambiguous</span>
  </div>
  <table>
    <thead>
      <tr>
        <th>Parser Span</th>
        <th>Mapping</th>
        <th>Matched Visual Target</th>
        <th>Parser Text</th>
        <th>Visual Rendered Estimate</th>
        <th>Visual Parser-Side Text</th>
      </tr>
    </thead>
    <tbody>
      {_alignment_rows(spans, mappings, blocks, regions)}
    </tbody>
  </table>
</body>
</html>
"""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
