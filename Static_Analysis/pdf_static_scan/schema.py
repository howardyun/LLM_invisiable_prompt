from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BBox = Tuple[float, float, float, float]
RGB = Tuple[int, int, int]


@dataclass(slots=True)
class PDFObject:
    object_id: str
    object_type: str
    source: str
    page_id: Optional[int]
    bbox: Optional[BBox]
    text: Optional[str] = None
    raw_value: Optional[Any] = None
    attrs: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Finding:
    finding_id: str
    file_sha256: str
    object_id: str
    object_type: str
    source: str
    page_id: Optional[int]
    bbox: Optional[BBox]
    loader: str
    loader_consumed: str
    visibility_state: str
    risk_type: str
    severity: str
    risk_score: float
    control_intent_score: float
    text_preview: Optional[str]
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScanError:
    stage: str
    message: str


@dataclass(slots=True)
class ExtractedPDF:
    file_info: Dict[str, Any]
    objects: List[PDFObject]
    object_stats: Dict[str, int]
    errors: List[ScanError] = field(default_factory=list)


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {k: to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
