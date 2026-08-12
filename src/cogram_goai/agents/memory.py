"""A2 — Keyword Memory: the only agent allowed to touch the note store."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from cogram_goai.notes import Note, NoteStore
from cogram_goai.skill import SKILL_NAME, keyword_recall

AGENT_NAME = "A2.keyword_memory"


class KeywordMemoryAgent:
    """Wraps ``cogram.keyword_recall`` and the write-back of accepted runs."""

    name = AGENT_NAME

    def __init__(self, store: NoteStore) -> None:
        self.store = store

    def recall(
        self,
        issue_text: str,
        max_notes: int = 3,
        min_score: float = 1.0,
        trace: Optional[Any] = None,
    ) -> Dict[str, Any]:
        result = keyword_recall(
            issue_text,
            notes=list(self.store),
            max_notes=max_notes,
            min_score=min_score,
        )
        if trace is not None:
            trace.record(
                self.name,
                "skill_call",
                skill=SKILL_NAME,
                hits=len(result["notes"]),
                note_ids=[note["id"] for note in result["notes"]],
                matched_tags=result["matched_tags"],
                fallback=result["fallback"],
            )
        return result

    def capture(
        self,
        text: str,
        tags: Iterable[str] = (),
        trace: Optional[Any] = None,
    ) -> Note:
        note = self.store.append(text, tags)
        if self.store.path:
            self.store.save()
        if trace is not None:
            trace.record(
                self.name,
                "experience_capture",
                note_id=note.id,
                tags=list(note.tags),
                persisted=bool(self.store.path),
            )
        return note

    def context_lines(self, result: Dict[str, Any]) -> List[str]:
        if not result["notes"]:
            return ["(no prior note matched; fallback=%s)" % result["fallback"]]
        return [
            "[%s | score %.1f] %s" % (note["id"], note["score"], note["text"])
            for note in result["notes"]
        ]
