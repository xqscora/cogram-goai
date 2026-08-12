# Scope: what this repository is, and what it is not

This repository is an **educational slice**. It was written to make one idea
legible — agents that share a memory need a gate and a trace, not a bigger
model — and it was deliberately kept small enough to audit in an afternoon.

## In scope

| Included | Where |
|---|---|
| Three agents with explicit decision boundaries | `src/cogram_goai/agents/` |
| One fully specified skill, `cogram.keyword_recall` | `src/cogram_goai/skill.py` |
| Keyword-overlap recall over a plain JSON note store | `src/cogram_goai/notes.py` |
| Append-only JSONL trace of every event | `src/cogram_goai/trace.py` |
| Human approval gate before any write-back | `src/cogram_goai/pipeline.py` |
| A CLI and a runnable example | `src/cogram_goai/cli.py`, `examples/` |
| 46 tests, zero dependencies | `tests/` |

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
compare. This is the public, simplified slice. The scoring function is five
lines because a reader should be able to verify it by hand.

## Honest limitations

1. Keyword overlap misses paraphrases. Two notes about the same bug worded
   differently will not recall each other.
2. Triage rules are cue-word based. An issue that avoids the cue words gets the
   generic `locate` + `fix` decomposition.
3. The verifier checks that evidence *exists*, not that it is true. It is a
   forcing function for the human at the gate, not a judge.
4. The note store is a flat JSON list loaded into memory. It is fine for
   hundreds of notes and wrong for hundreds of thousands.

These are stated rather than hidden because the alternative — an educational
demo that implies production capability — is worse than a small honest one.
