# Skill contract: `cogram.evidence_bind`

Print the machine-readable catalog with `cogram-goai tools`.

| Field | Value |
|---|---|
| **Name** | `cogram.evidence_bind` |
| **Version** | 0.3.0 |
| **Purpose** | Bind each subtask to a non-empty evidence string; fail items that have none |
| **Invocation point** | After memory recall, before the human gate |
| **Dependent tools** | None (pure function) |
| **Failure mode** | Returns `passed=false` on the item; never invents evidence |
| **Reuse** | CI, a verifier agent, or a human checklist can call the same function |

## Input

```json
{
  "subtasks": [
    {"id": "t1", "title": "Reproduce the timeout"},
    {"id": "t2", "title": "Locate the retry wrapper"}
  ],
  "evidence": {
    "t1": "reproduced locally with tests/fixtures/large_upload.bin"
  }
}
```

## Output

Each subtask becomes one checklist row. Missing or blank evidence fails the
row. The skill does **not** judge whether the evidence is true — only that
the caller produced a cited string the human can read at the gate.

## Why it is a skill, not an if-statement in the pipeline

The verifier agent is a thin wrapper. A unit test or a later agent can call
`cogram.evidence_bind` without constructing the rest of the loop. That is the
handbook bar: reusable encapsulation, not a one-shot script.
