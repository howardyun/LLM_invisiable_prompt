from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class DetectionConfig:
    """Runtime thresholds for the RRSD MVP detector."""

    min_font_size: float = 5.0
    tiny_font_size: float = 3.0
    low_contrast_threshold: float = 30.0
    low_alpha_threshold: float = 0.05
    match_threshold: float = 0.75
    weak_match_threshold: float = 0.35
    ambiguous_margin: float = 0.04
    risk_threshold: float = 0.40
    report_parser_only_without_instruction: bool = False
    tiny_text_min_chars_without_instruction: int = 12
    tiny_text_min_words_without_instruction: int = 2
    default_background_color: Tuple[int, int, int] = (255, 255, 255)
    enable_occlusion: bool = False
    occlusion_overlap_threshold: float = 0.80
    enable_font_encoding_analysis: bool = True
    encoding_min_chars: int = 40
    encoding_min_words: int = 5
    encoding_untrusted_ratio: float = 0.70
    encoding_tiny_font_ratio: float = 0.50
    encoding_min_unique_fonts: int = 4
    encoding_font_switch_density: float = 0.12
    encoding_max_avg_chars_per_show: float = 4.0
    enable_block_mapping: bool = True
    block_line_y_tolerance_factor: float = 0.70
    block_max_line_gap_factor: float = 1.85
    block_x_alignment_tolerance: float = 18.0
    block_min_table_rows: int = 2
    block_table_min_multicol_ratio: float = 0.45
    block_formula_math_ratio: float = 0.18
    block_formula_symbol_font_ratio: float = 0.35
    block_formula_max_prose_words: int = 8
    block_glyph_drift_max_similarity: float = 0.70
    block_special_weak_match_threshold: float = 0.50
    enable_parser_aggregation: bool = True
    parser_aggregation_max_spans: int = 10
    parser_aggregation_match_threshold: float = 0.70
    parser_aggregation_min_coverage: float = 0.42
    include_debug: bool = False
