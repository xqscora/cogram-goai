"""Append-only, hash-chained JSONL trace of everything the pipeline did."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

GENESIS_HASH = "0" * 64


class TraceError(RuntimeError):
    pass


def _canonical(entry: Dict[str, Any]) -> str:
    """Stable JSON for hashing. ``hash`` is excluded; everything else is in."""
    body = {key: value for key, value in entry.items() if key != "hash"}
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def event_hash(entry: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(entry).encode("utf-8")).hexdigest()


def _last_hash_on_disk(path: str) -> str:
    """Continue a chain when a new Trace appends to an existing JSONL file."""
    if not os.path.exists(path):
        return GENESIS_HASH
    last: Optional[Dict[str, Any]] = None
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            last = json.loads(line)
    if not last:
        return GENESIS_HASH
    return str(last.get("hash") or event_hash(last))


class Trace:
    """Records one line of JSON per pipeline event.

    Each event carries ``prev_hash`` and ``hash`` so a later reader can tell
    whether a line was inserted, dropped, or edited. Events are kept in
    memory as well as written to disk so tests and the CLI can assert on
    them without re-reading the file.
    """

    def __init__(self, path: Optional[str] = None, run_id: Optional[str] = None) -> None:
        self.path = path
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.events: List[Dict[str, Any]] = []
        self._resume_hash = GENESIS_HASH
        if self.path:
            parent = os.path.dirname(os.path.abspath(self.path))
            if parent:
                os.makedirs(parent, exist_ok=True)
            self._resume_hash = _last_hash_on_disk(self.path)

    def _prev_hash(self) -> str:
        if not self.events:
            return self._resume_hash
        return str(self.events[-1].get("hash") or event_hash(self.events[-1]))

    def record(self, agent: str, event: str, **payload: Any) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "run_id": self.run_id,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z",
            "agent": agent,
            "event": event,
            "prev_hash": self._prev_hash(),
        }
        if payload:
            entry["payload"] = payload
        entry["hash"] = event_hash(entry)
        self.events.append(entry)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def by_event(self, event: str) -> List[Dict[str, Any]]:
        return [entry for entry in self.events if entry["event"] == event]

    def as_jsonl(self) -> str:
        return "\n".join(json.dumps(entry, ensure_ascii=False) for entry in self.events)

    def verify(self) -> List[str]:
        """Return human-readable errors. Empty list means the chain is intact."""
        errors: List[str] = []
        expected_prev = GENESIS_HASH
        for index, entry in enumerate(self.events):
            prev = entry.get("prev_hash")
            digest = entry.get("hash")
            if prev != expected_prev:
                errors.append("event %d: prev_hash mismatch" % index)
            if not digest:
                errors.append("event %d: missing hash" % index)
            elif digest != event_hash(entry):
                errors.append("event %d: hash mismatch (payload edited)" % index)
            expected_prev = str(digest or "")
        return errors

    @classmethod
    def load(cls, path: str, verify_chain: bool = False) -> "Trace":
        """Reconstruct a trace from a JSONL file (replay / audit)."""
        events: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                events.append(json.loads(line))
        run_id = events[0]["run_id"] if events else None
        trace = cls(run_id=run_id)
        trace.events = events
        if verify_chain:
            errors = trace.verify()
            if errors:
                raise TraceError("tampered trace %s: %s" % (path, "; ".join(errors)))
        return trace
