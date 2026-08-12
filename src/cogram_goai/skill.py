"""The one mandatory skill: ``cogram.keyword_recall``.

Given free-form issue text, return the notes whose keywords overlap with it.
No embeddings, no model call, no ranking heuristics beyond token overlap — the
score is reproducible by hand, which is the point of an educational slice.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from cogram_goai.notes import Note, NoteStore
from cogram_goai.tokenize import token_set

SKILL_NAME = "cogram.keyword_recall"

#: A tag hit is worth more than a body-text hit because tags are curated.
TAG_WEIGHT = 2.0
TEXT_WEIGHT = 1.0

SKILL_CONTRACT: Dict[str, Any] = {
    "name": SKILL_NAME,
    "version": "0.1.0",
    "purpose": "Recall up to N previously captured notes whose keywords overlap the issue text.",
    "input": {
        "issue_text": "string, free-form issue or task description",
        "max_notes": "int >= 1, default 3",
        "min_score": "float >= 0, default 1.0",
    },
    "output": {
        "notes": "list of {id, text, tags, score, matched, matched_tags}",
        "matched_tags": "list of tags that contributed to at least one returned note",
        "query_tokens": "list of tokens extracted from issue_text",
        "fallback": "null, or 'manual_search' when nothing matched",
    },
    "invocation": "after triage, before any patch is written",
    "dependent_tools": ["local file read/write (or an equivalent MCP file tool)"],
    "failure_mode": "empty note list plus fallback='manual_search'; never raises on no-match",
    "security": [
        "read-only over the note store",
        "note store paths containing .env / secret / token / credential are rejected",
    ],
    "reuse": "any agent may call it as a shared scratchpad lookup",
}


def _score_note(note: Note, query: Iterable[str]) -> Dict[str, Any]:
    query_tokens = set(query)
    note_tokens = token_set(note.text)
    tag_tokens = {tag for tag in note.tags}

    text_hits = sorted(query_tokens & note_tokens)
    tag_hits = sorted({tag for tag in tag_tokens if tag in query_tokens})
    score = TEXT_WEIGHT * len(text_hits) + TAG_WEIGHT * len(tag_hits)
    return {"score": score, "text_hits": text_hits, "tag_hits": tag_hits}


def keyword_recall(
    issue_text: str,
    notes: Optional[Iterable[Note]] = None,
    max_notes: int = 3,
    min_score: float = 1.0,
    store: Optional[NoteStore] = None,
) -> Dict[str, Any]:
    """Run the skill. ``store`` is a convenience alias for ``notes``."""
    if max_notes < 1:
        raise ValueError("max_notes must be >= 1")
    if notes is None:
        notes = list(store or [])

    query_tokens = token_set(issue_text)
    scored: List[Dict[str, Any]] = []

    for note in notes:
        result = _score_note(note, query_tokens)
        if result["score"] < min_score:
            continue
        scored.append(
            {
                "id": note.id,
                "text": note.text,
                "tags": list(note.tags),
                "score": result["score"],
                "matched": result["text_hits"],
                "matched_tags": result["tag_hits"],
            }
        )

    scored.sort(key=lambda item: (-item["score"], item["id"]))
    hits = scored[:max_notes]

    # Only tags from notes we actually return count as matched, otherwise the
    # caller sees context it was never given.
    matched_tags: List[str] = []
    for hit in hits:
        for tag in hit["matched_tags"]:
            if tag not in matched_tags:
                matched_tags.append(tag)

    return {
        "skill": SKILL_NAME,
        "notes": hits,
        "matched_tags": matched_tags,
        "query_tokens": sorted(query_tokens),
        "fallback": None if hits else "manual_search",
    }
