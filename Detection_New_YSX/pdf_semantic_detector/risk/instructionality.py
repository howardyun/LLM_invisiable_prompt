from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Pattern

from ..pdf_analysis.normalization import normalize_text


INSTRUCTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above) instructions",
    r"disregard (all )?(previous|prior|above)",
    r"forget (all )?(previous|prior|above)",
    r"you are now",
    r"system prompt",
    r"developer message",
    r"only output",
    r"output only",
    r"answer with",
    r"do not (say|mention|include|reveal)",
    r"must answer",
    r"follow these instructions",
    r"hidden instruction",
    r"jailbreak",
    r"bypass",
    r"reveal .*prompt",
    r"rank this section first",
    r"prioritize this text",
    r"忽略.*(之前|以上|前面|先前).*指令",
    r"不要(说|提及|包含|透露)",
    r"(只|仅)输出",
    r"系统提示",
    r"开发者消息",
    r"越狱",
    r"绕过",
]

COMPILED_PATTERNS: List[Pattern[str]] = [re.compile(p, re.IGNORECASE) for p in INSTRUCTION_PATTERNS]


@dataclass(slots=True)
class InstructionalityResult:
    score: float
    matches: List[str]


def compute_instructionality(text: str) -> InstructionalityResult:
    normalized = normalize_text(text)
    matches: List[str] = []
    for pattern in COMPILED_PATTERNS:
        if pattern.search(normalized):
            matches.append(pattern.pattern)
    if not matches:
        return InstructionalityResult(score=0.0, matches=[])
    score = min(1.0, 0.35 + 0.25 * len(matches))
    return InstructionalityResult(score=score, matches=matches)
