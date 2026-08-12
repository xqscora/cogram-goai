"""Append-only JSONL trace of everything the pipeline did."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional


class Trace:
    """Records one line of JSON per pipeline event.

    Events are kept in memory as well as written to disk so that tests and the
    CLI can assert on them without re-reading the file.
    """

    def __init__(self, path: Optional[str] = None, run_id: Optional[str] = None) -> None:
        self.path = path
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.events: List[Dict[str, Any]] = []
        if self.path:
            parent = os.path.dirname(os.path.abspath(self.path))
            if parent:
                os.makedirs(parent, exist_ok=True)

    def record(self, agent: str, event: str, **payload: Any) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "run_id": self.run_id,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z",
            "agent": agent,
            "event": event,
        }
        if payload:
            entry["payload"] = payload
        self.events.append(entry)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def by_event(self, event: str) -> List[Dict[str, Any]]:
        return [entry for entry in self.events if entry["event"] == event]

    def as_jsonl(self) -> str:
        return "\n".join(json.dumps(entry, ensure_ascii=False) for entry in self.events)
