# Agent identity list

Scenario: collaborative triage of software issues over a shared note store.
Roles are orchestrated by `cogram_goai.pipeline`; there is no autonomous
controller and no agent-to-agent messaging outside the pipeline.

## A1 — `triage_clerk`

| Field | Value |
|---|---|
| **Code name** | `A1.triage_clerk` (`agents/triage.py`) |
| **Role** | Intake and task decomposition |
| **Capabilities** | Parse issue text; emit 2–3 subtasks with a kind, title and step budget |
| **Inputs** | `issue_text` |
| **Outputs** | `List[Subtask]` — `{id, kind, title, budget_steps, cues}` |
| **Dependencies** | `cogram_goai.tokenize` only |
| **Decision boundary** | Routing and splitting only. Cannot read or write the note store, cannot touch files, cannot approve |
| **Trace** | `decomposition` — full subtask list plus total budget |

Kinds it can emit: `reproduce`, `measure`, `locate`, `fix`, `fix_with_test`,
`document`. The mapping from cue words to kinds is a literal set membership test
in `agents/triage.py`.

## A2 — `keyword_memory`

| Field | Value |
|---|---|
| **Code name** | `A2.keyword_memory` (`agents/memory.py`) |
| **Role** | Shared note recall, and the single writer |
| **Capabilities** | Call `cogram.keyword_recall`; append one note after an approved run |
| **Inputs** | `issue_text`, `max_notes`, `min_score` |
| **Outputs** | `{notes[], matched_tags[], query_tokens[], fallback}` |
| **Dependencies** | `cogram_goai.skill`, a `NoteStore` |
| **Decision boundary** | Read-only during a run; writes only when the pipeline reports an approved gate. Cannot invent notes — a miss returns `fallback="manual_search"`. Cannot open a store whose path looks like a secret |
| **Trace** | `skill_call` (hits, note ids, matched tags, fallback), `experience_capture` (note id, tags, persisted) |

## A3 — `checklist_verifier`

| Field | Value |
|---|---|
| **Code name** | `A3.checklist_verifier` (`agents/verifier.py`) |
| **Role** | Evidence check before the human sees the run |
| **Inputs** | `subtasks`, `evidence` map of subtask id → string |
| **Outputs** | `List[ChecklistItem]` — `{subtask_id, requirement, passed, evidence}` |
| **Dependencies** | A1 output |
| **Decision boundary** | Judges presence of evidence, never its correctness. Cannot merge, cannot write, cannot skip an item. An empty checklist is not a pass |
| **Trace** | `verification` — passed/total plus every item |

## Human

| Field | Value |
|---|---|
| **Role** | Approval gate |
| **Inputs** | The full `PipelineResult` |
| **Outputs** | `True` / `False` |
| **Decision boundary** | The only actor allowed to authorise a write-back. Absent approver means `approved=None` and no write |
| **Trace** | `human_approval` |

## Collaboration graph

```
triage_clerk → keyword_memory → checklist_verifier → HUMAN → keyword_memory (capture)
```

Agents never call each other directly; `pipeline.run_pipeline` is the only
caller, which keeps the trace complete by construction.
