"""Skills: ``cogram.keyword_recall`` and ``cogram.evidence_bind``.

``keyword_recall`` returns previously captured notes whose keywords overlap
the issue text. Scoring is token overlap plus an audited synonym table
(see ``aliases.py``). No embeddings, no model call.

Each hit carries an evidence band copied from the production Cogram
contract's *shape* (high / medium / low / unknown) but computed only from
what this slice can actually see:

- high   — a curated tag overlapped
- medium — a body token overlapped (including audited synonyms)
- low    — never emitted here; reserved so the contract stays stable
- unknown — no hit; ``fallback: manual_search``

The slice does not claim a recalled note is a correct fix.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from cogram_goai.aliases import expand_tokens
from cogram_goai.notes import Note, NoteStore
from cogram_goai.tokenize import token_set

SKILL_NAME = "cogram.keyword_recall"
BIND_SKILL_NAME = "cogram.evidence_bind"

#: A tag hit is worth more than a body-text hit because tags are curated.
TAG_WEIGHT = 2.0
TEXT_WEIGHT = 1.0

SKILL_CONTRACT: Dict[str, Any] = {
    "name": SKILL_NAME,
    "version": "0.2.0",
    "purpose": "Recall up to N previously captured notes whose keywords overlap the issue text.",
    "input": {
        "issue_text": "string, free-form issue or task description",
        "max_notes": "int >= 1, default 3",
        "min_score": "float >= 0, default 1.0",
    },
    "output": {
        "notes": "list of {id, text, tags, score, band, reason, matched, matched_tags, cause, fix}",
        "matched_tags": "list of tags that contributed to at least one returned note",
        "query_tokens": "list of tokens extracted from issue_text",
        "expanded_tokens": "query tokens plus audited synonyms",
        "fallback": "null, or 'manual_search' when nothing matched",
    },
    "invocation": "after triage, before any patch is written",
    "dependent_tools": ["local file read/write (or an equivalent MCP file tool)"],
    "failure_mode": "empty note list plus fallback='manual_search'; never raises on no-match",
    "security": [
        "read-only over the note store",
        "note store paths containing .env / secret / token / credential are rejected",
        "rolled-back notes are skipped",
    ],
    "reuse": "any agent may call it as a shared scratchpad lookup",
}

BIND_CONTRACT: Dict[str, Any] = {
    "name": BIND_SKILL_NAME,
    "version": "0.2.0",
    "purpose": "Bind a map of subtask-id → evidence onto a triage checklist. Missing evidence fails the item.",
    "input": {
        "subtasks": "list of {id, title}",
        "evidence": "object mapping subtask id to a non-empty evidence string",
    },
    "output": {
        "items": "list of {subtask_id, requirement, passed, evidence}",
        "verified": "true only when every item passed",
    },
    "invocation": "after subtasks exist and evidence has been collected",
    "failure_mode": "verified=false; never invents evidence",
    "security": ["pure function; does not touch storage"],
    "reuse": "any verifier or CI job may call it",
}

SKILL_CATALOG: List[Dict[str, Any]] = [SKILL_CONTRACT, BIND_CONTRACT]


def _band_and_reason(text_hits: List[str], tag_hits: List[str]) -> tuple[str, str]:
    if tag_hits:
        return "high", "direct_structured_cue"
    if text_hits:
        return "medium", "keyword_overlap"
    return "unknown", "no_overlap"


def _score_note(note: Note, query: Iterable[str]) -> Dict[str, Any]:
    query_tokens = set(query)
    note_tokens = token_set(note.text)
    tag_tokens = set(note.tags)

    text_hits = sorted(query_tokens & note_tokens)
    tag_hits = sorted({tag for tag in tag_tokens if tag in query_tokens})
    score = TEXT_WEIGHT * len(text_hits) + TAG_WEIGHT * len(tag_hits)
    band, reason = _band_and_reason(text_hits, tag_hits)
    return {
        "score": score,
        "text_hits": text_hits,
        "tag_hits": tag_hits,
        "band": band,
        "reason": reason,
    }


def keyword_recall(
    issue_text: str,
    notes: Optional[Iterable[Note]] = None,
    max_notes: int = 3,
    min_score: float = 1.0,
    store: Optional[NoteStore] = None,
) -> Dict[str, Any]:
    """Run the recall skill. ``store`` is a convenience alias for ``notes``."""
    if max_notes < 1:
        raise ValueError("max_notes must be >= 1")
    if notes is None:
        notes = list(store or [])

    query_tokens = token_set(issue_text)
    expanded = expand_tokens(query_tokens)
    scored: List[Dict[str, Any]] = []

    for note in notes:
        if getattr(note, "status", "active") != "active":
            continue
        result = _score_note(note, expanded)
        if result["score"] < min_score:
            continue
        scored.append(
            {
                "id": note.id,
                "text": note.text,
                "tags": list(note.tags),
                "score": result["score"],
                "band": result["band"],
                "reason": result["reason"],
                "matched": result["text_hits"],
                "matched_tags": result["tag_hits"],
                "cause": note.cause,
                "fix": note.fix,
            }
        )

    scored.sort(key=lambda item: (-item["score"], item["id"]))
    hits = scored[:max_notes]

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
        "expanded_tokens": sorted(expanded),
        "fallback": None if hits else "manual_search",
    }


def evidence_bind(
    subtasks: Sequence[Dict[str, Any]],
    evidence: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Reusable skill: refuse any subtask that has no evidence string."""
    evidence = evidence or {}
    items: List[Dict[str, Any]] = []
    for task in subtasks:
        task_id = str(task.get("id", ""))
        supplied = str(evidence.get(task_id, "")).strip()
        items.append(
            {
                "subtask_id": task_id,
                "requirement": str(task.get("title") or task.get("requirement") or ""),
                "passed": bool(supplied),
                "evidence": supplied or "(missing)",
            }
        )
    verified = bool(items) and all(item["passed"] for item in items)
    return {
        "skill": BIND_SKILL_NAME,
        "items": items,
        "verified": verified,
    }
