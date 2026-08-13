"""A3 — Checklist Verifier: every subtask needs evidence before approval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from cogram_goai.agents.triage import Subtask
from cogram_goai.skill import BIND_SKILL_NAME, evidence_bind

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
    """Turns subtasks into a checklist via ``cogram.evidence_bind``.

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
        bound = evidence_bind(
            [task.to_dict() for task in subtasks],
            dict(evidence or {}),
        )
        items = [
            ChecklistItem(
                subtask_id=item["subtask_id"],
                requirement=item["requirement"],
                passed=item["passed"],
                evidence=item["evidence"],
            )
            for item in bound["items"]
        ]
        if trace is not None:
            trace.record(
                self.name,
                "verification",
                skill=BIND_SKILL_NAME,
                passed=sum(1 for item in items if item.passed),
                total=len(items),
                items=[item.to_dict() for item in items],
            )
        return items

    @staticmethod
    def all_passed(items: Sequence[ChecklistItem]) -> bool:
        return bool(items) and all(item.passed for item in items)
