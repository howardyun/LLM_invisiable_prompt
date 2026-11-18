from __future__ import annotations

import re
import unicodedata
from typing import List

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MULTISPACE_RE = re.compile(r"\s+")
HYPHEN_LINEBREAK_RE = re.compile(r"([A-Za-z])-\s*\n\s*([A-Za-z])")
TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)

LIGATURES = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "st",
    "\ufb06": "st",
}

INVISIBLE_CHARS = {
    "\u00ad": "",
    "\u200b": "",
    "\u200c": "",
    "\u200d": "",
    "\ufeff": "",
    "\u2060": "",
    "\xa0": " ",
}


def normalize_text(text: str) -> str:
    if not text:
        return ""
    for src, dst in INVISIBLE_CHARS.items():
        text = text.replace(src, dst)
    for src, dst in LIGATURES.items():
        text = text.replace(src, dst)
    text = HYPHEN_LINEBREAK_RE.sub(r"\1\2", text)
    text = unicodedata.normalize("NFKC", text)
    text = CONTROL_CHARS_RE.sub("", text)
    text = text.replace("\r", "\n")
    text = MULTISPACE_RE.sub(" ", text)
    return text.strip().lower()


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", normalize_text(text))


def text_tokens(text: str) -> List[str]:
    return TOKEN_RE.findall(normalize_text(text))


def split_text_lines(text: str) -> List[str]:
    return [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]


def split_long_line(line: str, max_chars: int = 320) -> List[str]:
    line = line.strip()
    if len(line) <= max_chars:
        return [line] if line else []
    parts = re.split(r"(?<=[.!?。！？])\s+", line)
    chunks: List[str] = []
    buf = ""
    for part in parts:
        if not part:
            continue
        if len(buf) + len(part) + 1 <= max_chars:
            buf = f"{buf} {part}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = part
    if buf:
        chunks.append(buf)
    return chunks or [line]
