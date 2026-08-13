"""Minimal multi-agent pipeline with a shared keyword memory skill.

Educational slice released for the GOAI 2026 Agent Infra track. See docs/SCOPE.md
for what this project deliberately does not contain.
"""

__version__ = "0.2.0"

from cogram_goai.notes import Note, NoteStore
from cogram_goai.pipeline import PipelineResult, rollback_capture, run_pipeline
from cogram_goai.skill import (
    BIND_SKILL_NAME,
    SKILL_CATALOG,
    SKILL_CONTRACT,
    SKILL_NAME,
    evidence_bind,
    keyword_recall,
)
from cogram_goai.trace import Trace

__all__ = [
    "Note",
    "NoteStore",
    "PipelineResult",
    "rollback_capture",
    "run_pipeline",
    "BIND_SKILL_NAME",
    "SKILL_CATALOG",
    "SKILL_CONTRACT",
    "SKILL_NAME",
    "evidence_bind",
    "keyword_recall",
    "Trace",
    "__version__",
]
