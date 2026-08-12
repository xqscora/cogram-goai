# Architecture

```
                       ┌──────────────────────────────┐
   issue text ────────▶│ A1  triage_clerk             │
                       │ rule-based decomposition     │
                       └──────────────┬───────────────┘
                                      │ 2-3 subtasks (+ budget)
                       ┌──────────────▼───────────────┐        ┌──────────────┐
                       │ A2  keyword_memory           │◀──────▶│  notes.json  │
                       │ skill: cogram.keyword_recall │  read  └──────────────┘
                       └──────────────┬───────────────┘
                                      │ recalled notes
                       ┌──────────────▼───────────────┐
                       │ A3  checklist_verifier       │
                       │ subtask × evidence           │
                       └──────────────┬───────────────┘
                                      │ verified?
                       ┌──────────────▼───────────────┐
                       │   HUMAN APPROVAL GATE        │
                       └──────────────┬───────────────┘
                            approved  │
                       ┌──────────────▼───────────────┐        ┌──────────────┐
                       │ A2  capture one note         │───────▶│  notes.json  │
                       └──────────────────────────────┘  write └──────────────┘

   every step ─────────────────────────────────────────────────▶  run.jsonl
```

## Modules

| Module | Responsibility |
|---|---|
| `cogram_goai.tokenize` | The one tokenizer, shared by agents and skill |
| `cogram_goai.notes` | `Note`, `NoteStore`, path safety rules |
| `cogram_goai.skill` | `cogram.keyword_recall` and its contract |
| `cogram_goai.agents.triage` | A1 — issue → subtasks |
| `cogram_goai.agents.memory` | A2 — the only module that reads or writes the store |
| `cogram_goai.agents.verifier` | A3 — checklist over subtasks and evidence |
| `cogram_goai.pipeline` | Orchestration, approval gate, capture |
| `cogram_goai.trace` | Append-only JSONL event log |
| `cogram_goai.cli` | `cogram-goai` commands |

## Why this shape

**Context passing is the actual problem.** The second agent on a task usually
re-derives what the first one already knew. Everything else here exists to make
that hand-off inspectable: the skill emits which note ids it returned, the
verifier emits which requirement each piece of evidence answered, and the trace
keeps both.

**One writer.** Read and write both live in `KeywordMemoryAgent`. Triage and
verification are pure functions of their inputs, which is why they are trivial
to test and why a reviewer only has to audit one module for storage safety.

**The gate is structural, not advisory.** `run_pipeline` takes an `approve`
callable. With no approver, the run returns `approved=None` and writes nothing —
so a scheduled or headless invocation cannot grow memory on its own. Two helpers,
`approve_always` and `approve_never`, exist for tests and CI.

## Event vocabulary in the trace

| Event | Emitted by | Payload highlights |
|---|---|---|
| `task_input` | pipeline | `chars`, `notes_in_store` |
| `decomposition` | A1 | `subtasks[]`, `budget_total` |
| `skill_call` | A2 | `skill`, `hits`, `note_ids`, `matched_tags`, `fallback` |
| `verification` | A3 | `passed`, `total`, `items[]` |
| `gate_skipped` | pipeline | `reason=checklist_incomplete` |
| `gate_pending` | pipeline | `reason=no_approver` |
| `human_approval` | pipeline | `approved` |
| `experience_capture` | A2 | `note_id`, `tags`, `persisted` |

A run that reaches `experience_capture` without a preceding `human_approval`
with `approved=true` would be a bug; `tests/test_pipeline.py` asserts the
ordering exists.

## Extending it

The skill is the seam. `keyword_recall(issue_text, notes, ...)` is a pure
function returning the documented shape; swapping in a different retrieval
strategy means replacing that one function and keeping the contract. The agents,
gate, and trace do not change.
