from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pdf_semantic_detector.config import DetectionConfig
from pdf_semantic_detector.models import RegionDescriptor
from pdf_semantic_detector.pdf_analysis.visibility import estimate_visibility


class VisibilityTests(unittest.TestCase):
    def test_low_contrast(self) -> None:
        region = RegionDescriptor(
            region_id="p1_r00001",
            page=1,
            region_type="text",
            bbox=(10, 10, 100, 20),
            text="hidden",
            color=(255, 255, 255),
            background_color=(255, 255, 255),
            font_size=12,
        )
        estimate_visibility(region, (0, 0, 200, 200), DetectionConfig())
        self.assertIn("low_color_contrast", region.visibility_reasons)
        self.assertLess(region.visibility_score, 0.2)

    def test_off_page(self) -> None:
        region = RegionDescriptor(
            region_id="p1_r00001",
            page=1,
            region_type="text",
            bbox=(500, 500, 600, 520),
            text="hidden",
            color=(0, 0, 0),
            background_color=(255, 255, 255),
            font_size=12,
        )
        estimate_visibility(region, (0, 0, 200, 200), DetectionConfig())
        self.assertIn("off_page", region.visibility_reasons)
        self.assertEqual(region.visibility_status, "invisible")

    def test_small_font(self) -> None:
        region = RegionDescriptor(
            region_id="p1_r00001",
            page=1,
            region_type="text",
            bbox=(10, 10, 100, 20),
            text="hidden",
            color=(0, 0, 0),
            background_color=(255, 255, 255),
            font_size=1,
        )
        estimate_visibility(region, (0, 0, 200, 200), DetectionConfig())
        self.assertIn("small_font_size", region.visibility_reasons)
        self.assertEqual(region.visibility_status, "low_visible")


if __name__ == "__main__":
    unittest.main()
