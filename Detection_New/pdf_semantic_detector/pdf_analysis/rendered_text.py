from __future__ import annotations

import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

from ..config import DetectionConfig
from ..models import BBox, RegionDescriptor
from .geometry import union_bbox
from .normalization import normalize_text


REFERENCE_CANDIDATES = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?-_()[]{}'\"/\\&%+*=<>"
REFERENCE_FONT_PATHS = [
    Path("C:/Windows/Fonts/times.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
]


@dataclass(slots=True)
class FontVisualInfo:
    resource_name: str
    xref: Optional[int]
    base_font: str
    font_bytes: Optional[bytes]
    has_to_unicode: bool
    has_unicode_cmap: bool
    has_symbolic_cmap: bool
    num_glyphs: Optional[int]
    cmap: Dict[int, int]

    @property
    def needs_shape_probe(self) -> bool:
        return bool(self.font_bytes) and not self.has_to_unicode and not self.has_unicode_cmap


@dataclass(slots=True)
class RenderedChar:
    parser_char: str
    rendered_char: str
    confidence: float
    font_resource: Optional[str]
    glyph_id: Optional[int]
    source: str


def _require_fitz():
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PyMuPDF is required for rendered text estimation.") from exc
    return fitz


def _require_pypdf():
    try:
        from pypdf import PdfReader  # type: ignore
        from pypdf.generic import ContentStream  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pypdf is required for rendered text estimation.") from exc
    return PdfReader, ContentStream


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack(">H", data[offset : offset + 2])[0]


def _i16(data: bytes, offset: int) -> int:
    return struct.unpack(">h", data[offset : offset + 2])[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack(">I", data[offset : offset + 4])[0]


def _table(data: bytes, tag: str) -> Optional[bytes]:
    if len(data) < 12:
        return None
    try:
        table_count = _u16(data, 4)
        for index in range(table_count):
            offset = 12 + index * 16
            if offset + 16 > len(data):
                break
            table_tag = data[offset : offset + 4].decode("latin1", errors="replace")
            table_offset = _u32(data, offset + 8)
            table_length = _u32(data, offset + 12)
            if table_tag == tag and table_offset + table_length <= len(data):
                return data[table_offset : table_offset + table_length]
    except Exception:
        return None
    return None


def _parse_maxp_num_glyphs(font_bytes: Optional[bytes]) -> Optional[int]:
    if not font_bytes:
        return None
    maxp = _table(font_bytes, "maxp")
    if not maxp or len(maxp) < 6:
        return None
    return _u16(maxp, 4)


def _parse_cmap_subtables(font_bytes: Optional[bytes]) -> List[Tuple[int, int, int, int]]:
    if not font_bytes:
        return []
    cmap = _table(font_bytes, "cmap")
    if not cmap or len(cmap) < 4:
        return []
    records: List[Tuple[int, int, int, int]] = []
    try:
        table_count = _u16(cmap, 2)
        for index in range(table_count):
            offset = 4 + index * 8
            if offset + 8 > len(cmap):
                break
            platform_id = _u16(cmap, offset)
            encoding_id = _u16(cmap, offset + 2)
            subtable_offset = _u32(cmap, offset + 4)
            if subtable_offset + 2 > len(cmap):
                continue
            fmt = _u16(cmap, subtable_offset)
            records.append((platform_id, encoding_id, fmt, subtable_offset))
    except Exception:
        return records
    return records


def _has_unicode_cmap(records: Iterable[Tuple[int, int, int, int]]) -> bool:
    for platform_id, encoding_id, _fmt, _offset in records:
        if platform_id == 0:
            return True
        if platform_id == 3 and encoding_id in {1, 10}:
            return True
    return False


def _has_symbolic_cmap(records: Iterable[Tuple[int, int, int, int]]) -> bool:
    return any(platform_id == 3 and encoding_id == 0 for platform_id, encoding_id, _fmt, _offset in records)


def _parse_cmap_map(font_bytes: Optional[bytes]) -> Dict[int, int]:
    if not font_bytes:
        return {}
    cmap = _table(font_bytes, "cmap")
    if not cmap:
        return {}
    records = _parse_cmap_subtables(font_bytes)
    chosen: Optional[Tuple[int, int, int, int]] = None
    for record in records:
        platform_id, encoding_id, fmt, _offset = record
        if fmt in {4, 12} and (platform_id == 0 or (platform_id == 3 and encoding_id in {1, 10})):
            chosen = record
            break
    if chosen is None:
        for record in records:
            if record[2] == 0:
                chosen = record
                break
    if chosen is None:
        for record in records:
            if record[2] == 4:
                chosen = record
                break
    if chosen is None:
        return {}

    _platform_id, _encoding_id, fmt, offset = chosen
    if fmt == 0:
        glyphs = cmap[offset + 6 : offset + 262]
        return {code: gid for code, gid in enumerate(glyphs) if gid}
    if fmt == 4:
        out: Dict[int, int] = {}
        seg_count = _u16(cmap, offset + 6) // 2
        end_offset = offset + 14
        start_offset = end_offset + 2 * seg_count + 2
        delta_offset = start_offset + 2 * seg_count
        range_offset = delta_offset + 2 * seg_count
        for segment in range(seg_count):
            end_code = _u16(cmap, end_offset + 2 * segment)
            start_code = _u16(cmap, start_offset + 2 * segment)
            delta = _i16(cmap, delta_offset + 2 * segment)
            range_off = _u16(cmap, range_offset + 2 * segment)
            for code in range(start_code, min(end_code, 0xFFFF) + 1):
                if code == 0xFFFF:
                    continue
                if range_off == 0:
                    gid = (code + delta) & 0xFFFF
                else:
                    glyph_offset = range_offset + 2 * segment + range_off + 2 * (code - start_code)
                    if glyph_offset + 2 > len(cmap):
                        continue
                    glyph_index = _u16(cmap, glyph_offset)
                    gid = 0 if glyph_index == 0 else (glyph_index + delta) & 0xFFFF
                if gid:
                    out[code] = gid
        return out
    return {}


def _glyph_offsets(font_bytes: bytes) -> List[int]:
    head = _table(font_bytes, "head")
    loca = _table(font_bytes, "loca")
    glyph_count = _parse_maxp_num_glyphs(font_bytes)
    if not head or not loca or glyph_count is None:
        return []
    index_to_loc_format = _i16(head, 50)
    if index_to_loc_format == 0:
        return [_u16(loca, 2 * i) * 2 for i in range(glyph_count + 1)]
    return [_u32(loca, 4 * i) for i in range(glyph_count + 1)]


def _glyph_contours(font_bytes: bytes, glyph_id: int) -> List[List[Tuple[float, float, bool]]]:
    glyf = _table(font_bytes, "glyf")
    offsets = _glyph_offsets(font_bytes)
    if not glyf or glyph_id < 0 or glyph_id + 1 >= len(offsets):
        return []
    start, end = offsets[glyph_id], offsets[glyph_id + 1]
    if start == end or end > len(glyf):
        return []
    glyph = glyf[start:end]
    if len(glyph) < 10:
        return []
    contour_count = _i16(glyph, 0)
    if contour_count <= 0:
        return []
    end_points = [_u16(glyph, 10 + 2 * i) for i in range(contour_count)]
    if not end_points:
        return []
    instruction_length = _u16(glyph, 10 + 2 * contour_count)
    cursor = 10 + 2 * contour_count + 2 + instruction_length
    point_count = end_points[-1] + 1
    flags: List[int] = []
    while len(flags) < point_count and cursor < len(glyph):
        flag = glyph[cursor]
        cursor += 1
        flags.append(flag)
        if flag & 0x08 and cursor < len(glyph):
            repeat = glyph[cursor]
            cursor += 1
            flags.extend([flag] * repeat)
    if len(flags) < point_count:
        return []

    xs: List[int] = []
    x = 0
    for flag in flags[:point_count]:
        if flag & 0x02:
            if cursor >= len(glyph):
                return []
            dx = glyph[cursor]
            cursor += 1
            x += dx if flag & 0x10 else -dx
        else:
            if flag & 0x10:
                dx = 0
            else:
                if cursor + 2 > len(glyph):
                    return []
                dx = _i16(glyph, cursor)
                cursor += 2
                x += dx
        xs.append(x)

    ys: List[int] = []
    y = 0
    for flag in flags[:point_count]:
        if flag & 0x04:
            if cursor >= len(glyph):
                return []
            dy = glyph[cursor]
            cursor += 1
            y += dy if flag & 0x20 else -dy
        else:
            if flag & 0x20:
                dy = 0
            else:
                if cursor + 2 > len(glyph):
                    return []
                dy = _i16(glyph, cursor)
                cursor += 2
                y += dy
        ys.append(y)

    contours: List[List[Tuple[float, float, bool]]] = []
    start_index = 0
    for end_index in end_points:
        contour = [
            (float(xs[i]), float(ys[i]), bool(flags[i] & 0x01))
            for i in range(start_index, end_index + 1)
        ]
        contours.append(contour)
        start_index = end_index + 1
    return contours


def _contour_to_polyline(contour: List[Tuple[float, float, bool]]) -> List[Tuple[float, float]]:
    if not contour:
        return []

    def midpoint(a: Tuple[float, float, bool], b: Tuple[float, float, bool]) -> Tuple[float, float, bool]:
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, True)

    points = list(contour)
    if not points[0][2]:
        if points[-1][2]:
            points = [points[-1]] + points[:-1]
        else:
            points = [midpoint(points[-1], points[0])] + points

    polyline: List[Tuple[float, float]] = [(points[0][0], points[0][1])]
    current = points[0]
    index = 1
    while index < len(points) + 1:
        nxt = points[index % len(points)]
        if nxt[2]:
            polyline.append((nxt[0], nxt[1]))
            current = nxt
            index += 1
            continue

        after = points[(index + 1) % len(points)]
        end_point = after if after[2] else midpoint(nxt, after)
        for step in range(1, 9):
            t = step / 8.0
            x = (1 - t) ** 2 * current[0] + 2 * (1 - t) * t * nxt[0] + t**2 * end_point[0]
            y = (1 - t) ** 2 * current[1] + 2 * (1 - t) * t * nxt[1] + t**2 * end_point[1]
            polyline.append((x, y))
        current = end_point
        index += 2 if after[2] else 1
    return polyline


@lru_cache(maxsize=4096)
def _glyph_outline_image(font_bytes: bytes, glyph_id: int) -> Optional[np.ndarray]:
    contours = _glyph_contours(font_bytes, glyph_id)
    polylines = [_contour_to_polyline(contour) for contour in contours]
    all_points = [point for polyline in polylines for point in polyline]
    if not all_points:
        return None
    xs = [point[0] for point in all_points]
    ys = [point[1] for point in all_points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        return None
    scale = 54.0 / max(width, height)
    image = Image.new("L", (64, 64), 0)
    draw = ImageDraw.Draw(image)
    for polyline in polylines:
        if len(polyline) < 2:
            continue
        xy = [((x - min_x) * scale + 5, 59 - (y - min_y) * scale) for x, y in polyline]
        draw.line(xy + [xy[0]], fill=255, width=2)
    return np.array(image) > 0


def _shape_similarity(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> float:
    if a is None or b is None:
        return 0.0
    intersection = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(intersection / union) if union else 0.0


@lru_cache(maxsize=1)
def _reference_glyphs() -> Dict[str, np.ndarray]:
    for path in REFERENCE_FONT_PATHS:
        if not path.exists():
            continue
        font_bytes = path.read_bytes()
        cmap = _parse_cmap_map(font_bytes)
        refs: Dict[str, np.ndarray] = {}
        for char in REFERENCE_CANDIDATES:
            glyph_id = cmap.get(ord(char))
            if glyph_id is None:
                continue
            image = _glyph_outline_image(font_bytes, glyph_id)
            if image is not None:
                refs[char] = image
        if refs:
            return refs
    return {}


@lru_cache(maxsize=8192)
def _classify_glyph(font_bytes: bytes, glyph_id: int) -> Tuple[Optional[str], float]:
    image = _glyph_outline_image(font_bytes, glyph_id)
    refs = _reference_glyphs()
    if image is None or not refs:
        return None, 0.0
    best_char: Optional[str] = None
    best_score = 0.0
    for char, ref_image in refs.items():
        score = _shape_similarity(image, ref_image)
        if score > best_score:
            best_char = char
            best_score = score
    return best_char, best_score


def _font_dict_by_resource(page: Any) -> Dict[str, Any]:
    try:
        fonts = page["/Resources"]["/Font"]
    except Exception:
        return {}
    out: Dict[str, Any] = {}
    for name, ref in fonts.items():
        try:
            out[str(name)] = ref.get_object()
        except Exception:
            out[str(name)] = ref
    return out


def _page_font_infos(pdf_path: str, page_index: int, reader_page: Any) -> Dict[str, FontVisualInfo]:
    fitz = _require_fitz()
    font_dicts = _font_dict_by_resource(reader_page)
    doc = fitz.open(pdf_path)
    try:
        fitz_page = doc.load_page(page_index)
        fitz_fonts = {f"/{item[4]}": item for item in fitz_page.get_fonts(full=True)}
        infos: Dict[str, FontVisualInfo] = {}
        for resource_name, font_obj in font_dicts.items():
            fitz_font = fitz_fonts.get(resource_name)
            xref = int(fitz_font[0]) if fitz_font and fitz_font[0] else None
            font_bytes: Optional[bytes] = None
            base_font = str(font_obj.get("/BaseFont", "")) if hasattr(font_obj, "get") else ""
            if xref:
                try:
                    extracted = doc.extract_font(xref)
                    base_font = str(extracted[0] or base_font)
                    font_bytes = extracted[3]
                except Exception:
                    font_bytes = None
            cmap_records = _parse_cmap_subtables(font_bytes)
            infos[resource_name] = FontVisualInfo(
                resource_name=resource_name,
                xref=xref,
                base_font=base_font,
                font_bytes=font_bytes,
                has_to_unicode=bool(font_obj.get("/ToUnicode")) if hasattr(font_obj, "get") else False,
                has_unicode_cmap=_has_unicode_cmap(cmap_records),
                has_symbolic_cmap=_has_symbolic_cmap(cmap_records),
                num_glyphs=_parse_maxp_num_glyphs(font_bytes),
                cmap=_parse_cmap_map(font_bytes),
            )
        return infos
    finally:
        doc.close()


def _text_from_operand(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("latin1", errors="replace")
    return str(value)


def _text_from_tj_array(value: object) -> str:
    if not isinstance(value, (list, tuple)):
        return _text_from_operand(value)
    parts: List[str] = []
    for item in value:
        if isinstance(item, (int, float)):
            continue
        parts.append(_text_from_operand(item))
    return "".join(parts)


def _rendered_chars_for_page(pdf_path: str, page_index: int) -> List[RenderedChar]:
    PdfReader, ContentStream = _require_pypdf()
    reader = PdfReader(pdf_path)
    page = reader.pages[page_index]
    font_infos = _page_font_infos(pdf_path, page_index, page)
    content_stream = ContentStream(page.get_contents(), reader)

    current_font: Optional[str] = None
    rendered_chars: List[RenderedChar] = []
    for operands, operator in content_stream.operations:
        if operator == b"Tf" and operands:
            current_font = str(operands[0])
            continue

        text = ""
        if operator == b"Tj" and operands:
            text = _text_from_operand(operands[0])
        elif operator == b"TJ" and operands:
            text = _text_from_tj_array(operands[0])
        elif operator in {b"'", b'"'} and operands:
            text = _text_from_operand(operands[-1])

        if not text:
            continue

        info = font_infos.get(current_font or "")
        for char in text:
            if char.isspace() or info is None or not info.needs_shape_probe or not info.font_bytes:
                rendered_chars.append(
                    RenderedChar(char, char, 1.0, current_font, None, "parser_char")
                )
                continue
            glyph_id = info.cmap.get(ord(char))
            if glyph_id is None:
                rendered_chars.append(
                    RenderedChar(char, char, 0.0, current_font, None, "missing_cmap")
                )
                continue
            visual_char, confidence = _classify_glyph(info.font_bytes, glyph_id)
            if visual_char is None or confidence < 0.45:
                visual_char = char
                source = "glyph_shape_low_confidence"
            else:
                source = "glyph_shape"
            rendered_chars.append(
                RenderedChar(char, visual_char, confidence, current_font, glyph_id, source)
            )
    return rendered_chars


def _mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _apply_char_estimates(regions: List[RegionDescriptor], chars: List[RenderedChar]) -> None:
    cursor = 0
    for region in regions:
        if region.region_type != "text" or not region.text:
            continue
        length = len(region.text)
        chunk = chars[cursor : cursor + length]
        cursor += length
        if len(chunk) != length:
            region.parser_text = region.text
            region.rendered_text_estimate = region.text
            region.rendered_text_confidence = None
            continue

        parser_text = "".join(char.parser_char for char in chunk)
        rendered_text = "".join(char.rendered_char for char in chunk)
        confidences = [char.confidence for char in chunk if char.source == "glyph_shape"]
        sources = [char.source for char in chunk]
        region.parser_text = parser_text
        region.rendered_text_estimate = rendered_text
        region.rendered_text_confidence = _mean(confidences)
        if any(source == "glyph_shape" for source in sources):
            region.text_semantic_source = "glyph_shape"
            region.text = rendered_text
            region.normalized_text = normalize_text(rendered_text)
            if parser_text != rendered_text:
                if region.font_flags is None:
                    region.font_flags = {}
                region.font_flags["semantic_drift"] = True
                region.font_flags["parser_text"] = parser_text
                region.font_flags["rendered_text_estimate"] = rendered_text
                region.font_flags["rendered_text_confidence"] = region.rendered_text_confidence
                region.font_flags["char_mappings"] = [
                    {
                        "parser_char": char.parser_char,
                        "rendered_char": char.rendered_char,
                        "font_resource": char.font_resource,
                        "glyph_id": char.glyph_id,
                        "confidence": round(char.confidence, 6),
                        "source": char.source,
                    }
                    for char in chunk
                ]
        else:
            region.text_semantic_source = "texttrace_unicode"
            region.rendered_text_estimate = region.text


def _group_drift_regions_into_lines(
    page_num: int,
    regions: List[RegionDescriptor],
    start_index: int,
    config: DetectionConfig,
) -> List[RegionDescriptor]:
    glyph_regions = [
        region
        for region in regions
        if region.region_type == "text"
        and region.text_semantic_source == "glyph_shape"
        and region.rendered_text_estimate
    ]
    if not glyph_regions:
        return []

    if not any(region.font_flags and region.font_flags.get("semantic_drift") for region in glyph_regions):
        return []

    sorted_regions = sorted(glyph_regions, key=lambda r: ((r.bbox[1] + r.bbox[3]) / 2.0, r.bbox[0]))
    lines: List[List[RegionDescriptor]] = []
    for region in sorted_regions:
        cy = (region.bbox[1] + region.bbox[3]) / 2.0
        placed = False
        for line in lines:
            ref = line[0]
            ref_cy = (ref.bbox[1] + ref.bbox[3]) / 2.0
            tolerance = max(3.0, (region.font_size or ref.font_size or 10.0) * 0.7)
            if abs(cy - ref_cy) <= tolerance:
                line.append(region)
                placed = True
                break
        if not placed:
            lines.append([region])

    line_regions: List[RegionDescriptor] = []
    for line in lines:
        line.sort(key=lambda r: r.bbox[0])
        rendered_parts: List[str] = []
        parser_parts: List[str] = []
        prev: Optional[RegionDescriptor] = None
        widths = [(r.bbox[2] - r.bbox[0]) / max(len(r.rendered_text_estimate or r.text or ""), 1) for r in line]
        median_width = sorted(widths)[len(widths) // 2] if widths else 3.0
        for region in line:
            if prev is not None:
                gap = region.bbox[0] - prev.bbox[2]
                threshold = max(2.0, median_width * 0.65)
                if gap > threshold:
                    rendered_parts.append(" ")
                    parser_parts.append(" ")
            rendered_parts.append(region.rendered_text_estimate or region.text or "")
            parser_parts.append(region.parser_text or "")
            prev = region

        rendered_text = "".join(rendered_parts).strip()
        parser_text = "".join(parser_parts).strip()
        if len(rendered_text) < 3 or rendered_text == parser_text:
            continue
        bbox = union_bbox([region.bbox for region in line])
        if bbox is None:
            continue
        confidence = _mean([r.rendered_text_confidence for r in line if r.rendered_text_confidence is not None])
        line_region = RegionDescriptor(
            region_id=f"p{page_num}_r{start_index + len(line_regions) + 1:05d}",
            page=page_num,
            region_type="text",
            bbox=bbox,
            text=rendered_text,
            normalized_text=normalize_text(rendered_text),
            parser_text=parser_text,
            rendered_text_estimate=rendered_text,
            rendered_text_confidence=confidence,
            text_semantic_source="glyph_shape_line",
            font_name=line[0].font_name,
            font_size=line[0].font_size,
            font_flags={
                "aggregated": "rendered_text_line",
                "semantic_drift": True,
                "parser_text": parser_text,
                "rendered_text_estimate": rendered_text,
                "rendered_text_confidence": confidence,
                "source_regions": [region.region_id for region in line],
            },
            color=line[0].color,
            background_color=line[0].background_color,
            alpha=line[0].alpha,
            z_order=min((region.z_order or 0) for region in line),
            source_stream=f"page_{page_num}_rendered_text_estimate",
            operator="glyph_shape_line",
            visibility_score=1.0,
            visibility_status="visible",
        )
        line_regions.append(line_region)
    return line_regions


def apply_rendered_text_estimates(
    pdf_path: str,
    page_index: int,
    page_num: int,
    regions: List[RegionDescriptor],
    config: DetectionConfig,
) -> List[RegionDescriptor]:
    try:
        rendered_chars = _rendered_chars_for_page(pdf_path, page_index)
    except Exception:
        for region in regions:
            if region.region_type == "text":
                region.parser_text = region.text
                region.rendered_text_estimate = region.text
                region.text_semantic_source = "texttrace_unicode"
        return regions

    _apply_char_estimates(regions, rendered_chars)
    line_regions = _group_drift_regions_into_lines(page_num, regions, len(regions), config)
    return regions + line_regions
