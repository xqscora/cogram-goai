# Security skills: redact, approval_gate, path_guard

These three contracts sit next to recall and evidence_bind in
`cogram-goai tools`. They are small on purpose: a judge can read the
functions in one screen.

## `cogram.redact`

Replaces secret-shaped spans (`token=…`, `password=…`, `ghp_…`, `sk-…`,
`AKIA…`) with `[REDACTED]` before A2 appends a note. It is not a complete
scanner. It is the slice-sized version of "do not write the key into the
scratchpad".

## `cogram.approval_gate`

| `verified` | `decision` | `state` | `allowed` |
|---|---|---|---|
| false | anything | `blocked_unverified` | false |
| true | `null` | `pending` | false |
| true | true | `approved` | true |
| true | false | `rejected` | false |

A missing human is pending, never a yes. The pipeline records `gate_state`
on the `human_approval` event.

## `cogram.path_guard`

Same denylist as `NoteStore` (`.env`, `secret`, `token`, `credential`,
`password`, `id_rsa`, `.pem`), exposed as a skill so another agent can ask
before opening a file.

## Hash chain

`Trace.record` writes `prev_hash` + `hash` (SHA-256 of the canonical
event, `hash` field excluded). `cogram-goai verify-trace --trace run.jsonl`
exits 1 if a line was edited, inserted, or dropped.
