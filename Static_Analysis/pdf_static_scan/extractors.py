from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from collections import deque
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

from .config import ScanConfig
from .schema import PDFObject
from .utils import (
    count_signature_markers,
    object_ref_key,
    pdf_value_to_text,
    rect_to_bbox,
    resolve_pdf_obj,
    safe_name,
)


def extract_text_spans(fitz_doc: Any, config: ScanConfig | None = None) -> List[PDFObject]:
    objects: List[PDFObject] = []
    if fitz_doc is None:
        return objects
    for page_index in range(len(fitz_doc)):
        page = fitz_doc.load_page(page_index)
        rect = page.rect
        page_width = float(rect.width)
        page_height = float(rect.height)
        trace_items = _safe_texttrace(page) if config is None or config.enable_texttrace_visibility else []
        data = page.get_text("dict")
        for block_no, block in enumerate(data.get("blocks", [])):
            if block.get("type", 0) != 0:
                continue
            for line_no, line in enumerate(block.get("lines", [])):
                for span_no, span in enumerate(line.get("spans", [])):
                    text = str(span.get("text", ""))
                    if not text or not text.strip():
                        continue
                    bbox = _tuple_bbox(span.get("bbox"))
                    trace = _best_trace_match(bbox, span, trace_items)
                    color = span.get("color")
                    alpha = span.get("alpha", span.get("opacity"))
                    if trace is not None:
                        color = span.get("color", trace.get("color"))
                        alpha = span.get("alpha", span.get("opacity", trace.get("opacity")))
                    size = span.get("size")
                    object_id = f"text:p{page_index + 1}:b{block_no}:l{line_no}:s{span_no}"
                    attrs = {
                        "block_no": block_no,
                        "line_no": line_no,
                        "span_no": span_no,
                        "origin": list(span.get("origin", ())) or None,
                        "page_width": page_width,
                        "page_height": page_height,
                        "font_name": span.get("font"),
                        "font_size": size,
                        "color_rgb": color,
                        "alpha": alpha,
                        "alpha_raw": alpha,
                        "opacity": trace.get("opacity") if trace else None,
                        "texttrace_type": trace.get("type") if trace else None,
                        "texttrace_seqno": trace.get("seqno") if trace else None,
                        "texttrace_bbox": list(trace.get("bbox", ())) if trace else None,
                        "layer": trace.get("layer") if trace else None,
                        "raw_color": color,
                        "font_flags": span.get("flags"),
                        "writing_mode": line.get("wmode"),
                        "char_count": len(text),
                    }
                    objects.append(
                        PDFObject(
                            object_id=object_id,
                            object_type="text_span",
                            source="content_stream",
                            page_id=page_index + 1,
                            bbox=bbox,
                            text=text,
                            raw_value=None,
                            attrs=attrs,
                        )
                    )
    return objects


def extract_pypdf_page_text(reader: Any, text_span_objects: Sequence[PDFObject]) -> List[PDFObject]:
    objects: List[PDFObject] = []
    if reader is None:
        return objects
    pymupdf_by_page: Dict[int, str] = {}
    for obj in text_span_objects:
        if obj.page_id is None or obj.text is None:
            continue
        pymupdf_by_page.setdefault(obj.page_id, "")
        pymupdf_by_page[obj.page_id] += " " + obj.text
    pages = getattr(reader, "pages", [])
    for page_index, page in enumerate(pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        if not text.strip():
            continue
        page_id = page_index + 1
        if _compact_text(text) == _compact_text(pymupdf_by_page.get(page_id, "")):
            continue
        objects.append(
            PDFObject(
                object_id=f"parser_text:p{page_id}:pypdf",
                object_type="parser_text",
                source="pypdf_extract_text",
                page_id=page_id,
                bbox=None,
                text=text,
                raw_value=text,
                attrs={"parser": "pypdf", "char_count": len(text)},
            )
        )
    return objects


def extract_metadata(reader: Any, config: ScanConfig) -> List[PDFObject]:
    objects: List[PDFObject] = []
    if reader is None:
        return objects
    metadata = getattr(reader, "metadata", None)
    if metadata:
        try:
            iterator = metadata.items()
        except Exception:
            iterator = []
        for key, value in iterator:
            text = pdf_value_to_text(value)
            if not text:
                continue
            key_text = str(key)
            objects.append(
                PDFObject(
                    object_id=f"metadata:info:{safe_name(key_text)}",
                    object_type="metadata",
                    source="info_dict",
                    page_id=None,
                    bbox=None,
                    text=text,
                    raw_value=text,
                    attrs={"metadata_key": key_text},
                )
            )

    xmp_text = _extract_raw_xmp(reader, config.max_metadata_bytes)
    if xmp_text:
        parsed = _parse_xmp_fields(xmp_text)
        if parsed:
            for idx, (tag, text) in enumerate(parsed):
                objects.append(
                    PDFObject(
                        object_id=f"metadata:xmp:{safe_name(tag)}:{idx}",
                        object_type="metadata",
                        source="xmp",
                        page_id=None,
                        bbox=None,
                        text=text,
                        raw_value=text,
                        attrs={"metadata_key": tag},
                    )
                )
        else:
            objects.append(
                PDFObject(
                    object_id="metadata:xmp:raw",
                    object_type="metadata",
                    source="xmp",
                    page_id=None,
                    bbox=None,
                    text=xmp_text,
                    raw_value=xmp_text,
                    attrs={"metadata_key": "raw_xmp", "parse_error": True},
                )
            )
    return objects


def extract_annotations(reader: Any, fitz_doc: Any) -> List[PDFObject]:
    if reader is not None:
        objects = _extract_annotations_pypdf(reader)
        if objects:
            return objects
    return _extract_annotations_fitz(fitz_doc)


def extract_forms(reader: Any) -> List[PDFObject]:
    objects: List[PDFObject] = []
    if reader is None:
        return objects
    fields: Dict[str, Any] = {}
    try:
        fields = reader.get_fields() or {}
    except Exception:
        fields = {}
    for field_name, field in fields.items():
        field = resolve_pdf_obj(field)
        field_type = pdf_value_to_text(_dict_get(field, "/FT"))
        for key in ("/V", "/DV", "/TU", "/TM", "/RV"):
            value = _dict_get(field, key)
            text = pdf_value_to_text(value)
            if not text:
                continue
            objects.append(
                PDFObject(
                    object_id=f"form:{safe_name(field_name)}:{safe_name(key)}",
                    object_type="form",
                    source="acroform",
                    page_id=None,
                    bbox=None,
                    text=text,
                    raw_value=text,
                    attrs={
                        "field_name": str(field_name),
                        "field_key": key,
                        "field_type": field_type,
                        "has_appearance": _dict_get(field, "/AP") is not None,
                    },
                )
            )
    return objects


def extract_ocg(reader: Any) -> List[PDFObject]:
    objects: List[PDFObject] = []
    if reader is None:
        return objects
    root = _reader_root(reader)
    ocprops = resolve_pdf_obj(_dict_get(root, "/OCProperties"))
    if not ocprops:
        return objects
    default_config = resolve_pdf_obj(_dict_get(ocprops, "/D")) or {}
    off_refs = _ref_set(_dict_get(default_config, "/OFF"))
    on_refs = _ref_set(_dict_get(default_config, "/ON"))
    base_state = pdf_value_to_text(_dict_get(default_config, "/BaseState"))
    ocgs = resolve_pdf_obj(_dict_get(ocprops, "/OCGs")) or []
    for idx, group_ref in enumerate(_iter_array(ocgs)):
        group = resolve_pdf_obj(group_ref)
        name = pdf_value_to_text(_dict_get(group, "/Name")) or f"OCG-{idx}"
        ref_key = object_ref_key(group_ref)
        state = "off" if ref_key in off_refs else "on" if ref_key in on_refs else "unknown"
        objects.append(
            PDFObject(
                object_id=f"ocg:group:{idx}:{safe_name(name)}",
                object_type="ocg",
                source="ocproperties",
                page_id=None,
                bbox=None,
                text=name,
                raw_value=name,
                attrs={
                    "ocg_name": name,
                    "ocg_default_state": state,
                    "base_state": base_state,
                    "off_group_count": len(off_refs),
                    "on_group_count": len(on_refs),
                },
            )
        )
    return objects


def extract_fonts(reader: Any) -> List[PDFObject]:
    objects: List[PDFObject] = []
    if reader is None:
        return objects
    seen: Set[Tuple[int, int] | str] = set()
    pages = getattr(reader, "pages", [])
    for page_index, page in enumerate(pages):
        page = resolve_pdf_obj(page)
        resources = resolve_pdf_obj(_dict_get(page, "/Resources")) or {}
        fonts = resolve_pdf_obj(_dict_get(resources, "/Font")) or {}
        if not hasattr(fonts, "items"):
            continue
        for resource_name, font_ref in fonts.items():
            key = object_ref_key(font_ref) or f"{page_index}:{resource_name}"
            if key in seen:
                continue
            seen.add(key)
            font = resolve_pdf_obj(font_ref)
            base_font = pdf_value_to_text(_dict_get(font, "/BaseFont")) or str(resource_name)
            subtype = pdf_value_to_text(_dict_get(font, "/Subtype"))
            encoding = _dict_get(font, "/Encoding")
            encoding_text = pdf_value_to_text(encoding)
            has_tounicode = _dict_get(font, "/ToUnicode") is not None
            descriptor = resolve_pdf_obj(_dict_get(font, "/FontDescriptor")) or {}
            embedded = any(_dict_get(descriptor, key_name) is not None for key_name in ("/FontFile", "/FontFile2", "/FontFile3"))
            subset = "+" in base_font.split("/")[-1][:8]
            custom_encoding = _is_custom_encoding(encoding, encoding_text)
            suspicious = (not has_tounicode and (custom_encoding or subset or embedded)) or custom_encoding
            if not suspicious:
                continue
            objects.append(
                PDFObject(
                    object_id=f"font:{safe_name(resource_name)}:{safe_name(base_font)}",
                    object_type="font",
                    source="resources_font",
                    page_id=page_index + 1,
                    bbox=None,
                    text=base_font,
                    raw_value=None,
                    attrs={
                        "resource_name": str(resource_name),
                        "base_font": base_font,
                        "subtype": subtype,
                        "encoding": encoding_text,
                        "missing_tounicode": not has_tounicode,
                        "custom_encoding": custom_encoding,
                        "embedded_font": embedded,
                        "embedded_subset_font": subset,
                    },
                )
            )
    return objects


def extract_embedded_files(reader: Any) -> List[PDFObject]:
    objects: List[PDFObject] = []
    if reader is None:
        return objects
    root = _reader_root(reader)
    names = resolve_pdf_obj(_dict_get(root, "/Names")) or {}
    embedded = resolve_pdf_obj(_dict_get(names, "/EmbeddedFiles"))
    for idx, (name, filespec_ref) in enumerate(_walk_name_tree(embedded)):
        obj = _embedded_file_object(idx, name, filespec_ref, "names")
        if obj is not None:
            objects.append(obj)
    af = resolve_pdf_obj(_dict_get(root, "/AF")) or []
    for idx, filespec_ref in enumerate(_iter_array(af)):
        obj = _embedded_file_object(idx, f"AF-{idx}", filespec_ref, "associated_files")
        if obj is not None:
            objects.append(obj)
    return objects


def extract_signatures(pdf_path: str, reader: Any, config: ScanConfig) -> List[PDFObject]:
    marker_info = count_signature_markers(pdf_path, config.max_signature_scan_bytes)
    signature_fields = _signature_fields(reader)
    signature_present = bool(signature_fields or marker_info.get("byte_range_count"))
    incremental = bool(marker_info.get("incremental_update_present"))
    if not signature_present and not incremental:
        return []
    attrs = dict(marker_info)
    attrs["signature_field_count"] = len(signature_fields)
    attrs["signature_fields"] = signature_fields[:20]
    return [
        PDFObject(
            object_id="signature:document",
            object_type="signature",
            source="signature_scan",
            page_id=None,
            bbox=None,
            text=None,
            raw_value=None,
            attrs=attrs,
        )
    ]


def _extract_annotations_pypdf(reader: Any) -> List[PDFObject]:
    objects: List[PDFObject] = []
    pages = getattr(reader, "pages", [])
    for page_index, page in enumerate(pages):
        page = resolve_pdf_obj(page)
        annots = resolve_pdf_obj(_dict_get(page, "/Annots")) or []
        for annot_index, annot_ref in enumerate(_iter_array(annots)):
            annot = resolve_pdf_obj(annot_ref)
            subtype = pdf_value_to_text(_dict_get(annot, "/Subtype")) or ""
            flags = _int_or_zero(_dict_get(annot, "/F"))
            bbox = rect_to_bbox(_dict_get(annot, "/Rect"))
            for field_key in ("/Contents", "/RC", "/T", "/Subj"):
                text = pdf_value_to_text(_dict_get(annot, field_key))
                if not text:
                    continue
                objects.append(
                    PDFObject(
                        object_id=f"annotation:p{page_index + 1}:a{annot_index}:{safe_name(field_key)}",
                        object_type="annotation",
                        source="annots",
                        page_id=page_index + 1,
                        bbox=bbox,
                        text=text,
                        raw_value=text,
                        attrs={"subtype": subtype, "flags": flags, "field_key": field_key},
                    )
                )
            action = resolve_pdf_obj(_dict_get(annot, "/A")) or {}
            uri = pdf_value_to_text(_dict_get(action, "/URI"))
            if uri:
                objects.append(
                    PDFObject(
                        object_id=f"annotation:p{page_index + 1}:a{annot_index}:uri",
                        object_type="annotation",
                        source="annots",
                        page_id=page_index + 1,
                        bbox=bbox,
                        text=uri,
                        raw_value=uri,
                        attrs={"subtype": subtype, "flags": flags, "field_key": "/A/URI"},
                    )
                )
    return objects


def _extract_annotations_fitz(fitz_doc: Any) -> List[PDFObject]:
    objects: List[PDFObject] = []
    if fitz_doc is None:
        return objects
    for page_index in range(len(fitz_doc)):
        page = fitz_doc.load_page(page_index)
        annots = page.annots()
        if annots is None:
            continue
        for annot_index, annot in enumerate(annots):
            info = annot.info or {}
            subtype = annot.type[1] if getattr(annot, "type", None) else ""
            flags = int(getattr(annot, "flags", 0) or 0)
            bbox = _rect_bbox(getattr(annot, "rect", None))
            for field_key in ("content", "title", "subject"):
                text = info.get(field_key)
                if not text:
                    continue
                objects.append(
                    PDFObject(
                        object_id=f"annotation:p{page_index + 1}:a{annot_index}:{safe_name(field_key)}",
                        object_type="annotation",
                        source="annots",
                        page_id=page_index + 1,
                        bbox=bbox,
                        text=str(text),
                        raw_value=str(text),
                        attrs={"subtype": subtype, "flags": flags, "field_key": field_key},
                    )
                )
    return objects


def _extract_raw_xmp(reader: Any, max_bytes: int) -> Optional[str]:
    root = _reader_root(reader)
    metadata_ref = _dict_get(root, "/Metadata")
    metadata = resolve_pdf_obj(metadata_ref)
    if metadata is None:
        return None
    try:
        data = metadata.get_data()
    except Exception:
        return None
    if not data:
        return None
    if len(data) > max_bytes:
        data = data[:max_bytes]
    return data.decode("utf-8", errors="replace")


def _parse_xmp_fields(xmp_text: str) -> List[Tuple[str, str]]:
    try:
        root = ET.fromstring(xmp_text)
    except Exception:
        return []
    fields: List[Tuple[str, str]] = []
    for elem in root.iter():
        text = (elem.text or "").strip()
        if not text:
            continue
        tag = _local_tag(elem.tag)
        if len(text) > 50000:
            text = text[:50000]
        fields.append((tag, text))
    return fields


def _embedded_file_object(idx: int, name: Any, filespec_ref: Any, source: str) -> Optional[PDFObject]:
    filespec = resolve_pdf_obj(filespec_ref)
    filename = (
        pdf_value_to_text(_dict_get(filespec, "/UF"))
        or pdf_value_to_text(_dict_get(filespec, "/F"))
        or pdf_value_to_text(name)
        or f"embedded-{idx}"
    )
    desc = pdf_value_to_text(_dict_get(filespec, "/Desc"))
    ef = resolve_pdf_obj(_dict_get(filespec, "/EF")) or {}
    stream = resolve_pdf_obj(_dict_get(ef, "/UF") or _dict_get(ef, "/F"))
    params = resolve_pdf_obj(_dict_get(stream, "/Params")) if stream is not None else {}
    size = _dict_get(params, "/Size") if params else None
    checksum = pdf_value_to_text(_dict_get(params, "/CheckSum")) if params else None
    subtype = pdf_value_to_text(_dict_get(stream, "/Subtype")) if stream is not None else None
    text = filename if not desc else f"{filename} {desc}"
    ext = os.path.splitext(filename.lower())[1]
    return PDFObject(
        object_id=f"embedded_file:{source}:{idx}:{safe_name(filename)}",
        object_type="embedded_file",
        source=source,
        page_id=None,
        bbox=None,
        text=text,
        raw_value=None,
        attrs={
            "filename": filename,
            "description": desc,
            "size": _int_or_none(size),
            "checksum": checksum,
            "mime_subtype": subtype,
            "suspicious_extension": ext in {".html", ".htm", ".js", ".docm", ".docx", ".zip", ".exe", ".bat", ".ps1", ".vbs", ".rtf"},
        },
    )


def _signature_fields(reader: Any) -> List[str]:
    if reader is None:
        return []
    fields: Dict[str, Any] = {}
    try:
        fields = reader.get_fields() or {}
    except Exception:
        fields = {}
    names: List[str] = []
    for name, field in fields.items():
        field = resolve_pdf_obj(field)
        field_type = pdf_value_to_text(_dict_get(field, "/FT"))
        value = resolve_pdf_obj(_dict_get(field, "/V"))
        if field_type == "/Sig" or _dict_get(value, "/ByteRange") is not None:
            names.append(str(name))
    return names


def _walk_name_tree(root: Any) -> Iterator[Tuple[Any, Any]]:
    if not root:
        return
    queue: deque[Any] = deque([root])
    while queue:
        node = resolve_pdf_obj(queue.popleft())
        names = resolve_pdf_obj(_dict_get(node, "/Names"))
        if names:
            items = list(_iter_array(names))
            for idx in range(0, len(items) - 1, 2):
                yield items[idx], items[idx + 1]
        kids = resolve_pdf_obj(_dict_get(node, "/Kids"))
        if kids:
            queue.extend(_iter_array(kids))


def _reader_root(reader: Any) -> Any:
    try:
        return resolve_pdf_obj(reader.trailer["/Root"])
    except Exception:
        return {}


def _dict_get(mapping: Any, key: str) -> Any:
    mapping = resolve_pdf_obj(mapping)
    if mapping is None:
        return None
    try:
        return mapping.get(key)
    except Exception:
        try:
            return mapping[key]
        except Exception:
            return None


def _iter_array(value: Any) -> Iterable[Any]:
    value = resolve_pdf_obj(value)
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return []
    try:
        return list(value)
    except Exception:
        return []


def _tuple_bbox(value: Any) -> Optional[Tuple[float, float, float, float]]:
    if value is None:
        return None
    try:
        x0, y0, x1, y1 = value[:4]
        return (float(x0), float(y0), float(x1), float(y1))
    except Exception:
        return None


def _compact_text(text: str) -> str:
    return " ".join(str(text).split())


def _rect_bbox(rect: Any) -> Optional[Tuple[float, float, float, float]]:
    if rect is None:
        return None
    try:
        return (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
    except Exception:
        return _tuple_bbox(rect)


def _safe_texttrace(page: Any) -> List[Dict[str, Any]]:
    try:
        traces = page.get_texttrace()
    except Exception:
        return []
    return [item for item in traces if isinstance(item, dict)]


def _best_trace_match(
    bbox: Optional[Tuple[float, float, float, float]],
    span: Dict[str, Any],
    trace_items: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if bbox is None or not trace_items:
        return None
    font = span.get("font")
    size = _float_or_none(span.get("size"))
    best: Optional[Dict[str, Any]] = None
    best_score = 0.0
    for trace in trace_items:
        trace_bbox = _tuple_bbox(trace.get("bbox"))
        if trace_bbox is None:
            continue
        overlap = _overlap_ratio(bbox, trace_bbox)
        if overlap <= 0:
            continue
        score = overlap
        if font and trace.get("font") == font:
            score += 0.1
        trace_size = _float_or_none(trace.get("size"))
        if size is not None and trace_size is not None and abs(size - trace_size) <= max(0.2, size * 0.05):
            score += 0.1
        if score > best_score:
            best = trace
            best_score = score
    return best if best_score >= 0.05 else None


def _overlap_ratio(
    bbox: Tuple[float, float, float, float],
    other: Tuple[float, float, float, float],
) -> float:
    x0, y0, x1, y1 = bbox
    ox0, oy0, ox1, oy1 = other
    ix0 = max(x0, ox0)
    iy0 = max(y0, oy0)
    ix1 = min(x1, ox1)
    iy1 = min(y1, oy1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    area = _bbox_area(bbox)
    if area <= 0:
        return 0.0
    return inter / area


def _bbox_area(bbox: Tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = bbox
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _float_or_none(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _ref_set(value: Any) -> Set[Tuple[int, int]]:
    return {key for key in (object_ref_key(item) for item in _iter_array(value)) if key is not None}


def _is_custom_encoding(encoding: Any, encoding_text: Optional[str]) -> bool:
    encoding = resolve_pdf_obj(encoding)
    if encoding is None:
        return False
    if hasattr(encoding, "items"):
        return True
    known = {"/WinAnsiEncoding", "/MacRomanEncoding", "/MacExpertEncoding", "/Identity-H", "/Identity-V"}
    return bool(encoding_text and encoding_text not in known)


def _int_or_zero(value: Any) -> int:
    try:
        return int(resolve_pdf_obj(value) or 0)
    except Exception:
        return 0


def _int_or_none(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(resolve_pdf_obj(value))
    except Exception:
        return None
