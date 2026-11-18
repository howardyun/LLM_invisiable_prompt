from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pdf_semantic_detector.config import DetectionConfig
from pdf_semantic_detector.mapping.mapper import map_one_span
from pdf_semantic_detector.models import ParserSpan, RegionDescriptor
from pdf_semantic_detector.pdf_analysis.block_builder import build_structure_blocks
from pdf_semantic_detector.pdf_analysis.normalization import normalize_text


def region(region_id: str, text: str, bbox: tuple[float, float, float, float], font: str = "Times") -> RegionDescriptor:
    return RegionDescriptor(
        region_id=region_id,
        page=1,
        region_type="text",
        bbox=bbox,
        text=text,
        normalized_text=normalize_text(text),
        parser_text=text,
        rendered_text_estimate=text,
        font_name=font,
        font_size=10.0,
    )


class BlockAggregationTests(unittest.TestCase):
    def test_inline_math_stays_paragraph(self) -> None:
        regions = [
            region("r1", "We use the variable", (10, 10, 120, 20)),
            region("r2", "x = 1", (126, 10, 158, 20), "CMMI10"),
            region("r3", "inside the paragraph to estimate model uncertainty.", (164, 10, 430, 20)),
        ]
        blocks = build_structure_blocks(regions, DetectionConfig())
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].block_role, "paragraph")
        self.assertGreater(blocks[0].features["inline_math_ratio"], 0)

    def test_display_math_becomes_formula(self) -> None:
        regions = [
            region("r1", "x = alpha + beta / gamma", (180, 40, 340, 52), "CMMI10"),
        ]
        blocks = build_structure_blocks(regions, DetectionConfig())
        self.assertEqual(blocks[0].block_role, "formula")

    def test_multicolumn_rows_become_table(self) -> None:
        regions = [
            region("r1", "Metric", (10, 10, 55, 20)),
            region("r2", "Ours", (140, 10, 175, 20)),
            region("r3", "Base", (240, 10, 275, 20)),
            region("r4", "PSNR", (10, 24, 45, 34)),
            region("r5", "31.2", (140, 24, 172, 34)),
            region("r6", "29.8", (240, 24, 272, 34)),
            region("r7", "SSIM", (10, 38, 45, 48)),
            region("r8", "0.91", (140, 38, 172, 48)),
            region("r9", "0.86", (240, 38, 272, 48)),
        ]
        blocks = build_structure_blocks(regions, DetectionConfig())
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].block_role, "table")

    def test_parser_span_maps_to_containing_block(self) -> None:
        regions = [
            region("r1", "The first visual line is visible.", (10, 10, 220, 20)),
            region("r2", "The second visual line is also visible.", (10, 24, 250, 34)),
        ]
        blocks = build_structure_blocks(regions, DetectionConfig())
        span = ParserSpan(
            span_id="s1",
            parser_name="pypdf",
            page=1,
            text="The second visual line is also visible.",
            normalized_text=normalize_text("The second visual line is also visible."),
            order=1,
        )
        mapping = map_one_span(span, regions, DetectionConfig(), blocks)
        self.assertEqual(mapping.mapping_scope, "block")
        self.assertEqual(mapping.support_status, "render_supported")
        self.assertEqual(mapping.matched_block_id, blocks[0].block_id)


if __name__ == "__main__":
    unittest.main()
