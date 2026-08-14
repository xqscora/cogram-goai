"""Plain-JSON note store used as the shared scratchpad between agents.

Notes are append-only. A rollback does not delete the row — it marks
``status: rolled_back`` so the audit trail still contains the rejected
capture. Recall skips rolled-back notes.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from cogram_goai.tokenize import normalize_tags

#: Substrings that must never appear in a note store path. The store is a
#: read-mostly scratchpad; pointing it at credentials would turn the recall
#: skill into an exfiltration tool.
FORBIDDEN_PATH_PARTS = (".env", "secret", "credential", "password", "token", "id_rsa", ".pem")

STATUS_ACTIVE = "active"
STATUS_ROLLED_BACK = "rolled_back"


class NoteStoreError(RuntimeError):
    pass


@dataclass
class Note:
    id: str
    text: str
    tags: List[str] = field(default_factory=list)
    cause: str = ""
    fix: str = ""
    status: str = STATUS_ACTIVE
    run_id: str = ""
    issue_hash: str = ""
    cited: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Note":
        if not isinstance(raw, dict):
            raise NoteStoreError("each note must be a JSON object")
        text = str(raw.get("text", "")).strip()
        if not text:
            raise NoteStoreError("note %r has no text" % raw.get("id"))
        status = str(raw.get("status") or STATUS_ACTIVE)
        if status not in {STATUS_ACTIVE, STATUS_ROLLED_BACK}:
            status = STATUS_ACTIVE
        return cls(
            id=str(raw.get("id") or "note-%s" % abs(hash(text)) % 10**6),
            text=text,
            tags=normalize_tags(raw.get("tags") or []),
            cause=str(raw.get("cause") or "").strip(),
            fix=str(raw.get("fix") or "").strip(),
            status=status,
            run_id=str(raw.get("run_id") or "").strip(),
            issue_hash=str(raw.get("issue_hash") or "").strip(),
            cited=[str(item).strip() for item in (raw.get("cited") or []) if str(item).strip()],
        )

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "text": self.text,
            "tags": list(self.tags),
            "status": self.status,
        }
        if self.cause:
            payload["cause"] = self.cause
        if self.fix:
            payload["fix"] = self.fix
        if self.run_id:
            payload["run_id"] = self.run_id
        if self.issue_hash:
            payload["issue_hash"] = self.issue_hash
        if self.cited:
            payload["cited"] = list(self.cited)
        return payload


def _assert_safe_path(path: str) -> None:
    lowered = os.path.basename(path).lower()
    for part in FORBIDDEN_PATH_PARTS:
        if part in lowered:
            raise NoteStoreError("refusing to use %r as a note store" % path)


class NoteStore:
    """Loads, queries, appends and rolls back notes stored as a JSON list."""

    def __init__(self, notes: Optional[Iterable[Note]] = None, path: Optional[str] = None) -> None:
        self.path = path
        self.notes: List[Note] = list(notes or [])

    @classmethod
    def load(cls, path: str) -> "NoteStore":
        _assert_safe_path(path)
        if not os.path.exists(path):
            return cls(path=path)
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if isinstance(raw, dict):
            raw = raw.get("notes", [])
        if not isinstance(raw, list):
            raise NoteStoreError("%s must contain a JSON list of notes" % path)
        return cls(notes=[Note.from_dict(item) for item in raw], path=path)

    def save(self, path: Optional[str] = None) -> str:
        target = path or self.path
        if not target:
            raise NoteStoreError("no path to save to")
        _assert_safe_path(target)
        parent = os.path.dirname(os.path.abspath(target))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump([note.to_dict() for note in self.notes], handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        self.path = target
        return target

    def append(
        self,
        text: str,
        tags: Iterable[str] = (),
        note_id: Optional[str] = None,
        cause: str = "",
        fix: str = "",
        run_id: str = "",
        issue_hash: str = "",
        cited: Iterable[str] = (),
    ) -> Note:
        text = text.strip()
        if not text:
            raise NoteStoreError("cannot append an empty note")
        note = Note(
            id=note_id or "note-%s-%03d" % (time.strftime("%Y%m%d"), len(self.notes) + 1),
            text=text,
            tags=normalize_tags(tags),
            cause=cause.strip(),
            fix=fix.strip(),
            run_id=run_id.strip(),
            issue_hash=issue_hash.strip(),
            cited=[str(item).strip() for item in cited if str(item).strip()],
        )
        self.notes.append(note)
        return note

    def find_duplicate(self, issue_hash: str, cause: str = "", fix: str = "") -> Optional[Note]:
        """Same issue + same cited cause/fix → reuse the active row."""
        digest = (issue_hash or "").strip()
        if not digest:
            return None
        cause = (cause or "").strip()
        fix = (fix or "").strip()
        for note in self.active():
            if note.issue_hash == digest and note.cause == cause and note.fix == fix:
                return note
        return None

    def rollback(self, note_id: str) -> Note:
        """Mark a note rolled back. The row stays so the audit trail is intact."""
        for note in self.notes:
            if note.id == note_id:
                if note.status == STATUS_ROLLED_BACK:
                    raise NoteStoreError("note %s is already rolled back" % note_id)
                note.status = STATUS_ROLLED_BACK
                return note
        raise NoteStoreError("note %s not found" % note_id)

    def active(self) -> List[Note]:
        return [note for note in self.notes if note.status == STATUS_ACTIVE]

    def __len__(self) -> int:
        return len(self.notes)

    def __iter__(self):
        return iter(self.notes)
