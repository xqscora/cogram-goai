"""A3 — Checklist Verifier: every subtask needs evidence before approval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from cogram_goai.agents.triage import Subtask

AGENT_NAME = "A3.checklist_verifier"


@dataclass
class ChecklistItem:
    subtask_id: str
    requirement: str
    passed: bool
    evidence: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subtask_id": self.subtask_id,
            "requirement": self.requirement,
            "passed": self.passed,
            "evidence": self.evidence,
        }


class ChecklistVerifier:
    """Turns subtasks into a checklist and marks each item against evidence.

    Evidence is supplied by whoever ran the subtask (a human, a coding agent, a
    CI job). This agent does not judge quality — it only refuses to let an
    unevidenced subtask reach the approval gate.
    """

    name = AGENT_NAME

    def run(
        self,
        subtasks: Sequence[Subtask],
        evidence: Optional[Mapping[str, str]] = None,
        trace: Optional[Any] = None,
    ) -> List[ChecklistItem]:
        evidence = evidence or {}
        items: List[ChecklistItem] = []
        for task in subtasks:
            supplied = str(evidence.get(task.id, "")).strip()
            items.append(
                ChecklistItem(
                    subtask_id=task.id,
                    requirement=task.title,
                    passed=bool(supplied),
                    evidence=supplied or "(missing)",
                )
            )
        if trace is not None:
            trace.record(
                self.name,
                "verification",
                passed=sum(1 for item in items if item.passed),
                total=len(items),
                items=[item.to_dict() for item in items],
            )
        return items

    @staticmethod
    def all_passed(items: Sequence[ChecklistItem]) -> bool:
        return bool(items) and all(item.passed for item in items)
