"""A1 — Triage Clerk: turn one issue into 2-3 budgeted subtasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from cogram_goai.tokenize import token_set

AGENT_NAME = "A1.triage_clerk"

_REPRODUCE_CUES = {"crash", "error", "fails", "failing", "traceback", "exception", "500", "报错", "崩溃", "失败"}
_TEST_CUES = {"test", "tests", "regression", "coverage", "pytest", "测试", "回归"}
_DOC_CUES = {"doc", "docs", "readme", "documentation", "文档"}
_PERF_CUES = {"slow", "timeout", "latency", "performance", "memory", "卡顿", "超时", "性能"}

_MAX_SUBTASKS = 3


@dataclass
class Subtask:
    id: str
    kind: str
    title: str
    budget_steps: int
    cues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "budget_steps": self.budget_steps,
            "cues": list(self.cues),
        }


class TriageClerk:
    """Rule-based decomposition.

    The rules are visible and few on purpose: a judge can predict the output
    from the issue text without running anything.
    """

    name = AGENT_NAME

    def run(self, issue_text: str, trace: Optional[Any] = None) -> List[Subtask]:
        tokens = token_set(issue_text)
        summary = _first_sentence(issue_text)
        subtasks: List[Subtask] = []

        def add(kind: str, title: str, budget: int, cues: List[str]) -> None:
            if len(subtasks) >= _MAX_SUBTASKS:
                return
            subtasks.append(
                Subtask(
                    id="t%d" % (len(subtasks) + 1),
                    kind=kind,
                    title=title,
                    budget_steps=budget,
                    cues=cues,
                )
            )

        repro_cues = sorted(tokens & _REPRODUCE_CUES)
        perf_cues = sorted(tokens & _PERF_CUES)
        test_cues = sorted(tokens & _TEST_CUES)
        doc_cues = sorted(tokens & _DOC_CUES)

        if repro_cues:
            add("reproduce", "Reproduce: %s" % summary, 2, repro_cues)
        elif perf_cues:
            add("measure", "Measure the reported slowdown: %s" % summary, 2, perf_cues)

        add("locate", "Locate the responsible module for: %s" % summary, 3, [])
        add("fix", "Draft the smallest fix for: %s" % summary, 3, [])

        if test_cues and subtasks and subtasks[-1].kind == "fix":
            subtasks[-1] = Subtask(
                id=subtasks[-1].id,
                kind="fix_with_test",
                title=subtasks[-1].title + " (with regression test)",
                budget_steps=subtasks[-1].budget_steps + 1,
                cues=test_cues,
            )
        if doc_cues and len(subtasks) < _MAX_SUBTASKS:
            add("document", "Update the docs touched by: %s" % summary, 1, doc_cues)

        if trace is not None:
            trace.record(
                self.name,
                "decomposition",
                subtasks=[task.to_dict() for task in subtasks],
                budget_total=sum(task.budget_steps for task in subtasks),
            )
        return subtasks


def _first_sentence(text: str, limit: int = 90) -> str:
    cleaned = " ".join(text.split())
    for stop in (". ", "。", "\n"):
        index = cleaned.find(stop)
        if 0 < index < limit:
            cleaned = cleaned[:index]
            break
    return cleaned[:limit].strip() or "(empty issue)"
