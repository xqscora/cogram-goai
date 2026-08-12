# Skill contract: `cogram.keyword_recall`

Print the machine-readable version at any time with `cogram-goai contract`.

| Field | Value |
|---|---|
| **Name** | `cogram.keyword_recall` |
| **Version** | 0.1.0 |
| **Purpose** | Recall up to N previously captured notes whose keywords overlap the issue text |
| **Invocation point** | After triage, before any patch is written |
| **Dependent tools** | Local file read/write, or an equivalent MCP file tool |
| **Failure mode** | Returns an empty list plus `fallback="manual_search"`; never raises on a miss |
| **Reuse** | Any agent may call it; it is the shared scratchpad lookup |

## Input

```json
{
  "issue_text": "Large uploads time out on retry",
  "max_notes": 3,
  "min_score": 1.0
}
```

| Field | Type | Default | Notes |
|---|---|---|---|
| `issue_text` | string | required | Free-form issue or task text |
| `max_notes` | int ≥ 1 | 3 | `ValueError` if below 1 |
| `min_score` | float ≥ 0 | 1.0 | Raise it to demand stronger overlap |

## Output

```json
{
  "skill": "cogram.keyword_recall",
  "notes": [
    {
      "id": "note-001",
      "text": "Uploads over 8 MB time out because the retry wrapper reuses a consumed stream.",
      "tags": ["upload", "timeout", "retry"],
      "score": 11.0,
      "matched": ["mb", "over", "retry", "uploads", "wrapper"],
      "matched_tags": ["retry", "upload"]
    }
  ],
  "matched_tags": ["retry", "upload"],
  "query_tokens": ["large", "retry", "time", "timeout", "uploads"],
  "fallback": null
}
```

`matched_tags` at the top level is collected **only from the notes actually
returned**, so the caller is never shown context it did not receive.

## Scoring

```
score(note) = 1.0 × |query_tokens ∩ note_body_tokens|
            + 2.0 × |query_tokens ∩ note_tags|
```

Sorted by descending score, ties broken by note id so runs are reproducible.
Tags are worth double because they are curated by a human at capture time,
whereas body tokens are incidental.

## Tokenization

1. Lowercase.
2. Split on non-alphanumerics; keep tokens of length ≥ 2.
3. Drop a fixed English stopword list.
4. Split CJK runs into character bigrams (`上传超时` → `上传`, `传超`, `超时`).
5. De-duplicate, preserving order.

Step 4 is why a Chinese issue can recall a Chinese note without a segmentation
library. It is crude: it also produces junk bigrams that cross word boundaries.
Those simply fail to match anything, so they cost recall precision, not
correctness.

## Security boundary

- The skill is **read-only** over the note store.
- The store refuses paths whose filename contains `.env`, `secret`,
  `credential`, `password`, `token`, `id_rsa`, or `.pem`
  (`cogram_goai.notes.FORBIDDEN_PATH_PARTS`).
- The skill never calls out to the network and never executes note contents.

## Worked example

Note store:

| id | text | tags |
|---|---|---|
| n1 | Uploads time out because the retry wrapper reuses a stream | upload, retry |
| n2 | Login 500s came from an expired signing key | login, auth |

Query: `"upload retry timeout"` → query tokens `{upload, retry, timeout}`.

- n1: body hits `{retry}` = 1.0; tag hits `{upload, retry}` = 4.0 → **5.0**
- n2: no hits → filtered out by `min_score`

Result: one note, `matched_tags = ["upload", "retry"]`, `fallback = null`.
