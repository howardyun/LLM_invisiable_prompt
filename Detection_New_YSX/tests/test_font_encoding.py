from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pdf_semantic_detector.config import DetectionConfig
from pdf_semantic_detector.pdf_analysis import extract_pdf_regions
from pdf_semantic_detector.pdf_analysis.font_encoding import detect_font_encoding_issues


class FontEncodingTests(unittest.TestCase):
    def test_pdf_migrate_sample_flags_encoding_drift(self) -> None:
        sample = Path(__file__).resolve().parents[2] / "Detection" / "testData" / "org" / "pdf_migrate.pdf"
        if not sample.exists():
            self.skipTest("pdf_migrate.pdf sample is not available")
        regions = extract_pdf_regions(str(sample), DetectionConfig())
        issues = detect_font_encoding_issues(str(sample), DetectionConfig(), regions)
        self.assertTrue(issues)
        self.assertIn("untrusted_font_text_mapping", issues[0].reasons)
        self.assertIn("tiny_embedded_subset_fonts", issues[0].reasons)
        self.assertIn("Content masking attack", issues[0].evidence["text_preview"])
        self.assertIn("This___", issues[0].evidence["parser_text_preview"])

    def test_pdf_migrate_rendered_text_estimate(self) -> None:
        sample = Path(__file__).resolve().parents[2] / "Detection" / "testData" / "org" / "pdf_migrate.pdf"
        if not sample.exists():
            self.skipTest("pdf_migrate.pdf sample is not available")
        regions = extract_pdf_regions(str(sample), DetectionConfig())
        rendered_lines = [r for r in regions if r.text_semantic_source == "glyph_shape_line"]
        self.assertTrue(rendered_lines)
        line_text = " ".join(r.rendered_text_estimate or "" for r in rendered_lines)
        self.assertIn("Content masking attack", line_text)
        self.assertIn("real message", line_text)


if __name__ == "__main__":
    unittest.main()
