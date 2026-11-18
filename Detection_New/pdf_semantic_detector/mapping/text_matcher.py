from __future__ import annotations

from difflib import SequenceMatcher

from ..pdf_analysis.normalization import compact_text, normalize_text, text_tokens


def exact_or_substring_score(a: str, b: str) -> float:
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    a_compact = compact_text(a_norm)
    b_compact = compact_text(b_norm)
    if a_compact and b_compact and a_compact == b_compact:
        return 0.98
    if a_norm in b_norm or b_norm in a_norm:
        return min(len(a_norm), len(b_norm)) / max(len(a_norm), len(b_norm))
    if a_compact and b_compact and (a_compact in b_compact or b_compact in a_compact):
        return 0.92 * min(len(a_compact), len(b_compact)) / max(len(a_compact), len(b_compact))
    return 0.0


def token_jaccard(a: str, b: str) -> float:
    a_tokens = set(text_tokens(a))
    b_tokens = set(text_tokens(b))
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def char_ngram_similarity(a: str, b: str, n: int = 3) -> float:
    a_compact = compact_text(a)
    b_compact = compact_text(b)
    if not a_compact or not b_compact:
        return 0.0
    if len(a_compact) < n or len(b_compact) < n:
        return 1.0 if a_compact == b_compact else 0.0
    a_grams = {a_compact[i : i + n] for i in range(len(a_compact) - n + 1)}
    b_grams = {b_compact[i : i + n] for i in range(len(b_compact) - n + 1)}
    return len(a_grams & b_grams) / len(a_grams | b_grams)


def edit_similarity(a: str, b: str) -> float:
    a_compact = compact_text(a)
    b_compact = compact_text(b)
    if not a_compact or not b_compact:
        return 0.0
    return SequenceMatcher(None, a_compact, b_compact).ratio()


def text_match_score(a: str, b: str) -> float:
    return max(
        exact_or_substring_score(a, b),
        token_jaccard(a, b),
        char_ngram_similarity(a, b),
        edit_similarity(a, b),
    )


def block_text_match_score(span_text: str, block_text: str) -> float:
    span_norm = normalize_text(span_text)
    block_norm = normalize_text(block_text)
    if not span_norm or not block_norm:
        return 0.0
    span_compact = compact_text(span_norm)
    block_compact = compact_text(block_norm)
    if len(span_compact) >= 12 and span_compact in block_compact:
        return 0.97
    if len(block_compact) >= 12 and block_compact in span_compact:
        return 0.94
    return text_match_score(span_norm, block_norm)
