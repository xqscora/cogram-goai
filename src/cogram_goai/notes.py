"""Plain-JSON note store used as the shared scratchpad between agents."""

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


class NoteStoreError(RuntimeError):
    pass


@dataclass
class Note:
    id: str
    text: str
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Note":
        if not isinstance(raw, dict):
            raise NoteStoreError("each note must be a JSON object")
        text = str(raw.get("text", "")).strip()
        if not text:
            raise NoteStoreError("note %r has no text" % raw.get("id"))
        return cls(
            id=str(raw.get("id") or "note-%s" % abs(hash(text)) % 10**6),
            text=text,
            tags=normalize_tags(raw.get("tags") or []),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "text": self.text, "tags": list(self.tags)}


def _assert_safe_path(path: str) -> None:
    lowered = os.path.basename(path).lower()
    for part in FORBIDDEN_PATH_PARTS:
        if part in lowered:
            raise NoteStoreError("refusing to use %r as a note store" % path)


class NoteStore:
    """Loads, queries and appends notes stored as a JSON list."""

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

    def append(self, text: str, tags: Iterable[str] = (), note_id: Optional[str] = None) -> Note:
        text = text.strip()
        if not text:
            raise NoteStoreError("cannot append an empty note")
        note = Note(
            id=note_id or "note-%s-%03d" % (time.strftime("%Y%m%d"), len(self.notes) + 1),
            text=text,
            tags=normalize_tags(tags),
        )
        self.notes.append(note)
        return note

    def __len__(self) -> int:
        return len(self.notes)

    def __iter__(self):
        return iter(self.notes)
