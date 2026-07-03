"""Page rendering, region cropping, and debug visualizations."""

from __future__ import annotations

import re
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

from detector_models import LayoutRegion


def render_pages(
    pdf_path: Path,
    pages_dir: Path,
    dpi: int,
    max_pages: int | None,
) -> dict[int, Path]:
    """Render PDF pages to RGB PNGs with PyMuPDF."""

    pages_dir.mkdir(parents=True, exist_ok=True)
    rendered: dict[int, Path] = {}
    matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    with fitz.open(pdf_path) as pdf:
        count = min(len(pdf), max_pages) if max_pages else len(pdf)
        for page_index in range(count):
            path = pages_dir / f"page_{page_index + 1:04d}.png"
            pdf[page_index].get_pixmap(matrix=matrix, alpha=False).save(path)
            rendered[page_index + 1] = path
    return rendered


def crop_pdf_bbox_to_image(
    page_image_path: Path,
    bbox: list[float],
    output_path: Path,
    dpi: int,
    padding_points: float,
) -> dict:
    """Crop one PDF-point bbox from a rendered page image."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72.0
    with Image.open(page_image_path) as image:
        left = max(0, int((bbox[0] - padding_points) * scale))
        top = max(0, int((bbox[1] - padding_points) * scale))
        right = min(image.width, int((bbox[2] + padding_points) * scale + 0.999))
        bottom = min(image.height, int((bbox[3] + padding_points) * scale + 0.999))
        if right <= left or bottom <= top:
            raise ValueError(f"Empty crop bbox: {bbox}")
        image.crop((left, top, right, bottom)).save(output_path)
        return {
            "patch_pixel_bbox": [left, top, right, bottom],
            "patch_pdf_bbox": [
                round(left / scale, 3),
                round(top / scale, 3),
                round(right / scale, 3),
                round(bottom / scale, 3),
            ],
            "patch_size_px": [right - left, bottom - top],
            "render_dpi": dpi,
        }


def crop_region_patches(
    regions: list[LayoutRegion],
    page_images: dict[int, Path],
    patches_dir: Path,
    dpi: int,
    padding_points: float,
) -> None:
    """Crop every candidate region into a patch for OCR."""

    patches_dir.mkdir(parents=True, exist_ok=True)
    for region in regions:
        page_path = page_images.get(region.page_no)
        if not page_path:
            continue
        safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "_", region.label)
        path = patches_dir / f"{region.region_id}_p{region.page_no}_{safe_label}.png"
        try:
            meta = crop_pdf_bbox_to_image(page_path, region.bbox, path, dpi, padding_points)
        except ValueError:
            continue
        region.patch_path = path.as_posix()
        region.extra.update(meta)


def draw_visualizations(
    regions: list[LayoutRegion],
    page_images: dict[int, Path],
    output_dir: Path,
    dpi: int,
) -> None:
    """Draw all candidate bboxes on rendered pages."""

    output_dir.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72.0
    grouped: dict[int, list[LayoutRegion]] = {}
    for region in regions:
        grouped.setdefault(region.page_no, []).append(region)
    font = ImageFont.load_default()

    for page_no, page_path in page_images.items():
        with Image.open(page_path).convert("RGB") as image:
            draw = ImageDraw.Draw(image)
            for region in grouped.get(page_no, []):
                x0, y0, x1, y1 = region.bbox
                box = (x0 * scale, y0 * scale, x1 * scale, y1 * scale)
                color = (255, 0, 0) if region.source == "docling_region" else (0, 120, 255)
                draw.rectangle(box, outline=color, width=2)
                draw.text(
                    (box[0] + 2, max(0, box[1] - 12)),
                    f"{region.region_id}:{region.source}:{region.label}",
                    fill=color,
                    font=font,
                )
            image.save(output_dir / f"page_{page_no:04d}_bbox.png")



def measure_visible_ink(image_path: Path) -> dict:
    """Estimate whether a crop visibly contains dark foreground ink.

    This is deliberately simple and conservative.  It is used only as a fallback
    when OCR fails to match PyMuPDF text: if the tight verification crop clearly
    contains visible dark pixels and the text has no control intent, we treat the
    miss as an OCR failure rather than hidden text.
    """

    with Image.open(image_path) as image:
        gray = image.convert("L")
        pixels = list(gray.getdata())
        width, height = gray.size

    total = max(1, len(pixels))
    dark_pixels = sum(1 for value in pixels if value < 180)
    very_dark_pixels = sum(1 for value in pixels if value < 110)
    non_white_pixels = sum(1 for value in pixels if value < 245)
    dark_ratio = dark_pixels / total
    very_dark_ratio = very_dark_pixels / total
    non_white_ratio = non_white_pixels / total

    # Text crops in these PDFs are usually black-on-white.  Requiring both a
    # minimum count and ratio avoids suppressing truly blank hidden-text crops
    # because of tiny compression specks.
    visible = (
        (dark_pixels >= 25 and dark_ratio >= 0.003)
        or (very_dark_pixels >= 12 and very_dark_ratio >= 0.0015)
        or (non_white_pixels >= 60 and non_white_ratio >= 0.012 and very_dark_pixels >= 4)
    )
    return {
        "visible_ink": bool(visible),
        "image_size_px": [width, height],
        "dark_pixel_count": dark_pixels,
        "very_dark_pixel_count": very_dark_pixels,
        "non_white_pixel_count": non_white_pixels,
        "dark_pixel_ratio": round(dark_ratio, 6),
        "very_dark_pixel_ratio": round(very_dark_ratio, 6),
        "non_white_pixel_ratio": round(non_white_ratio, 6),
    }
