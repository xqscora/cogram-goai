"""The closed loop: decompose, recall, verify, gate on a human, capture."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional

from cogram_goai.agents.memory import KeywordMemoryAgent
from cogram_goai.agents.triage import Subtask, TriageClerk
from cogram_goai.agents.verifier import ChecklistItem, ChecklistVerifier
from cogram_goai.notes import Note, NoteStore
from cogram_goai.skill import approval_gate
from cogram_goai.trace import Trace

#: An approval callback receives the result-so-far and returns True to merge.
ApprovalFn = Callable[["PipelineResult"], bool]

PIPELINE_AGENT = "pipeline"


def approve_always(_: "PipelineResult") -> bool:
    return True


def approve_never(_: "PipelineResult") -> bool:
    return False


def issue_hash(text: str) -> str:
    """Stable 16-hex digest of whitespace-normalized issue text."""
    normalized = " ".join((text or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


@dataclass
class PipelineResult:
    issue_text: str
    subtasks: List[Subtask] = field(default_factory=list)
    recall: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    checklist: List[ChecklistItem] = field(default_factory=list)
    verified: bool = False
    approved: Optional[bool] = None
    captured_note_id: Optional[str] = None
    issue_hash: str = ""
    trace: Optional[Trace] = None

    @property
    def run_id(self) -> str:
        return self.trace.run_id if self.trace else ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "issue_hash": self.issue_hash,
            "issue_text": self.issue_text,
            "subtasks": [task.to_dict() for task in self.subtasks],
            "recall": self.recall,
            "context": self.context,
            "checklist": [item.to_dict() for item in self.checklist],
            "verified": self.verified,
            "approved": self.approved,
            "captured_note_id": self.captured_note_id,
        }


def run_pipeline(
    issue_text: str,
    store: NoteStore,
    trace: Optional[Trace] = None,
    evidence: Optional[Mapping[str, str]] = None,
    approve: Optional[ApprovalFn] = None,
    max_notes: int = 3,
    capture: bool = True,
    capture_tags: Optional[List[str]] = None,
) -> PipelineResult:
    """Run one issue through the three agents.

    ``approve`` is required for anything to be written back. Leaving it as
    ``None`` means the run stops at the gate with ``approved=None``, which is
    what a headless CI run should see.
    """
    trace = trace or Trace()
    digest = issue_hash(issue_text)
    result = PipelineResult(issue_text=issue_text, issue_hash=digest, trace=trace)

    trace.record(
        PIPELINE_AGENT,
        "task_input",
        chars=len(issue_text),
        issue_hash=digest,
        notes_in_store=len(store.active()),
    )

    result.subtasks = TriageClerk().run(issue_text, trace=trace)

    memory = KeywordMemoryAgent(store)
    result.recall = memory.recall(issue_text, max_notes=max_notes, trace=trace)
    result.context = memory.context_packet(result.recall)
    trace.record(
        PIPELINE_AGENT,
        "context_packet",
        citations=[item["id"] for item in result.context.get("citations", [])],
        auto_inject=result.context.get("auto_inject", []),
        fallback=result.context.get("fallback"),
        conflict=result.context.get("conflict"),
    )

    result.checklist = ChecklistVerifier().run(result.subtasks, evidence=evidence, trace=trace)
    result.verified = ChecklistVerifier.all_passed(result.checklist)

    if not result.verified:
        trace.record(PIPELINE_AGENT, "gate_skipped", reason="checklist_incomplete")
        return result

    if approve is None:
        trace.record(PIPELINE_AGENT, "gate_pending", reason="no_approver")
        return result

    result.approved = bool(approve(result))
    gate = approval_gate(result.verified, result.approved)
    trace.record(
        PIPELINE_AGENT,
        "human_approval",
        approved=result.approved,
        gate_state=gate["state"],
        allowed=gate["allowed"],
    )

    if gate["allowed"] and capture:
        cause, fix = _cause_fix_from_context(result.context)
        note = memory.capture(
            _capture_text(result),
            tags=capture_tags or result.recall.get("matched_tags", []),
            trace=trace,
            cause=cause,
            fix=fix,
            run_id=trace.run_id,
            issue_hash=digest,
        )
        result.captured_note_id = note.id

    return result


def rollback_capture(store: NoteStore, note_id: str, trace: Optional[Trace] = None) -> Note:
    """Undo a capture without deleting the audit row."""
    trace = trace or Trace()
    note = KeywordMemoryAgent(store).rollback(note_id, trace=trace)
    trace.record(PIPELINE_AGENT, "rollback", note_id=note.id)
    return note


def _cause_fix_from_context(context: Mapping[str, Any]) -> tuple[str, str]:
    if context.get("conflict"):
        return "", ""
    for item in context.get("citations") or []:
        if item.get("band") == "high":
            return str(item.get("cause") or ""), str(item.get("fix") or "")
    for item in context.get("citations") or []:
        if item.get("cause") or item.get("fix"):
            return str(item.get("cause") or ""), str(item.get("fix") or "")
    return "", ""


def _capture_text(result: PipelineResult) -> str:
    kinds = ", ".join(task.kind for task in result.subtasks)
    head = " ".join(result.issue_text.split())[:120]
    return "Resolved: %s | subtasks: %s" % (head, kinds)
