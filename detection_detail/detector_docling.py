"""Docling layout extraction and Docling/RapidOCR helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Iterable

import fitz

from detector_io import write_json
from detector_models import LayoutRegion


def accelerator_config(device: str, num_threads: int):
    """Create Docling accelerator options."""

    import torch
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested, but torch.cuda.is_available() is False.")
    selected = {
        "cuda": AcceleratorDevice.CUDA,
        "cpu": AcceleratorDevice.CPU,
        "auto": AcceleratorDevice.AUTO,
    }[device]
    return AcceleratorOptions(device=selected, num_threads=num_threads)


def parse_docling_layout(
    pdf_path: Path,
    output_dir: Path,
    max_pages: int | None,
    device: str,
    num_threads: int,
) -> list[LayoutRegion]:
    """Use Docling to obtain semantic layout regions and PDF bboxes."""

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_table_structure = False
    options.do_code_enrichment = False
    options.do_formula_enrichment = False
    options.accelerator_options = accelerator_config(device, num_threads)

    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    page_range = (1, max_pages) if max_pages else (1, sys.maxsize)
    conversion = converter.convert(pdf_path, page_range=page_range)
    document = conversion.document

    write_json(output_dir / "docling_raw.json", document.export_to_dict())
    (output_dir / "docling.md").write_text(document.export_to_markdown(), encoding="utf-8")

    with fitz.open(pdf_path) as pdf:
        page_heights = {index + 1: page.rect.height for index, page in enumerate(pdf)}
        page_widths = {index + 1: page.rect.width for index, page in enumerate(pdf)}

    regions: list[LayoutRegion] = []
    order = 0
    for item, level in document.iterate_items(with_groups=False):
        provenance = getattr(item, "prov", None) or []
        label_obj = getattr(item, "label", None)
        label = getattr(label_obj, "value", str(label_obj or "unknown"))
        item_text = str(getattr(item, "text", "") or "")
        content_obj = getattr(item, "content_layer", None)
        content_layer = getattr(content_obj, "value", str(content_obj)) if content_obj else None
        raw_ref = str(getattr(item, "self_ref", "") or "") or None

        for prov_index, prov in enumerate(provenance):
            page_no = int(prov.page_no)
            if max_pages and page_no > max_pages:
                continue
            page_height = page_heights.get(page_no)
            page_width = page_widths.get(page_no)
            if not page_height or not page_width:
                continue

            original_origin = getattr(prov.bbox.coord_origin, "value", str(prov.bbox.coord_origin))
            top_left = prov.bbox.to_top_left_origin(page_height)
            left = max(0.0, min(float(top_left.l), page_width))
            top = max(0.0, min(float(top_left.t), page_height))
            right = max(0.0, min(float(top_left.r), page_width))
            bottom = max(0.0, min(float(top_left.b), page_height))
            if right <= left or bottom <= top:
                continue

            order += 1
            charspan = list(prov.charspan) if getattr(prov, "charspan", None) else None
            regions.append(
                LayoutRegion(
                    region_id=f"r{order:05d}",
                    order=order,
                    source="docling_region",
                    label=label,
                    page_no=page_no,
                    bbox=[round(left, 3), round(top, 3), round(right, 3), round(bottom, 3)],
                    coord_origin="TOPLEFT",
                    docling_text=item_text,
                    charspan=charspan,
                    content_layer=content_layer,
                    raw_ref=raw_ref,
                    extra={
                        "docling_level": level,
                        "provenance_index": prov_index,
                        "original_coord_origin": original_origin,
                    },
                )
            )

    if not regions:
        raise RuntimeError("Docling returned no layout regions with page bbox information.")
    return regions


def extract_docling_ocr_records(document: Any) -> tuple[str, list[dict[str, Any]]]:
    """Return OCR text plus raw Docling OCR text items.

    We intentionally inspect export_to_dict()["texts"] because export_to_text()
    can omit OCR items nested under picture nodes.
    """

    direct_text = str(document.export_to_text() or "").strip()
    try:
        data = document.export_to_dict()
    except Exception:
        return direct_text, []

    records: list[dict[str, Any]] = []
    for item_index, item in enumerate(data.get("texts", []) or []):
        value = str(item.get("text") or item.get("orig") or "").strip()
        if not value:
            continue
        provenance = item.get("prov") or []
        if provenance:
            prov = provenance[0]
            bbox = prov.get("bbox") or {}
            origin = str(bbox.get("coord_origin") or "").upper()
            page_no = int(prov.get("page_no") or 1)
            left = float(bbox.get("l") or 0.0)
            top = float(bbox.get("t") or 0.0)
            bottom = float(bbox.get("b") or top)
        else:
            bbox = {}
            origin = ""
            page_no = 1
            left = top = bottom = 0.0

        y_mid = (top + bottom) / 2.0
        if "BOTTOMLEFT" in origin:
            y_mid = -y_mid
        sort_key = [page_no, int(round(y_mid / 20.0)), left, item_index]
        records.append(
            {
                "item_index": item_index,
                "self_ref": item.get("self_ref"),
                "parent_ref": (item.get("parent") or {}).get("$ref")
                if isinstance(item.get("parent"), dict)
                else None,
                "label": item.get("label"),
                "text": value,
                "bbox": bbox,
                "coord_origin": origin,
                "page_no_in_patch": page_no,
                "sort_key": sort_key,
            }
        )

    if not records:
        return direct_text, []
    records.sort(key=lambda item: item["sort_key"])
    return "\n".join(item["text"] for item in records).strip(), records


class DoclingRegionalOCR:
    """Run Docling RapidOCR with the Torch CUDA backend on region images."""

    def __init__(self, device: str, num_threads: int):
        import torch
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
        from docling.document_converter import DocumentConverter, ImageFormatOption

        options = PdfPipelineOptions()
        options.do_ocr = True
        options.do_table_structure = False
        options.do_code_enrichment = False
        options.do_formula_enrichment = False
        options.ocr_options = RapidOcrOptions(
            backend="torch",
            force_full_page_ocr=True,
            lang=["english", "chinese"],
        )
        options.accelerator_options = accelerator_config(device, num_threads)
        self.converter = DocumentConverter(
            format_options={InputFormat.IMAGE: ImageFormatOption(pipeline_options=options)}
        )
        self.device_summary = f"cuda:{torch.cuda.get_device_name(0)}" if device == "cuda" else device

    def recognize_one(self, patch_path: Path) -> tuple[str, str | None, list[dict[str, Any]]]:
        """OCR one patch. Returns text, error, raw OCR records."""

        try:
            result = self.converter.convert(patch_path, raises_on_error=False)
            document = getattr(result, "document", None)
            if document is None:
                return "", f"Docling conversion failed: {getattr(result, 'status', 'unknown')}", []
            ocr_text, ocr_records = extract_docling_ocr_records(document)
            return ocr_text, None, ocr_records
        except Exception as exc:
            return "", f"{type(exc).__name__}: {exc}", []

    def recognize_many(self, patch_paths: Iterable[Path]) -> Iterable[tuple[str, str | None, list[dict[str, Any]]]]:
        for patch_path in patch_paths:
            yield self.recognize_one(patch_path)
