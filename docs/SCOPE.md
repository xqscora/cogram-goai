# Scope: what this repository is, and what it is not

This repository is a **public competition slice**. It was written to make one
idea legible — agents that share a memory need a gate, a cited context packet,
and a trace, not a bigger model — and it was kept small enough to audit in an
afternoon.

## In scope

| Included | Where |
|---|---|
| Three agents with explicit decision boundaries | `src/cogram_goai/agents/` |
| Five reusable skills | recall, evidence_bind, redact, approval_gate, path_guard |
| Audited synonym table (not embeddings) | `src/cogram_goai/aliases.py` |
| Cited context packet + evidence bands + conflict | `agents/memory.py` `context_packet` |
| Hash-chained JSONL trace + replay + verify | `src/cogram_goai/trace.py`, `cogram-goai verify-trace` |
| Human approval gate | `src/cogram_goai/pipeline.py` |
| Rollback that does not delete the row | `NoteStore.rollback` |
| CLI and runnable example | `src/cogram_goai/cli.py`, `examples/` |
| Tests, zero dependencies | `tests/` |

## Explicitly out of scope

None of the following is present here, and none of it is implied by anything
here:

- Vector search, embeddings, rerankers, or any model call
- Any form of graph memory, activation decay, or novelty/surprise gating
- Line-level source routing or symbol resolution
- Private benchmarks, held-out evaluation sets, or precision numbers
- Cloud sync, account systems, authentication, or license keys
- Closed binaries, paid distribution, or proprietary trajectory datasets

If a reviewer asks how this compares to a production memory system: it does not
compare. This is the public slice. The scoring function is still short enough
to verify by hand.

## Honest limitations

1. The synonym table only covers the pairs we wrote down. Unlisted paraphrases
   still miss. That is intentional — adding a pair is a documented edit.
2. Triage rules are cue-word based. An issue that avoids the cue words gets the
   generic `locate` + `fix` decomposition.
3. The verifier checks that evidence *exists*, not that it is true. It is a
   forcing function for the human at the gate, not a judge.
4. The note store is a flat JSON list loaded into memory. It is fine for
   hundreds of notes and wrong for hundreds of thousands.

These are stated rather than hidden because the alternative — a demo that
implies production capability — is worse than a small honest one.
