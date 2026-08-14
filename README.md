# cogram-goai

**Three agents, five reusable skills, one cited memory, and a human who has to say yes.**

A dependency-free reference implementation of a production-shaped multi-agent
loop for software issues: triage decomposes the work, memory recalls *cited*
prior notes (never a bare dump), the verifier refuses unevidenced subtasks,
and nothing is written back without an explicit human approval. Captures can
be rolled back without deleting the audit row.

This is the public GOAI 2026 Agent Infra slice of Cogram. It is not the
product. See [docs/SCOPE.md](docs/SCOPE.md).

[中文说明](README.zh-CN.md) · [Architecture](docs/ARCHITECTURE.md) · [Skill contracts](docs/SKILL_keyword_recall.md) · [evidence_bind](docs/SKILL_evidence_bind.md) · [audit skills](docs/SKILL_audit.md) · [GOAI mapping](docs/GOAI_2026.md)

---

## Why this exists (judge in 30 seconds)

GOAI Agent Infra asks for **at least three agents**, **reusable skills**,
**context that can be audited**, and **approval / rollback / evidence**.

| Handbook requirement | Where it is |
|---|---|
| Multi-agent closed loop | A1 triage → A2 memory → A3 verifier → human gate |
| Reusable skills, not one-shot scripts | five contracts in `cogram-goai tools` |
| Context + execution evidence | cited `context` packet + hash-chained JSONL + evidence map |
| Security / approval / rollback / audit | path guard, redact-on-capture, pending-if-no-approver, `rollback`, `verify-trace` |
| Honest open-source slice | Apache-2.0, zero runtime deps |

It does **not** call a model, embed text, or sync to the cloud. Every score
is token overlap plus a one-page synonym table you can read.

---

## Install and run

```bash
git clone https://github.com/xqscora/cogram-goai.git
cd cogram-goai
pip install -e .

cogram-goai demo --auto-approve --trace run.jsonl
cogram-goai demo --conflict --auto-approve --no-capture
cogram-goai replay --trace run.jsonl
cogram-goai verify-trace --trace run.jsonl
cogram-goai tools
```

Requires Python 3.9+. There are no runtime dependencies.

Sample output:

```
[A1 triage] 3 subtasks
  - t1 (reproduce, budget 2) Reproduce: Large file upload fails with a timeout...
  - t2 (locate, budget 3) Locate the responsible module for: ...
  - t3 (fix_with_test, budget 4) Draft the smallest fix for: ... (with regression test)

[A2 memory] 3 recalled note(s)
  - note-001 score=11.0 band=high :: Uploads over 8 MB time out because the retry wrapper...
      matched: mb, over, retry, uploads, wrapper
  auto-inject (high band): note-001

[A3 verifier] all items passed
  [x] Reproduce: ... <- reproduced locally with tests/fixtures/large_upload.bin

[gate] approved=True
[memory] captured new note note-20260814-008
```

---

## The loop

```
issue text
   → A1 triage_clerk           split into 2–3 budgeted subtasks
   → A2 keyword_memory         skill cogram.keyword_recall
   → context packet            citations + evidence band; only `high` is auto-injected
                               (two high notes with different causes → inject nothing)
   → A3 checklist_verifier     skill cogram.evidence_bind
   → human approval gate       nothing is written without an explicit yes
   → A2 keyword_memory         append one structured note (text / cause / fix)
   → optional rollback         status=rolled_back; the row stays for audit
```

Every step appends one JSON line to the trace. Each line carries `prev_hash`
and `hash`. Replay does not re-run the agents — it reconstructs what already
happened, and `verify-trace` refuses an edited file:

```bash
cogram-goai replay --trace run.jsonl
cogram-goai verify-trace --trace run.jsonl
```

---

## Skills

Print the machine-readable catalog:

```bash
cogram-goai tools
cogram-goai contract          # keyword_recall only
```

### `cogram.keyword_recall`

Scoring is hand-checkable: one point per overlapping body token (after an
**audited synonym table** so `超时` and `timeout` match), two points per
overlapping tag. Ties broken by note id.

Each hit carries an **evidence band** (shape taken from Cogram's public
product contract, computed only from what this slice can see):

| Band | Meaning here | Auto-injected into the next agent? |
|---|---|---|
| `high` | a curated tag overlapped | yes |
| `medium` | body / synonym overlap only | cited, not auto-injected |
| `unknown` | no hit | `fallback: manual_search` |

The skill never claims a note is a correct fix. Rolled-back notes are skipped.

### `cogram.evidence_bind`

Pure function: subtask list + `{id: evidence}` map → checklist. Missing
evidence fails the item. The verifier agent is a thin wrapper around this
skill, so a CI job can call the same contract without the rest of the pipeline.

### `cogram.redact` / `cogram.approval_gate` / `cogram.path_guard`

The three security skills are also in the catalog. Capture runs `redact`
before append. The gate skill is the only license to write. `path_guard`
is the same denylist `NoteStore` uses, callable on its own.

---

## CLI

| Command | What it does |
|---|---|
| `cogram-goai demo` | Run the bundled issue end to end (`--conflict` for disagreeing high notes) |
| `cogram-goai run --issue-file bug.txt --evidence '{"t1":"repro log"}'` | Run your own issue |
| `cogram-goai skill --issue "..."` | Call recall on its own |
| `cogram-goai tools` | Print every skill contract |
| `cogram-goai notes --add "lesson" --tag retry` | Inspect or extend the note store |
| `cogram-goai rollback --note-id note-…` | Mark a capture rolled back |
| `cogram-goai replay --trace run.jsonl` | Print a saved audit trail |
| `cogram-goai verify-trace --trace run.jsonl` | Check the hash chain (`--complete` also requires a full event set) |

Useful flags: `--notes PATH`, `--trace PATH`, `--auto-approve` / `--reject`, `--json`.

---

## Design rules

1. **Nothing is written without a human yes.** `run_pipeline` returns
   `approved=None` when no approver is supplied.
2. **An unevidenced subtask fails the checklist.** Presence, not quality. The same sentence cannot cover two subtasks.
3. **Only one agent touches storage.** `KeywordMemoryAgent` owns every read
   and write. Rollback is the same agent.
4. **The note store cannot be pointed at secrets.** Paths containing `.env`,
   `secret`, `token`, `credential`, `password`, `id_rsa` or `.pem` are refused.
5. **Recall degrades, it does not hallucinate.** No match → explicit fallback.
6. **Rollback is not delete.** The row stays with `status: rolled_back`.
7. **Context is cited.** Downstream agents receive a packet with ids, bands
   and reasons — not an uncited blob.
8. **Conflict is visible.** Two `high` notes with different causes empty
   `auto_inject`. The human still sees every citation.
9. **The trace is tamper-evident.** Editing a JSONL line breaks `verify-trace`.
10. **A capture cites its run.** Each written note stores `run_id` and `issue_hash`. The same pair is not appended twice.
11. **Security cues become a budgeted subtask.** `auth` / `cors` / `oauth` / `xss` add a `secure` item instead of hoping the fix agent notices.

---

## Tests

```bash
python -m unittest discover tests -v
```

Zero dependencies. Python 3.9+.

## License

Apache-2.0. See [LICENSE](LICENSE) and [docs/SCOPE.md](docs/SCOPE.md).
