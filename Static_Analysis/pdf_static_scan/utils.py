from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from .schema import RGB, to_jsonable

try:
    import orjson  # type: ignore
except Exception:  # pragma: no cover - optional speed path
    orjson = None


def sha256_file(path: str | os.PathLike[str], chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dumps_json(value: Any, *, pretty: bool = False) -> str:
    payload = to_jsonable(value)
    if orjson is not None:
        option = orjson.OPT_SORT_KEYS
        if pretty:
            option |= orjson.OPT_INDENT_2
        return orjson.dumps(payload, option=option).decode("utf-8")
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2 if pretty else None)


def write_json(path: str | os.PathLike[str], value: Any, *, pretty: bool = True) -> None:
    Path(path).write_text(dumps_json(value, pretty=pretty), encoding="utf-8")


def text_preview(text: Optional[str], max_len: int) -> Optional[str]:
    if text is None:
        return None
    compact = " ".join(str(text).split())
    if len(compact) <= max_len:
        return compact
    return compact[: max(0, max_len - 3)] + "..."


def normalize_rgb(value: Any) -> Optional[RGB]:
    if value is None:
        return None
    if isinstance(value, int):
        return ((value >> 16) & 255, (value >> 8) & 255, value & 255)
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        values = value[:3]
        if all(isinstance(v, (int, float)) for v in values):
            if all(0.0 <= float(v) <= 1.0 for v in values):
                return tuple(int(round(float(v) * 255)) for v in values)  # type: ignore[return-value]
            return tuple(int(max(0, min(255, round(float(v))))) for v in values)  # type: ignore[return-value]
    return None


def iter_pdf_files(input_dir: str | os.PathLike[str], *, recursive: bool = True) -> Iterator[str]:
    root = Path(input_dir)
    if recursive:
        for path in root.rglob("*.pdf"):
            if path.is_file():
                yield str(path)
        return
    for path in root.glob("*.pdf"):
        if path.is_file():
            yield str(path)


def safe_name(value: Any) -> str:
    text = str(value).strip()
    text = text.replace("\x00", "")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_.:/-]+", "_", text)
    return text[:120] or "unknown"


def object_ref_key(value: Any) -> Optional[Tuple[int, int]]:
    idnum = getattr(value, "idnum", None)
    generation = getattr(value, "generation", None)
    if idnum is None:
        return None
    return (int(idnum), int(generation or 0))


def resolve_pdf_obj(value: Any) -> Any:
    try:
        if hasattr(value, "get_object"):
            return value.get_object()
    except Exception:
        return value
    return value


def pdf_value_to_text(value: Any) -> Optional[str]:
    value = resolve_pdf_obj(value)
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (str, int, float, bool)):
        text = str(value)
        return text if text.strip() else None
    try:
        text = str(value)
    except Exception:
        return None
    return text if text.strip() else None


def rect_to_bbox(value: Any) -> Optional[Tuple[float, float, float, float]]:
    value = resolve_pdf_obj(value)
    if value is None:
        return None
    try:
        items = list(value)
    except Exception:
        return None
    if len(items) < 4:
        return None
    try:
        return (float(items[0]), float(items[1]), float(items[2]), float(items[3]))
    except Exception:
        return None


def count_signature_markers(path: str | os.PathLike[str], max_bytes: int) -> Dict[str, Any]:
    file_size = os.path.getsize(path)
    startxref_count = 0
    byte_range_count = 0
    tail = b""
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            combined = tail + chunk
            startxref_count += combined.count(b"startxref")
            byte_range_count += combined.count(b"/ByteRange")
            tail = combined[-32:]

    result: Dict[str, Any] = {
        "startxref_count": startxref_count,
        "byte_range_count": byte_range_count,
        "incremental_update_present": startxref_count > 1,
        "post_signature_bytes_present": None,
    }
    if file_size > max_bytes:
        result["signature_scan_limited"] = True
        return result

    data = Path(path).read_bytes()
    byte_range_re = re.compile(rb"/ByteRange\s*\[\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\]")
    post_signature = False
    ranges: List[List[int]] = []
    for match in byte_range_re.finditer(data):
        nums = [int(x) for x in match.groups()]
        ranges.append(nums)
        signed_end = nums[2] + nums[3]
        if signed_end < file_size:
            post_signature = True
    result["byte_ranges"] = ranges[:10]
    result["post_signature_bytes_present"] = post_signature if ranges else None
    return result


def flatten_errors(errors: Iterable[Any]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for err in errors:
        stage = getattr(err, "stage", "unknown")
        message = getattr(err, "message", str(err))
        rows.append({"stage": str(stage), "message": str(message)})
    return rows
