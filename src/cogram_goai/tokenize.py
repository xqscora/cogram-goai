"""Deterministic tokenizer shared by the memory skill and the agents.

Kept intentionally simple: lowercase, split on non-alphanumerics, drop stopwords
and very short tokens. CJK text is split per character bigram so that Chinese
issue text still produces overlapping keys without a segmentation dependency.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Set

STOPWORDS: Set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "cannot",
    "did", "do", "does", "for", "from", "get", "gets", "had", "has", "have",
    "how", "i", "if", "in", "into", "is", "it", "its", "not", "of", "on", "or",
    "should", "so", "than", "that", "the", "then", "there", "they", "this",
    "to", "was", "we", "were", "what", "when", "where", "which", "why", "will",
    "with", "would", "you", "your",
}

_WORD_RE = re.compile(r"[a-z0-9_]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_MIN_WORD_LEN = 2


def _cjk_bigrams(text: str) -> List[str]:
    grams: List[str] = []
    for run in _CJK_RE.findall(text):
        if len(run) == 1:
            grams.append(run)
            continue
        grams.extend(run[i : i + 2] for i in range(len(run) - 1))
    return grams


def tokenize(text: str) -> List[str]:
    """Return the ordered, de-duplicated keyword tokens found in ``text``."""
    if not text:
        return []
    lowered = text.lower()
    tokens = [
        word
        for word in _WORD_RE.findall(lowered)
        if len(word) >= _MIN_WORD_LEN and word not in STOPWORDS
    ]
    tokens.extend(_cjk_bigrams(lowered))

    seen: Set[str] = set()
    ordered: List[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            ordered.append(token)
    return ordered


def token_set(text: str) -> Set[str]:
    return set(tokenize(text))


def normalize_tags(tags: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    seen: Set[str] = set()
    for tag in tags:
        cleaned = str(tag).strip().lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            normalized.append(cleaned)
    return normalized
