# ACC Global Archive — `~/.claude/acc`

This directory is the **cross-project** ACC archive: lossy, high-signal session
checkpoints written with `--global`, shared across every project on this
machine. The location is overridable with the `ACC_GLOBAL_DIR` environment
variable.

## Naming convention

```
NNN-YYYY-MM-DD-topic.md
```

- `NNN` — zero-padded sequence number (`001`, `002`, …). Highest number = newest.
- `YYYY-MM-DD` — date the checkpoint was produced.
- `topic` — short kebab-case focus slug.

Filenames sort **lexicographically**, so the highest filename is always the most
recent entry. Tooling relies on this — do not rename files out of sequence.

## What lands here

Only entries explicitly written with `new_acc.py --global`. Per-project
`docs/acc/` archives are separate and are never scanned into this one. Each
global entry carries a `**Source project:**` line recording where it was
produced, so consumers can tell whose work a checkpoint describes.

## Lifecycle

- **Producer** — `new_acc.py --topic <slug> --global` scaffolds a new entry here.
- **Consumer** — `acc_session_start.py --global` (the SessionStart hook) falls
  back to this archive when the current project has no `docs/acc/` entries; the
  project archive always takes precedence. `find_latest_acc.py --global` and
  `list_acc.py --global` read this archive directly.

## Notes

- This `README.md` is **excluded** from the "latest entry" search.
- Checkpoints here travel between projects by design — keep the per-project
  default for anything that shouldn't.
