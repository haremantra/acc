# acc — Adaptive Context Compressor

A Claude Code skill that compresses a working session into a small, portable, version-controlled handoff artifact, so a fresh session can resume the work without replaying the conversation.

## Design

Most session-handoff tooling optimizes for *retention* — preserve as much as possible. `acc` makes the opposite bet: it optimizes for *signal density* (under 800 words, lossy by design) and ships with a **necessity gate** that decides whether an artifact should be produced at all — defaulting to `HANDOFF.md` when an `acc` would add no inter-session leverage.

## Modes

- **Mode A — produce.** `/acc [focus]` extracts five dimensions from the current session (Decisions / Current State / Open Questions / Rejected Approaches / Next Actions) and writes `docs/acc/NNN-YYYY-MM-DD-topic.md`.
- **Mode B — consume.** `/acc invoke-last` loads the newest archive entry into a fresh session as inherited context.

## Install

```bash
git clone https://github.com/haremantra/acc.git ~/.claude/skills/acc
```

Restart Claude Code (or refresh skills) and invoke `/acc`.

## Layout

| Path | Purpose |
|---|---|
| `SKILL.md` | Skill definition: process steps, rules, bundled resources |
| `scripts/new_acc.py` | Scaffold a new ACC entry (Mode A) |
| `scripts/find_latest_acc.py` | Locate the newest entry (Mode B) |
| `assets/acc-template.md` | Canonical output skeleton |
| `assets/docs-acc-readme.md` | README seed dropped into `docs/acc/` on first run |
| `references/necessity-check.md` | Step-0 rubric — 9 criteria for ACC vs. HANDOFF |
| `references/example-acc.md` | Good vs. bad worked example |

## Requirements

- Claude Code
- Python 3.x for the helper scripts (stdlib only)

## License

MIT. See `LICENSE`.
