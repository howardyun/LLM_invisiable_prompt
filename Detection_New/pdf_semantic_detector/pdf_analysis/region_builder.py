from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from ..config import DetectionConfig
from ..models import BBox, RegionDescriptor
from .geometry import normalize_bbox
from .normalization import normalize_text
from .occlusion import apply_occlusion_estimate
from .rendered_text import apply_rendered_text_estimates
from .visibility import estimate_visibility, normalize_color


def _require_fitz():
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised only without dependency
        raise RuntimeError(
            "PyMuPDF is required for PDF region extraction. Install with: pip install pymupdf"
        ) from exc
    return fitz


def _chars_to_text(chars: Iterable[Any]) -> str:
    out: List[str] = []
    for item in chars:
        try:
            codepoint = int(item[0])
        except Exception:
            continue
        if 0 <= codepoint <= 0x10FFFF:
            out.append(chr(codepoint))
    return "".join(out)


def _page_bbox(page: Any) -> BBox:
    rect = getattr(page, "rect")
    return (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))


def _source_object(page: Any) -> Optional[str]:
    xref = getattr(page, "xref", None)
    if isinstance(xref, int) and xref > 0:
        return f"{xref} 0 obj"
    return None


def _build_texttrace_regions(
    pdf_path: str,
    page: Any,
    page_index: int,
    page_num: int,
    config: DetectionConfig,
) -> List[RegionDescriptor]:
    page_box = _page_bbox(page)
    page_obj = _source_object(page)
    try:
        texttrace = page.get_texttrace()
    except Exception:
        return []
    try:
        bboxlog = page.get_bboxlog()
    except Exception:
        bboxlog = []

    regions: List[RegionDescriptor] = []
    for local_idx, span in enumerate(texttrace):
        text = _chars_to_text(span.get("chars", []))
        if not text.strip():
            continue
        bbox = normalize_bbox(span.get("bbox"))
        if bbox is None:
            continue
        seqno = span.get("seqno", local_idx)
        bboxlog_type = None
        if isinstance(seqno, int) and 0 <= seqno < len(bboxlog):
            bboxlog_type = bboxlog[seqno][0]
        region = RegionDescriptor(
            region_id=f"p{page_num}_r{len(regions) + 1:05d}",
            page=page_num,
            region_type="text",
            bbox=bbox,
            text=text,
            normalized_text=normalize_text(text),
            parser_text=text,
            rendered_text_estimate=text,
            rendered_text_confidence=None,
            text_semantic_source="texttrace_unicode",
            font_name=span.get("font"),
            font_size=float(span["size"]) if span.get("size") is not None else None,
            font_flags={
                "flags": span.get("flags"),
                "texttrace_type": span.get("type"),
                "bboxlog_type": bboxlog_type,
                "colorspace": span.get("colorspace"),
            },
            color=normalize_color(span.get("color")),
            background_color=config.default_background_color,
            alpha=float(span["opacity"]) if span.get("opacity") is not None else None,
            z_order=int(seqno) if isinstance(seqno, int) else local_idx,
            layer=span.get("layer") or None,
            source_object=page_obj,
            source_stream=f"page_{page_num}_texttrace",
            operator=bboxlog_type or "texttrace",
            operator_offset=int(seqno) if isinstance(seqno, int) else None,
        )
        regions.append(estimate_visibility(region, page_box, config))
    return apply_rendered_text_estimates(pdf_path, page_index, page_num, regions, config)


def _build_dict_regions(page: Any, page_num: int, config: DetectionConfig) -> List[RegionDescriptor]:
    page_box = _page_bbox(page)
    page_obj = _source_object(page)
    try:
        text_dict = page.get_text("dict", sort=False)
    except Exception:
        return []

    regions: List[RegionDescriptor] = []
    z_order = 0
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = str(span.get("text") or "")
                if not text.strip():
                    continue
                bbox = normalize_bbox(span.get("bbox"))
                if bbox is None:
                    continue
                region = RegionDescriptor(
                    region_id=f"p{page_num}_r{len(regions) + 1:05d}",
                    page=page_num,
                    region_type="text",
                    bbox=bbox,
                    text=text,
                    normalized_text=normalize_text(text),
                    parser_text=text,
                    rendered_text_estimate=text,
                    rendered_text_confidence=None,
                    text_semantic_source="dict_unicode",
                    font_name=span.get("font"),
                    font_size=float(span["size"]) if span.get("size") is not None else None,
                    font_flags={"flags": span.get("flags"), "fallback": "dict"},
                    color=normalize_color(span.get("color")),
                    background_color=config.default_background_color,
                    alpha=float(span["alpha"]) if span.get("alpha") is not None else None,
                    z_order=z_order,
                    source_object=page_obj,
                    source_stream=f"page_{page_num}_dict",
                    operator="dict_span",
                    operator_offset=z_order,
                )
                z_order += 1
                regions.append(estimate_visibility(region, page_box, config))
    return regions


def _build_paint_regions(page: Any, page_num: int, start_idx: int, config: DetectionConfig) -> List[RegionDescriptor]:
    page_box = _page_bbox(page)
    page_obj = _source_object(page)
    regions: List[RegionDescriptor] = []
    try:
        bboxlog = page.get_bboxlog()
    except Exception:
        return regions

    drawings_by_seq: Dict[int, Any] = {}
    try:
        for drawing in page.get_drawings():
            seqno = drawing.get("seqno")
            if isinstance(seqno, int):
                drawings_by_seq[seqno] = drawing
    except Exception:
        pass

    for seqno, item in enumerate(bboxlog):
        kind, raw_bbox = item[0], item[1]
        if "text" in str(kind):
            continue
        bbox = normalize_bbox(raw_bbox)
        if bbox is None:
            continue
        drawing = drawings_by_seq.get(seqno, {})
        fill = normalize_color(drawing.get("fill") if isinstance(drawing, dict) else None)
        alpha = None
        if isinstance(drawing, dict):
            alpha = drawing.get("fill_opacity", drawing.get("opacity"))
        region_type = "image" if "image" in str(kind) else "path"
        region = RegionDescriptor(
            region_id=f"p{page_num}_r{start_idx + len(regions) + 1:05d}",
            page=page_num,
            region_type=region_type,
            bbox=bbox,
            color=fill,
            background_color=config.default_background_color,
            alpha=float(alpha) if alpha is not None else None,
            z_order=seqno,
            source_object=page_obj,
            source_stream=f"page_{page_num}_bboxlog",
            operator=str(kind),
            operator_offset=seqno,
        )
        regions.append(estimate_visibility(region, page_box, config))
    return regions


def extract_pdf_regions(pdf_path: str, config: Optional[DetectionConfig] = None) -> List[RegionDescriptor]:
    """Build region-level render semantic descriptors from a PDF."""

    config = config or DetectionConfig()
    fitz = _require_fitz()
    doc = fitz.open(pdf_path)
    all_regions: List[RegionDescriptor] = []
    try:
        for page_index in range(len(doc)):
            page = doc.load_page(page_index)
            page_num = page_index + 1
            page_regions = _build_texttrace_regions(pdf_path, page, page_index, page_num, config)
            if not page_regions:
                page_regions = _build_dict_regions(page, page_num, config)
            paint_regions = _build_paint_regions(page, page_num, len(page_regions), config)
            all_regions.extend(page_regions + paint_regions)
    finally:
        doc.close()
    return apply_occlusion_estimate(all_regions, config)
