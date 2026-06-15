from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .config import ScanConfig
from .schema import PDFObject, RGB
from .utils import normalize_rgb

ZERO_WIDTH_CHARS = {
    "\u200b",
    "\u200c",
    "\u200d",
    "\u2060",
    "\ufeff",
}
BIDI_CONTROL_CHARS = {
    "\u061c",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
}

ENGLISH_PHRASES = (
    "ignore previous",
    "ignore above",
    "ignore all prior",
    "ignore all previous",
    "system prompt",
    "developer message",
    "assistant message",
    "follow these instructions",
    "new instruction",
    "override",
    "do not reveal",
    "do not mention",
    "hidden instruction",
    "secret instruction",
    "only output",
    "output exactly",
    "return json",
    "summarize the document as",
    "answer with",
    "refuse to",
    "bypass",
    "jailbreak",
)

CHINESE_PHRASES = (
    "\u5ffd\u7565\u4ee5\u4e0a",
    "\u5ffd\u7565\u4e4b\u524d",
    "\u5ffd\u7565\u524d\u9762\u7684\u5185\u5bb9",
    "\u65e0\u89c6\u4e0a\u8ff0",
    "\u7cfb\u7edf\u63d0\u793a",
    "\u5f00\u53d1\u8005\u6d88\u606f",
    "\u52a9\u624b\u6d88\u606f",
    "\u8bf7\u6309\u7167\u4ee5\u4e0b\u6307\u4ee4",
    "\u65b0\u7684\u6307\u4ee4",
    "\u8986\u76d6\u4e4b\u524d\u7684\u89c4\u5219",
    "\u4e0d\u8981\u900f\u9732",
    "\u4e0d\u8981\u63d0\u53ca",
    "\u9690\u85cf\u6307\u4ee4",
    "\u53ea\u8f93\u51fa",
    "\u4e25\u683c\u8f93\u51fa",
    "\u8fd4\u56de json",
    "\u603b\u7ed3\u4e3a",
    "\u56de\u7b54\u65f6\u5fc5\u987b",
    "\u7ed5\u8fc7",
    "\u8d8a\u72f1",
)

ROLE_RE = re.compile(r"\b(system|developer|assistant|user)\b", re.IGNORECASE)
ACTION_RE = re.compile(r"\b(ignore|follow|output|return|refuse|override|bypass|reveal|summari[sz]e)\b", re.IGNORECASE)
HIDDEN_RE = re.compile(r"\b(hidden|secret|invisible|transparent|metadata|annotation)\b", re.IGNORECASE)
FORMAT_RE = re.compile(r"\b(json|yaml|xml|markdown|exactly|only)\b", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"([!?.。！？]){3,}")


@dataclass(slots=True)
class NormalizedText:
    text: str
    zero_width_char_present: bool = False
    bidi_control_char_present: bool = False
    unicode_confusable_candidate: bool = False


def normalize_text(text: Optional[str]) -> NormalizedText:
    raw = "" if text is None else str(text)
    zero = any(ch in ZERO_WIDTH_CHARS for ch in raw)
    bidi = any(ch in BIDI_CONTROL_CHARS for ch in raw)
    without_controls = "".join(ch for ch in raw if ch not in ZERO_WIDTH_CHARS and ch not in BIDI_CONTROL_CHARS)
    normalized = unicodedata.normalize("NFKC", without_controls).lower()
    normalized = PUNCT_RE.sub(r"\1", normalized)
    normalized = SPACE_RE.sub(" ", normalized).strip()
    confusable = any(_is_private_or_control_char(ch) for ch in raw)
    return NormalizedText(
        text=normalized,
        zero_width_char_present=zero,
        bidi_control_char_present=bidi,
        unicode_confusable_candidate=confusable,
    )


def analyze_control_intent(text: Optional[str], config: ScanConfig) -> Tuple[float, Dict[str, Any]]:
    norm = normalize_text(text)
    if not norm.text and not norm.zero_width_char_present and not norm.bidi_control_char_present:
        return 0.0, _norm_evidence(norm)

    phrases: List[str] = []
    phrase_source: List[str] = []
    if config.enable_english_patterns:
        phrase_source.extend(ENGLISH_PHRASES)
    if config.enable_chinese_patterns:
        phrase_source.extend(CHINESE_PHRASES)
    for phrase in phrase_source:
        nphrase = normalize_text(phrase).text
        if nphrase and nphrase in norm.text:
            phrases.append(phrase)

    roles = sorted(set(match.group(1).lower() for match in ROLE_RE.finditer(norm.text)))
    actions = sorted(set(match.group(1).lower() for match in ACTION_RE.finditer(norm.text)))
    hidden = sorted(set(match.group(1).lower() for match in HIDDEN_RE.finditer(norm.text)))
    formats = sorted(set(match.group(1).lower() for match in FORMAT_RE.finditer(norm.text)))

    score = 0.0
    if phrases:
        score += 0.6
    if roles:
        score += 0.2
    if actions:
        score += 0.2
    if hidden:
        score += 0.2
    if formats:
        score += 0.1
    if config.zero_width_as_signal and norm.zero_width_char_present:
        score += 0.1
    if config.bidi_as_signal and norm.bidi_control_char_present:
        score += 0.1

    evidence = _norm_evidence(norm)
    evidence.update(
        {
            "matched_phrases": phrases,
            "matched_roles": roles,
            "matched_actions": actions,
            "matched_hidden_terms": hidden,
            "matched_format_terms": formats,
            "normalized_preview": norm.text[:240],
        }
    )
    return min(score, 1.0), evidence


def analyze_visibility(obj: PDFObject, config: ScanConfig) -> Tuple[str, List[str], Dict[str, Any]]:
    reasons: List[str] = []
    flags: Dict[str, Any] = {}
    if obj.object_type in {"text_span", "parser_text"}:
        bbox = obj.bbox
        page_width = _float_or_none(obj.attrs.get("page_width"))
        page_height = _float_or_none(obj.attrs.get("page_height"))
        font_size = _float_or_none(obj.attrs.get("font_size"))
        alpha = _normalize_alpha(obj.attrs.get("alpha"))
        opacity = _normalize_alpha(obj.attrs.get("opacity"))
        alpha_values = [value for value in (alpha, opacity) if value is not None]
        effective_alpha = min(alpha_values) if alpha_values else None
        color = normalize_rgb(obj.attrs.get("color_rgb"))
        bbox_area = bbox_area_value(bbox)
        render_mode = _int_or_none(obj.attrs.get("texttrace_type"))

        flags["_detail_alpha"] = effective_alpha
        flags["_detail_alpha_raw"] = obj.attrs.get("alpha_raw", obj.attrs.get("alpha"))
        flags["_detail_opacity"] = opacity
        flags["_detail_bbox_area"] = bbox_area
        flags["_detail_font_size"] = font_size
        flags["_detail_color_rgb"] = color
        flags["_detail_texttrace_type"] = render_mode
        flags["_detail_layer"] = obj.attrs.get("layer")

        state = "visible"
        visibility_score = 1.0
        if bbox is None:
            reasons.append("missing_bbox")
            visibility_score = min(visibility_score, 0.5)
            state = _weaker_state(state, "unknown")
        else:
            if bbox_area <= 0:
                reasons.append("zero_area_bbox")
                flags["zero_area_bbox"] = True
                visibility_score = min(visibility_score, 0.02)
                state = "invisible"
            elif bbox_area < config.min_visible_bbox_area:
                reasons.append("tiny_bbox_area")
                flags["tiny_text"] = True
                visibility_score = min(visibility_score, 0.12)
                state = _weaker_state(state, "weak_visible")

            if page_width is not None and page_height is not None:
                overlap_ratio = page_overlap_ratio(bbox, page_width, page_height)
                flags["_detail_page_overlap_ratio"] = overlap_ratio
                if bbox_outside_page(bbox, page_width, page_height, config.page_margin):
                    reasons.append("page_outside")
                    flags["page_outside"] = True
                    visibility_score = min(visibility_score, 0.01)
                    state = "invisible"
                elif overlap_ratio < config.partial_page_overlap_threshold:
                    reasons.append("mostly_off_page")
                    flags["page_partially_outside"] = True
                    visibility_score = min(visibility_score, 0.25)
                    state = _weaker_state(state, "weak_visible")
                elif overlap_ratio < 1.0:
                    reasons.append("partially_off_page")
                    flags["page_partially_outside"] = True
                    visibility_score = min(visibility_score, 0.55)
                    state = _weaker_state(state, "weak_visible")

        if render_mode == 3:
            reasons.append("render_mode_invisible")
            flags["render_mode_invisible"] = True
            visibility_score = min(visibility_score, 0.01)
            state = "invisible"

        if font_size is not None:
            if font_size <= config.invisible_font_threshold:
                reasons.append("tiny_font_invisible")
                flags["tiny_text"] = True
                visibility_score = min(visibility_score, 0.05)
                state = "invisible"
            elif font_size <= config.tiny_font_threshold:
                reasons.append("tiny_font_weak")
                flags["tiny_text"] = True
                visibility_score = min(visibility_score, 0.35)
                state = _weaker_state(state, "weak_visible")

        if effective_alpha is not None:
            if effective_alpha <= config.alpha_invisible_threshold:
                reasons.append("transparent_text")
                flags["low_alpha"] = True
                visibility_score = min(visibility_score, 0.02)
                state = "invisible"
            elif effective_alpha <= config.alpha_weak_threshold:
                reasons.append("low_alpha")
                flags["low_alpha"] = True
                visibility_score = min(visibility_score, 0.35)
                state = _weaker_state(state, "weak_visible")

        if color is not None and is_near_white(color, config.white_rgb_threshold):
            reasons.append("near_white_text")
            flags["low_contrast"] = True
            visibility_score = min(visibility_score, 0.45)
            state = _weaker_state(state, "weak_visible")

        layer = str(obj.attrs.get("layer") or "").strip().lower()
        if layer in {"hidden", "off", "disabled"}:
            reasons.append("hidden_layer")
            flags["ocg_off"] = True
            visibility_score = min(visibility_score, 0.05)
            state = "invisible"

        norm = normalize_text(obj.text)
        if norm.zero_width_char_present or norm.bidi_control_char_present:
            flags["zero_width_or_bidi"] = True
            if norm.zero_width_char_present:
                reasons.append("zero_width_char")
            if norm.bidi_control_char_present:
                reasons.append("bidi_control_char")
        flags["_detail_visibility_score"] = round(max(0.0, min(1.0, visibility_score)), 6)
        return state, reasons, flags

    if obj.object_type == "annotation":
        ann_flags = int(obj.attrs.get("flags", 0) or 0)
        if ann_flags & 1:
            reasons.append("annotation_invisible_flag")
        if ann_flags & 2:
            reasons.append("annotation_hidden_flag")
        if ann_flags & 32:
            reasons.append("annotation_noview_flag")
        if reasons:
            flags["hidden_annotation"] = True
            return "invisible", reasons, flags
        return "visible" if obj.bbox is not None else "non_visual", reasons, flags

    if obj.object_type in {"metadata", "form", "embedded_file", "signature", "font"}:
        return "non_visual", reasons, flags

    if obj.object_type in {"ocg", "ocg_text"}:
        if str(obj.attrs.get("ocg_default_state", "")).lower() == "off":
            reasons.append("ocg_default_off")
            flags["ocg_off"] = True
            return "invisible", reasons, flags
        return "unknown", reasons, flags

    return "unknown", reasons, flags


def analyze_object_anomalies(obj: PDFObject, visibility_flags: Dict[str, Any]) -> Dict[str, Any]:
    flags = dict(visibility_flags)
    if obj.object_type == "font":
        if obj.attrs.get("missing_tounicode") and (
            obj.attrs.get("custom_encoding") or obj.attrs.get("embedded_subset_font")
        ):
            flags["font_mapping_anomaly"] = True
    if obj.object_type == "signature":
        if obj.attrs.get("post_signature_bytes_present"):
            flags["post_signature_update"] = True
        if obj.attrs.get("incremental_update_present"):
            flags["incremental_update"] = True
    return flags


def classify_risk_type(
    obj: PDFObject,
    consumed: str,
    visibility: str,
    control_score: float,
    anomaly_flags: Dict[str, bool],
) -> str:
    if obj.object_type == "metadata" and control_score > 0:
        return "METADATA_INJECTION"
    if obj.object_type == "annotation":
        if anomaly_flags.get("hidden_annotation") and control_score > 0:
            return "HIDDEN_ANNOTATION_INJECTION"
        if control_score > 0:
            return "ANNOTATION_INJECTION"
    if obj.object_type == "form" and control_score > 0:
        return "FORM_FIELD_INJECTION"
    if obj.object_type in {"ocg", "ocg_text"} and anomaly_flags.get("ocg_off"):
        return "OCG_HIDDEN_TEXT"
    if obj.object_type == "embedded_file":
        return "EMBEDDED_FILE_PRESENT"
    if obj.object_type == "signature" and (
        anomaly_flags.get("post_signature_update") or anomaly_flags.get("incremental_update")
    ):
        return "SIGNED_INCREMENTAL_UPDATE"
    if anomaly_flags.get("font_mapping_anomaly"):
        return "FONT_MAPPING_MIRAGE_CANDIDATE"
    if anomaly_flags.get("zero_width_or_bidi"):
        return "BIDI_OR_ZERO_WIDTH_TEXT"
    if obj.object_type in {"text_span", "parser_text"}:
        if control_score > 0:
            if visibility == "invisible":
                return "CONTROL_TEXT_INVISIBLE"
            if visibility == "weak_visible":
                return "CONTROL_TEXT_WEAK_VISIBLE"
            return "CONTROL_TEXT_VISIBLE"
        if anomaly_flags.get("page_outside"):
            return "PAGE_OUTSIDE_TEXT"
        if anomaly_flags.get("tiny_text"):
            return "TINY_TEXT"
        if anomaly_flags.get("render_mode_invisible"):
            return "RENDER_MODE_INVISIBLE_TEXT"
        if anomaly_flags.get("low_alpha"):
            return "TRANSPARENT_TEXT"
        if anomaly_flags.get("low_contrast"):
            return "LOW_CONTRAST_TEXT"
    if consumed == "uncertain":
        return "LOADER_UNCERTAIN_CONSUMPTION"
    return "LOW_SUSPICION_OBJECT"


def compute_risk_score(
    consumed: str,
    visibility: str,
    control_score: float,
    anomaly_flags: Dict[str, bool],
) -> float:
    score = 0.0
    if consumed == "yes":
        score += 0.25
    elif consumed == "uncertain":
        score += 0.15

    if visibility in {"invisible", "non_visual"}:
        score += 0.25
    elif visibility == "weak_visible":
        score += 0.15
    elif visibility == "unknown":
        score += 0.10

    score += 0.35 * control_score

    if anomaly_flags.get("font_mapping_anomaly"):
        score += 0.10
    if anomaly_flags.get("ocg_off"):
        score += 0.15
    if anomaly_flags.get("hidden_annotation"):
        score += 0.15
    if anomaly_flags.get("zero_width_or_bidi"):
        score += 0.10
    if anomaly_flags.get("page_outside"):
        score += 0.15
    if anomaly_flags.get("render_mode_invisible"):
        score += 0.15
    if anomaly_flags.get("low_alpha"):
        score += 0.10
    if anomaly_flags.get("low_contrast"):
        score += 0.05
    if anomaly_flags.get("post_signature_update"):
        score += 0.10
    return round(min(score, 1.0), 6)


def severity_from_score(score: float, config: ScanConfig) -> str:
    if score >= config.critical_threshold:
        return "critical"
    if score >= config.high_threshold:
        return "high"
    if score >= config.medium_threshold:
        return "medium"
    return "low"


def should_emit_finding(score: float, risk_type: str, config: ScanConfig) -> bool:
    if config.emit_all:
        return True
    if risk_type == "LOW_SUSPICION_OBJECT":
        return False
    return bool(score >= config.min_score or risk_type in config.always_emit_types)


def bbox_outside_page(bbox: Tuple[float, float, float, float], width: float, height: float, margin: float) -> bool:
    x0, y0, x1, y1 = bbox
    return x1 < -margin or y1 < -margin or x0 > width + margin or y0 > height + margin


def page_overlap_ratio(bbox: Tuple[float, float, float, float], width: float, height: float) -> float:
    x0, y0, x1, y1 = bbox
    area = bbox_area_value(bbox)
    if area <= 0:
        return 0.0
    ix0 = max(0.0, x0)
    iy0 = max(0.0, y0)
    ix1 = min(width, x1)
    iy1 = min(height, y1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    return max(0.0, min(1.0, inter / area))


def bbox_area_value(bbox: Optional[Tuple[float, float, float, float]]) -> float:
    if bbox is None:
        return 0.0
    x0, y0, x1, y1 = bbox
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def is_near_white(rgb: RGB, threshold: int = 245) -> bool:
    return rgb[0] >= threshold and rgb[1] >= threshold and rgb[2] >= threshold


def _weaker_state(current: str, candidate: str) -> str:
    rank = {"visible": 0, "weak_visible": 1, "unknown": 2, "invisible": 3, "non_visual": 4}
    return candidate if rank.get(candidate, 0) > rank.get(current, 0) else current


def _float_or_none(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _int_or_none(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _normalize_alpha(value: Any) -> Optional[float]:
    raw = _float_or_none(value)
    if raw is None:
        return None
    if raw > 1.0:
        raw = raw / 255.0
    return max(0.0, min(1.0, raw))


def _norm_evidence(norm: NormalizedText) -> Dict[str, Any]:
    return {
        "zero_width_char_present": norm.zero_width_char_present,
        "bidi_control_char_present": norm.bidi_control_char_present,
        "unicode_confusable_candidate": norm.unicode_confusable_candidate,
    }


def _is_private_or_control_char(ch: str) -> bool:
    cat = unicodedata.category(ch)
    if cat in {"Co", "Cs"}:
        return True
    if cat == "Cc" and ch not in {"\t", "\n", "\r"}:
        return True
    return False
