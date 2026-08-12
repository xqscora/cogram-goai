# cogram-goai

**Three small agents, one shared note store, and a human who has to say yes.**

A dependency-free reference implementation of the smallest useful multi-agent
loop: an issue comes in, one agent splits it into subtasks, one agent recalls
what was learned from similar issues before, one agent checks that every
subtask has evidence, and a human approves before anything is written back.

Everything is plain Python and plain JSON. No embeddings, no model calls, no
network. You can predict every output by reading the code, which is the point —
this is a teaching slice, not a product.

[中文说明](README.zh-CN.md) · [Architecture](docs/ARCHITECTURE.md) · [Skill contract](docs/SKILL_keyword_recall.md) · [Scope](docs/SCOPE.md)

---

## Install and run

```bash
git clone https://github.com/xqscora/cogram-goai.git
cd cogram-goai
pip install -e .

cogram-goai demo --auto-approve --trace run.jsonl
```

Requires Python 3.9+. There are no runtime dependencies.

Sample output:

```
[A1 triage] 3 subtasks
  - t1 (reproduce, budget 2) Reproduce: Large file upload fails with a timeout error...
  - t2 (locate, budget 3) Locate the responsible module for: ...
  - t3 (fix_with_test, budget 4) Draft the smallest fix for: ... (with regression test)

[A2 memory] 3 recalled note(s)
  - note-001 score=11.0 :: Uploads over 8 MB time out because the retry wrapper reuses
                           an already-consumed stream. Rewind before each retry.
      matched: mb, over, retry, uploads, wrapper

[A3 verifier] all items passed
  [x] Reproduce: ... <- reproduced locally with tests/fixtures/large_upload.bin

[gate] approved=True
[memory] captured new note note-20260812-008
```

## The loop

```
issue text
   → A1 triage_clerk        split into 2-3 budgeted subtasks
   → A2 keyword_memory      call skill cogram.keyword_recall on the note store
   → A3 checklist_verifier  every subtask must carry evidence
   → human approval gate    nothing is written without an explicit yes
   → A2 keyword_memory      append one note so the next run starts warmer
```

Every step appends one JSON line to the trace, so a reviewer can reconstruct a
run without trusting the summary:

```json
{"run_id":"4f58c0ff2c5b","ts":"2026-08-12T09:46:36Z","agent":"A2.keyword_memory",
 "event":"skill_call","payload":{"skill":"cogram.keyword_recall","hits":3,
 "note_ids":["note-001","note-003","note-002"],"fallback":null}}
```

## The skill: `cogram.keyword_recall`

One skill, fully specified in [docs/SKILL_keyword_recall.md](docs/SKILL_keyword_recall.md)
and printable at runtime:

```bash
cogram-goai contract          # the machine-readable contract
cogram-goai skill --issue "upload times out on retry"
```

Scoring is deliberately hand-checkable: one point per overlapping body token,
two points per overlapping tag, ties broken by note id. Chinese text is split
into character bigrams so mixed-language issues still match without pulling in a
segmentation dependency.

When nothing matches, the skill returns an empty list and
`fallback: "manual_search"` — it never invents a note.

## CLI

| Command | What it does |
|---|---|
| `cogram-goai demo` | Run the bundled issue end to end |
| `cogram-goai run --issue-file bug.txt --evidence '{"t1":"repro log"}'` | Run your own issue |
| `cogram-goai skill --issue "..."` | Call the recall skill on its own |
| `cogram-goai contract` | Print the skill contract as JSON |
| `cogram-goai notes --add "lesson" --tag retry` | Inspect or extend the note store |

Useful flags: `--notes PATH` (point at your own store), `--trace PATH` (write
JSONL), `--auto-approve` / `--reject` (non-interactive gates), `--json`.

## Design rules

1. **Nothing is written without a human yes.** `run_pipeline` returns
   `approved=None` when no approver is supplied; a headless run cannot silently
   grow the memory.
2. **An unevidenced subtask fails the checklist.** The verifier judges presence
   of evidence, not its quality — it will not bless work it cannot see.
3. **Only one agent touches storage.** `KeywordMemoryAgent` owns every read and
   write; the other two agents are pure functions over text.
4. **The note store cannot be pointed at secrets.** Paths containing `.env`,
   `secret`, `token`, `credential`, `password`, `id_rsa` or `.pem` are refused,
   so recall can never become exfiltration.
5. **Recall degrades, it does not hallucinate.** No match returns an explicit
   fallback flag.

## Tests

```bash
python -m unittest discover tests -v     # 46 tests, no dependencies
```

## License

Apache-2.0. See [LICENSE](LICENSE) and [docs/SCOPE.md](docs/SCOPE.md) for what
this repository intentionally does not contain.
