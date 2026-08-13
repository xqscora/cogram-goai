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
            notes=self.store.active(),
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
                bands=[note.get("band") for note in result["notes"]],
                fallback=result["fallback"],
            )
        return result

    def capture(
        self,
        text: str,
        tags: Iterable[str] = (),
        trace: Optional[Any] = None,
        cause: str = "",
        fix: str = "",
    ) -> Note:
        note = self.store.append(text, tags, cause=cause, fix=fix)
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

    def rollback(self, note_id: str, trace: Optional[Any] = None) -> Note:
        note = self.store.rollback(note_id)
        if self.store.path:
            self.store.save()
        if trace is not None:
            trace.record(self.name, "rollback", note_id=note.id)
        return note

    def context_packet(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Bounded, cited context for the next agent. Never a bare dump."""
        notes = result.get("notes") or []
        return {
            "citations": [
                {
                    "id": note["id"],
                    "band": note.get("band", "unknown"),
                    "reason": note.get("reason", ""),
                    "text": note["text"],
                    "cause": note.get("cause") or "",
                    "fix": note.get("fix") or "",
                }
                for note in notes
            ],
            "fallback": result.get("fallback"),
            "auto_inject": [note["id"] for note in notes if note.get("band") == "high"],
        }

    def context_lines(self, result: Dict[str, Any]) -> List[str]:
        if not result["notes"]:
            return ["(no prior note matched; fallback=%s)" % result["fallback"]]
        return [
            "[%s | %s | score %.1f] %s" % (
                note["id"],
                note.get("band", "?"),
                note["score"],
                note["text"],
            )
            for note in result["notes"]
        ]
