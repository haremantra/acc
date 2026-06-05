# acc

[![CI](https://github.com/haremantra/acc/actions/workflows/ci.yml/badge.svg)](https://github.com/haremantra/acc/actions/workflows/ci.yml)

A Claude Code skill for ending a session and not having to re-explain it to the next one.

## What it does

Long sessions end and the next thread starts cold. Auto-compaction summarizes away the load-bearing parts (the decisions, the things you already tried and ruled out), so even a compacted replay loses the most expensive context. `acc` writes a small artifact at the end of a session that the next thread loads as inherited context. Replay isn't necessary anymore.

Average run: about 150k tokens of conversation down to about 1k. The artifact is at most 800 words, in five fixed sections.

| Section | What goes here |
|---|---|
| Decisions | What got decided, and why |
| Current State | What exists right now (files, branches, versions, tests) |
| Open Questions | What's blocked |
| Rejected Approaches | What was tried and ruled out |
| Next Actions | Ordered, specific enough to execute |

That fourth section is the one most handoff tooling drops. Auto-compaction tends to summarize away "we tried X, it failed because Y", and then the next session re-tries X. `acc` captures that on purpose. Negative knowledge is the most expensive class of facts to rediscover, so it gets a first-class slot.

## The second bet

A Step 0 necessity gate that aborts production if a plain `HANDOFF.md` would carry the same load. Most session-handoff skills always produce. This one asks if it should. The worst thing a productivity tool can do is run on momentum and dilute its own archive, so the gate fires often by design.

## Other tools in this space

There are good ones (mem0, Zep, REMvisual/claude-handoff). They're mostly retention-maximalist: preserve as much of the session as possible, dossier-style. `acc` is the lossy-digest end of that trade-off. For a 500k-token session with buried load-bearing facts, the dossier approach is probably the right tool. For a one-page checkpoint that seeds the next thread, this one is.

## Two modes

- **Produce.** `/acc [focus]` extracts the five sections from the current session and writes `docs/acc/NNN-YYYY-MM-DD-topic.md` in the project being worked on.
- **Consume.** `/acc invoke-last` loads the newest archive entry into a fresh session as inherited context.

## Requirements

- Claude Code (any recent version)
- Git, for clone and updates
- Python 3.8+, stdlib only, nothing to `pip install`

## Install

Claude Code discovers skills at `~/.claude/skills/<name>/SKILL.md`. Clone this repo directly into that path.

### macOS / Linux

```bash
git clone https://github.com/haremantra/acc.git ~/.claude/skills/acc
```

### Windows (PowerShell)

```powershell
git clone https://github.com/haremantra/acc.git "$HOME\.claude\skills\acc"
```

### Windows (Command Prompt)

```cmd
git clone https://github.com/haremantra/acc.git "%USERPROFILE%\.claude\skills\acc"
```

### Alternative: clone elsewhere and symlink (development workflow)

Useful if you want the working tree in `~/code/` (or somewhere else) and just want to expose it to Claude Code through a link.

**macOS / Linux:**
```bash
git clone https://github.com/haremantra/acc.git ~/code/acc
ln -s ~/code/acc ~/.claude/skills/acc
```

**Windows (PowerShell, run as Administrator or with Developer Mode on):**
```powershell
git clone https://github.com/haremantra/acc.git C:\code\acc
New-Item -ItemType SymbolicLink -Path "$HOME\.claude\skills\acc" -Target "C:\code\acc"
```

## Verify

Open Claude Code in any project and run:

```
/acc
```

The skill will first decide whether the session even warrants an `acc` (that's the necessity gate). To load the most recent archived `acc` into a fresh session, run:

```
/acc invoke-last
```

If `/acc` isn't recognized, restart Claude Code and check that `SKILL.md` lives at the expected path: `~/.claude/skills/acc/SKILL.md` on macOS/Linux, or `%USERPROFILE%\.claude\skills\acc\SKILL.md` on Windows.

## Layout

| Path | Purpose |
|---|---|
| `SKILL.md` | Skill definition: process steps, rules, bundled resources |
| `scripts/new_acc.py` | Scaffold a new `acc` entry (produce mode) |
| `scripts/find_latest_acc.py` | Locate the newest entry (consume mode) |
| `assets/acc-template.md` | Canonical output skeleton |
| `assets/docs-acc-readme.md` | README seed dropped into `docs/acc/` on first run |
| `references/necessity-check.md` | The Step 0 rubric, 9 criteria for `acc` vs. `HANDOFF` |
| `references/example-acc.md` | Good vs. bad worked example |
| `tests/test_scripts.py` | Unit tests for the two helper scripts |
| `tests/test_skill_integrity.py` | Checks SKILL.md frontmatter, bundled-file existence, template-token contract |
| `ruff.toml` | Lint/format config (CI's `lint` job) |

## Running the tests

The helper scripts are deterministic, so they're covered by a stdlib-only
test suite (no `pip` install needed). From the repo root:

```bash
python -m unittest discover -s tests
```

The suite covers two layers. `test_scripts.py` pins the behaviors the
helper scripts must get right every time: latest-entry selection
(lexicographic sort, `README.md` excluded) and next-entry numbering
(zero-padded, monotonic), plus slug generation, template substitution,
and exit codes. `test_skill_integrity.py` validates the bundle itself —
SKILL.md frontmatter, that every bundled file it advertises exists, and
that every `{{TOKEN}}` the scaffolder substitutes is present in the
template (so a rename never ships a literal `{{DATE}}` to users).

CI also runs `ruff check`, `ruff format --check`, and `compileall` over
`scripts/` and `tests/`; reproduce that locally with:

```bash
ruff check . && ruff format --check .
```

## Update

**macOS / Linux:**
```bash
git -C ~/.claude/skills/acc pull
```

**Windows (PowerShell):**
```powershell
git -C "$HOME\.claude\skills\acc" pull
```

## Uninstall

**macOS / Linux:**
```bash
rm -rf ~/.claude/skills/acc
```

**Windows (PowerShell):**
```powershell
Remove-Item -Recurse -Force "$HOME\.claude\skills\acc"
```

## Troubleshooting

**`/acc` doesn't appear in Claude Code.**
Confirm the file exists at the expected path:
- macOS/Linux: `ls ~/.claude/skills/acc/SKILL.md`
- Windows (PowerShell): `Get-ChildItem "$HOME\.claude\skills\acc\SKILL.md"`

Then restart Claude Code.

**Windows: helper scripts fail with `python3: command not found` or open the Microsoft Store.**
On Windows, invoke the scripts as `python new_acc.py ...`, not `python3 ...`. The `python3` alias often resolves to the Microsoft Store install shim, which fails silently. Either remove the shim from PATH or use the `python` launcher.

**`fatal: detected dubious ownership` when running `git` against the repo.**
This shows up on filesystems that don't record ownership (FAT/exFAT, some external drives, network shares). Mark the directory safe:

```bash
git config --global --add safe.directory <absolute-path-to-repo>
```

For a one-off invocation without touching global config:

```bash
git -c safe.directory=<absolute-path-to-repo> <command>
```

**`acc` entries are landing in the wrong project.**
The scripts write to `./docs/acc/` relative to the current working directory at the moment the skill runs, not to a global location. If entries end up in the wrong place, check Claude Code's working directory.

## When not to use this

If your handoffs already work for you, you don't need this. That's what the gate is for.

## License

MIT. See `LICENSE`.
