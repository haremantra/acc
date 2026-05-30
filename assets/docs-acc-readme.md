# ACC Archive — `docs/acc/`

This directory holds **Adaptive Context Compressor** outputs: lossy, high-signal
compressions of past working sessions, produced by the `/acc` skill.

## Naming convention

```
NNN-YYYY-MM-DD-topic.md
```

- `NNN` — zero-padded sequence number (`001`, `002`, …). Highest number = newest.
- `YYYY-MM-DD` — date the ACC was produced.
- `topic` — short kebab-case focus slug.

Filenames sort **lexicographically**, so the highest filename is always the most
recent ACC. Tooling (`find_latest_acc.py`, `new_acc.py`) relies on this — do not
rename files out of sequence.

## Lifecycle

- **Producer (Mode A)** — `/acc [focus]` compresses the current session and writes a
  new `NNN-…md` entry here.
- **Consumer (Mode B)** — `/acc invoke-last` loads the newest entry into a fresh
  session as inherited context, so you skip replaying prior conversation.

## Notes

- This `README.md` is **excluded** from the "latest ACC" search.
- Each entry is meant to stand alone: someone should be able to continue the work
  from the ACC alone, without re-reading the original conversation.
