"""Audited synonym groups for keyword recall.

This is the public-slice answer to "keyword overlap misses paraphrases".
It is a table a human can read in one screen, not an embedding space.
Adding a pair is a documented edit; the skill never invents a synonym at
runtime.

Taken from the same discipline as the production Cogram contract: the
caller (or a maintainer) already knows these terms are the same thing.
The table does not learn, decay, or re-rank.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Set

# Each inner list is one meaning. Tokens are matched after the shared
# tokenizer (lowercase English words, CJK bigrams).
SYNONYM_GROUPS: List[List[str]] = [
    ["timeout", "timedout", "超时"],
    ["retry", "retries", "rewind", "重试"],
    ["upload", "uploader", "uploads", "上传"],
    ["stream", "streams"],
    ["crash", "exception", "traceback", "报错", "崩溃"],
    ["slow", "latency", "performance", "卡顿", "性能"],
    ["test", "tests", "pytest", "regression", "测试", "回归"],
    ["docs", "readme", "documentation", "文档"],
]


def alias_index(groups: Iterable[Iterable[str]] = SYNONYM_GROUPS) -> Dict[str, Set[str]]:
    index: Dict[str, Set[str]] = {}
    for group in groups:
        members = {token for token in group if token}
        for token in members:
            index.setdefault(token, set()).update(members)
    return index


ALIAS_INDEX = alias_index()


def expand_tokens(tokens: Iterable[str], index: Dict[str, Set[str]] = ALIAS_INDEX) -> Set[str]:
    """Return the original tokens plus every audited synonym."""
    expanded: Set[str] = set()
    for token in tokens:
        expanded.add(token)
        expanded.update(index.get(token, ()))
    return expanded
