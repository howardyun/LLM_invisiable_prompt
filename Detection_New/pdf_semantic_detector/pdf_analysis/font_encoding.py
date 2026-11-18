from __future__ import annotations

import re
import struct
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..config import DetectionConfig
from ..models import RegionDescriptor

WORD_RE = re.compile(r"[A-Za-z]{3,}")


@dataclass(slots=True)
class FontProgramInfo:
    resource_name: str
    xref: Optional[int]
    base_font: str
    subtype: str
    embedded: bool
    has_to_unicode: bool
    has_encoding: bool
    font_type: Optional[str] = None
    font_ext: Optional[str] = None
    num_glyphs: Optional[int] = None
    cmap_subtables: List[Tuple[int, int, int]] = None  # type: ignore[assignment]
    has_unicode_cmap: bool = False
    has_symbolic_cmap: bool = False
    parse_error: Optional[str] = None

    @property
    def untrusted_text_mapping(self) -> bool:
        return self.embedded and not self.has_to_unicode and not self.has_unicode_cmap

    @property
    def tiny_subset(self) -> bool:
        return self.num_glyphs is not None and self.num_glyphs <= 12


@dataclass(slots=True)
class FontEncodingIssue:
    issue_id: str
    page: int
    risk_score: float
    text: str
    reasons: List[str]
    evidence: Dict[str, object]


def _semantic_preview_by_page(regions: Optional[List[RegionDescriptor]]) -> Dict[int, Dict[str, str]]:
    if not regions:
        return {}

    page_lines: Dict[int, List[RegionDescriptor]] = defaultdict(list)
    for region in regions:
        if region.region_type != "text":
            continue
        if region.text_semantic_source != "glyph_shape_line":
            continue
        if not region.rendered_text_estimate:
            continue
        page_lines[region.page].append(region)

    previews: Dict[int, Dict[str, str]] = {}
    for page, lines in page_lines.items():
        lines.sort(key=lambda region: (region.bbox[1], region.bbox[0]))
        rendered = "\n".join((line.rendered_text_estimate or "").strip() for line in lines).strip()
        parser = "\n".join((line.parser_text or "").strip() for line in lines).strip()
        if rendered:
            previews[page] = {
                "rendered_text": rendered,
                "parser_text": parser,
                "source": "glyph_shape_line",
            }
    return previews


def _require_fitz():
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PyMuPDF is required for font encoding analysis.") from exc
    return fitz


def _require_pypdf():
    try:
        from pypdf import PdfReader  # type: ignore
        from pypdf.generic import ContentStream  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pypdf is required for font encoding analysis.") from exc
    return PdfReader, ContentStream


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack(">H", data[offset : offset + 2])[0]


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


def _parse_cmap_subtables(font_bytes: Optional[bytes]) -> List[Tuple[int, int, int]]:
    if not font_bytes:
        return []
    cmap = _table(font_bytes, "cmap")
    if not cmap or len(cmap) < 4:
        return []
    records: List[Tuple[int, int, int]] = []
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
            records.append((platform_id, encoding_id, fmt))
    except Exception:
        return records
    return records


def _has_unicode_cmap(records: Iterable[Tuple[int, int, int]]) -> bool:
    for platform_id, encoding_id, _fmt in records:
        if platform_id == 0:
            return True
        if platform_id == 3 and encoding_id in {1, 10}:
            return True
    return False


def _has_symbolic_cmap(records: Iterable[Tuple[int, int, int]]) -> bool:
    return any(platform_id == 3 and encoding_id == 0 for platform_id, encoding_id, _fmt in records)


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


def _page_font_infos(pdf_path: str, page_index: int, reader_page: Any) -> Dict[str, FontProgramInfo]:
    fitz = _require_fitz()
    font_dicts = _font_dict_by_resource(reader_page)
    doc = fitz.open(pdf_path)
    try:
        fitz_page = doc.load_page(page_index)
        fitz_fonts = {f"/{item[4]}": item for item in fitz_page.get_fonts(full=True)}
        infos: Dict[str, FontProgramInfo] = {}
        for resource_name, font_obj in font_dicts.items():
            fitz_font = fitz_fonts.get(resource_name)
            xref = int(fitz_font[0]) if fitz_font and fitz_font[0] else None
            font_bytes: Optional[bytes] = None
            font_name = str(font_obj.get("/BaseFont", "")) if hasattr(font_obj, "get") else ""
            font_ext = None
            font_type = None
            parse_error = None
            if xref:
                try:
                    extracted = doc.extract_font(xref)
                    font_name = str(extracted[0] or font_name)
                    font_ext = str(extracted[1] or "")
                    font_type = str(extracted[2] or "")
                    font_bytes = extracted[3]
                except Exception as exc:
                    parse_error = str(exc)

            cmap_subtables = _parse_cmap_subtables(font_bytes)
            subtype = str(font_obj.get("/Subtype", "")) if hasattr(font_obj, "get") else ""
            info = FontProgramInfo(
                resource_name=resource_name,
                xref=xref,
                base_font=font_name,
                subtype=subtype,
                embedded=bool(font_bytes),
                has_to_unicode=bool(font_obj.get("/ToUnicode")) if hasattr(font_obj, "get") else False,
                has_encoding=bool(font_obj.get("/Encoding")) if hasattr(font_obj, "get") else False,
                font_type=font_type,
                font_ext=font_ext,
                num_glyphs=_parse_maxp_num_glyphs(font_bytes),
                cmap_subtables=cmap_subtables,
                has_unicode_cmap=_has_unicode_cmap(cmap_subtables),
                has_symbolic_cmap=_has_symbolic_cmap(cmap_subtables),
                parse_error=parse_error,
            )
            infos[resource_name] = info
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


def _prose_word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def _natural_text_ratio(text: str) -> float:
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return 0.0
    natural = sum(1 for ch in chars if ch.isalpha() or ch.isdigit() or ch in ".,;:!?'-_()")
    return natural / len(chars)


def _score_issue(
    untrusted_ratio: float,
    tiny_ratio: float,
    font_switch_density: float,
    unique_untrusted_fonts: int,
    avg_chars_per_show: float,
) -> float:
    score = 0.35 * untrusted_ratio + 0.25 * tiny_ratio
    score += 0.20 * min(1.0, font_switch_density / 0.50)
    score += 0.10 * min(1.0, unique_untrusted_fonts / 12.0)
    if avg_chars_per_show <= 2.0:
        score += 0.10
    elif avg_chars_per_show <= 4.0:
        score += 0.05
    return round(max(0.0, min(1.0, score)), 6)


def detect_font_encoding_issues(
    pdf_path: str,
    config: DetectionConfig,
    regions: Optional[List[RegionDescriptor]] = None,
) -> List[FontEncodingIssue]:
    if not config.enable_font_encoding_analysis:
        return []

    PdfReader, ContentStream = _require_pypdf()
    reader = PdfReader(pdf_path)
    issues: List[FontEncodingIssue] = []
    semantic_previews = _semantic_preview_by_page(regions)

    for page_index, page in enumerate(reader.pages):
        font_infos = _page_font_infos(pdf_path, page_index, page)
        try:
            content_stream = ContentStream(page.get_contents(), reader)
        except Exception:
            continue

        current_font: Optional[str] = None
        text_parts: List[str] = []
        chars_by_font: Counter[str] = Counter()
        text_show_count = 0
        font_switches = 0
        used_fonts: List[str] = []

        for operands, operator in content_stream.operations:
            if operator == b"Tf" and operands:
                next_font = str(operands[0])
                if current_font is not None and next_font != current_font:
                    font_switches += 1
                current_font = next_font
                used_fonts.append(next_font)
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
            text_show_count += 1
            text_parts.append(text)
            if current_font is not None:
                chars_by_font[current_font] += len(text)

        page_text = "".join(text_parts).strip()
        total_chars = sum(len(part) for part in text_parts)
        if total_chars < config.encoding_min_chars:
            continue
        if _prose_word_count(page_text) < config.encoding_min_words:
            continue
        if _natural_text_ratio(page_text) < 0.70:
            continue

        untrusted_chars = 0
        tiny_chars = 0
        untrusted_fonts: List[str] = []
        tiny_fonts: List[str] = []
        font_samples: Dict[str, object] = {}

        for font_name, char_count in chars_by_font.items():
            info = font_infos.get(font_name)
            if info is None:
                continue
            if info.untrusted_text_mapping:
                untrusted_chars += char_count
                untrusted_fonts.append(font_name)
            if info.untrusted_text_mapping and info.tiny_subset:
                tiny_chars += char_count
                tiny_fonts.append(font_name)
            font_samples[font_name] = {
                "base_font": info.base_font,
                "subtype": info.subtype,
                "xref": info.xref,
                "embedded": info.embedded,
                "has_to_unicode": info.has_to_unicode,
                "has_unicode_cmap": info.has_unicode_cmap,
                "has_symbolic_cmap": info.has_symbolic_cmap,
                "cmap_subtables": info.cmap_subtables,
                "num_glyphs": info.num_glyphs,
                "chars": char_count,
            }

        untrusted_ratio = untrusted_chars / max(total_chars, 1)
        tiny_ratio = tiny_chars / max(total_chars, 1)
        unique_untrusted_fonts = len(set(untrusted_fonts))
        font_switch_density = font_switches / max(total_chars, 1)
        avg_chars_per_show = total_chars / max(text_show_count, 1)

        reasons: List[str] = []
        if untrusted_ratio >= config.encoding_untrusted_ratio:
            reasons.append("untrusted_font_text_mapping")
        if tiny_ratio >= config.encoding_tiny_font_ratio:
            reasons.append("tiny_embedded_subset_fonts")
        if unique_untrusted_fonts >= config.encoding_min_unique_fonts:
            reasons.append("many_untrusted_font_resources")
        if font_switch_density >= config.encoding_font_switch_density:
            reasons.append("high_frequency_font_switching")
        if avg_chars_per_show <= config.encoding_max_avg_chars_per_show:
            reasons.append("short_text_show_chunks")

        suspicious = (
            "untrusted_font_text_mapping" in reasons
            and "tiny_embedded_subset_fonts" in reasons
            and "many_untrusted_font_resources" in reasons
            and ("high_frequency_font_switching" in reasons or "short_text_show_chunks" in reasons)
        )
        if not suspicious:
            continue

        score = _score_issue(
            untrusted_ratio,
            tiny_ratio,
            font_switch_density,
            unique_untrusted_fonts,
            avg_chars_per_show,
        )
        semantic_preview = semantic_previews.get(page_index + 1, {})
        rendered_text = semantic_preview.get("rendered_text") or page_text
        parser_text_preview = semantic_preview.get("parser_text") or page_text
        rendered_text_source = semantic_preview.get("source") or "content_stream_text"
        issues.append(
            FontEncodingIssue(
                issue_id=f"enc_p{page_index + 1:04d}_{len(issues) + 1:04d}",
                page=page_index + 1,
                risk_score=score,
                text=rendered_text,
                reasons=reasons,
                evidence={
                    "total_chars": total_chars,
                    "text_show_count": text_show_count,
                    "font_switches": font_switches,
                    "font_switch_density": round(font_switch_density, 6),
                    "avg_chars_per_text_show": round(avg_chars_per_show, 6),
                    "untrusted_char_ratio": round(untrusted_ratio, 6),
                    "tiny_subset_char_ratio": round(tiny_ratio, 6),
                    "unique_fonts": len(set(used_fonts)),
                    "unique_untrusted_fonts": unique_untrusted_fonts,
                    "untrusted_fonts": sorted(set(untrusted_fonts)),
                    "tiny_subset_fonts": sorted(set(tiny_fonts)),
                    "font_samples": font_samples,
                    "text_preview": rendered_text[:300],
                    "rendered_text_preview": rendered_text[:300],
                    "parser_text_preview": parser_text_preview[:300],
                    "rendered_text_source": rendered_text_source,
                },
            )
        )

    return issues
