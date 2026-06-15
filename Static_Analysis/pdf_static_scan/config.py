from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable, Tuple


DEFAULT_ALWAYS_EMIT_TYPES = (
    "METADATA_INJECTION",
    "HIDDEN_ANNOTATION_INJECTION",
    "FORM_FIELD_INJECTION",
    "OCG_HIDDEN_TEXT",
    "EMBEDDED_FILE_PRESENT",
)


@dataclass(slots=True)
class ScanConfig:
    min_score: float = 0.40
    emit_all: bool = False
    fail_fast: bool = False
    max_text_preview_len: int = 200
    max_metadata_bytes: int = 2 * 1024 * 1024
    max_signature_scan_bytes: int = 256 * 1024 * 1024
    include_objects: bool = False
    jobs: int = 1
    always_emit_types: Tuple[str, ...] = field(default_factory=lambda: DEFAULT_ALWAYS_EMIT_TYPES)

    tiny_font_threshold: float = 2.0
    invisible_font_threshold: float = 0.5
    white_rgb_threshold: int = 245
    alpha_invisible_threshold: float = 0.05
    alpha_weak_threshold: float = 0.25
    page_margin: float = 2.0
    min_visible_bbox_area: float = 1.0
    partial_page_overlap_threshold: float = 0.5
    enable_texttrace_visibility: bool = True

    critical_threshold: float = 0.85
    high_threshold: float = 0.65
    medium_threshold: float = 0.40

    enable_english_patterns: bool = True
    enable_chinese_patterns: bool = True
    zero_width_as_signal: bool = True
    bidi_as_signal: bool = True

    extract_fonts: bool = True
    extract_embedded_files: bool = True
    extract_signatures: bool = True
    extract_pypdf_text: bool = False

    def with_overrides(
        self,
        *,
        min_score: float | None = None,
        emit_all: bool | None = None,
        fail_fast: bool | None = None,
        include_objects: bool | None = None,
        jobs: int | None = None,
        extract_pypdf_text: bool | None = None,
        enable_texttrace_visibility: bool | None = None,
        always_emit_types: Iterable[str] | None = None,
    ) -> "ScanConfig":
        updates = {}
        if min_score is not None:
            updates["min_score"] = min_score
        if emit_all is not None:
            updates["emit_all"] = emit_all
        if fail_fast is not None:
            updates["fail_fast"] = fail_fast
        if include_objects is not None:
            updates["include_objects"] = include_objects
        if jobs is not None:
            updates["jobs"] = max(1, jobs)
        if extract_pypdf_text is not None:
            updates["extract_pypdf_text"] = extract_pypdf_text
        if enable_texttrace_visibility is not None:
            updates["enable_texttrace_visibility"] = enable_texttrace_visibility
        if always_emit_types is not None:
            updates["always_emit_types"] = tuple(always_emit_types)
        return replace(self, **updates)
