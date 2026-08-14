"""Skills: recall, evidence bind, redact, approval gate, path guard.

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

import re

from cogram_goai.aliases import expand_tokens
from cogram_goai.notes import Note, NoteStore, NoteStoreError, _assert_safe_path
from cogram_goai.tokenize import token_set

SKILL_NAME = "cogram.keyword_recall"
BIND_SKILL_NAME = "cogram.evidence_bind"

#: A tag hit is worth more than a body-text hit because tags are curated.
TAG_WEIGHT = 2.0
TEXT_WEIGHT = 1.0

SKILL_CONTRACT: Dict[str, Any] = {
    "name": SKILL_NAME,
    "version": "0.3.0",
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
    "version": "0.3.0",
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

REDACT_SKILL_NAME = "cogram.redact"
GATE_SKILL_NAME = "cogram.approval_gate"
PATH_SKILL_NAME = "cogram.path_guard"

REDACT_CONTRACT: Dict[str, Any] = {
    "name": REDACT_SKILL_NAME,
    "version": "0.3.0",
    "purpose": "Strip secret-shaped tokens from text before it is written to the note store.",
    "input": {"text": "string"},
    "output": {"text": "redacted string", "redactions": "int, how many spans were replaced"},
    "invocation": "inside A2 capture, before append",
    "failure_mode": "returns the original text with redactions=0; never raises on a clean string",
    "security": ["pure function; does not touch storage"],
    "reuse": "any writer that accepts free-form text",
}

GATE_CONTRACT: Dict[str, Any] = {
    "name": GATE_SKILL_NAME,
    "version": "0.3.0",
    "purpose": "Turn (verified, human decision) into a single write-permission.",
    "input": {
        "verified": "bool, checklist complete",
        "decision": "true / false / null (no approver yet)",
    },
    "output": {
        "allowed": "true only when verified and decision is true",
        "state": "blocked_unverified | pending | approved | rejected",
    },
    "invocation": "after A3, before any capture",
    "failure_mode": "allowed=false; never invents a yes",
    "security": ["pure function; the only way a write is licensed"],
    "reuse": "pipeline, CI, or an MCP approval tool",
}

PATH_CONTRACT: Dict[str, Any] = {
    "name": PATH_SKILL_NAME,
    "version": "0.3.0",
    "purpose": "Refuse a note-store path that looks like a credential file.",
    "input": {"path": "string"},
    "output": {"allowed": "bool", "reason": "string when refused"},
    "invocation": "before NoteStore.load / save",
    "failure_mode": "allowed=false plus a reason; does not raise",
    "security": ["pure function over the path string"],
    "reuse": "any agent that is about to open a scratchpad file",
}

SKILL_CATALOG: List[Dict[str, Any]] = [
    SKILL_CONTRACT,
    BIND_CONTRACT,
    REDACT_CONTRACT,
    GATE_CONTRACT,
    PATH_CONTRACT,
]


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


#: Shapes a human would recognise as a secret in an issue comment. This is
#: not a complete secret scanner; it is the slice-sized version of "do not
#: write the key into the scratchpad".
_REDACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(api[_-]?key|token|password|secret|passwd)\s*[:=]\s*\S+"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgho_[A-Za-z0-9]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[A-Z0-9]{16}"),
)


def redact(text: str) -> Dict[str, Any]:
    """Replace secret-shaped spans with ``[REDACTED]``."""
    out = text
    hits = 0
    for pattern in _REDACT_PATTERNS:
        out, count = pattern.subn("[REDACTED]", out)
        hits += count
    return {
        "skill": REDACT_SKILL_NAME,
        "text": out,
        "redactions": hits,
    }


def approval_gate(verified: bool, decision: Optional[bool]) -> Dict[str, Any]:
    """License a write. A missing decision is pending, never a yes."""
    if not verified:
        state = "blocked_unverified"
        allowed = False
    elif decision is None:
        state = "pending"
        allowed = False
    elif decision:
        state = "approved"
        allowed = True
    else:
        state = "rejected"
        allowed = False
    return {
        "skill": GATE_SKILL_NAME,
        "allowed": allowed,
        "state": state,
        "verified": bool(verified),
        "decision": decision,
    }


def path_guard(path: str) -> Dict[str, Any]:
    """Same denylist as ``NoteStore``, as a reusable skill."""
    try:
        _assert_safe_path(path)
    except NoteStoreError as exc:
        return {
            "skill": PATH_SKILL_NAME,
            "allowed": False,
            "path": path,
            "reason": str(exc),
        }
    return {
        "skill": PATH_SKILL_NAME,
        "allowed": True,
        "path": path,
        "reason": "",
    }
