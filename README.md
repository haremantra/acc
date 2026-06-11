# acc

[![CI](https://github.com/haremantra/acc/actions/workflows/ci.yml/badge.svg)](https://github.com/haremantra/acc/actions/workflows/ci.yml)

A session checkpoint for Claude Code. Five sections, one file, replay-free resume.

## What it does

Long sessions end and the next thread starts cold. Auto-compaction summarizes away the load-bearing parts — the decisions, the things you tried and ruled out — so even a compacted replay loses the most expensive context. `acc` writes a session checkpoint at end-of-session that the next thread loads as inherited context. You resume from your reasoning, not from a replay of the transcript.

The checkpoint is at most 800 words in five fixed sections. A typical session goes from ~150k tokens to ~1k.

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

Useful if you want the working tree in `~/code/` (or somewhere else) and just want to expose it to Claude Code through a link. From inside the clone, the bundled installer does the symlink and verifies it for you:

**macOS / Linux:**
```bash
git clone https://github.com/haremantra/acc.git ~/code/acc
cd ~/code/acc && ./install.sh          # or: make install  (add --copy to copy instead of symlink)
```

**Windows (PowerShell, run as Administrator or with Developer Mode on):**
```powershell
git clone https://github.com/haremantra/acc.git C:\code\acc
cd C:\code\acc; ./install.ps1           # add -Copy to copy instead of symlink
```

Remove it later with `make uninstall` (or just delete `~/.claude/skills/acc`).

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

## Auto-load on session start (optional)

Typing `/acc invoke-last` every time is easy to forget. A `SessionStart` hook makes it automatic: every new session in a project that has a `docs/acc/` archive inherits the latest entry, no command needed. Copy `assets/session-start-settings.json` into the project's `.claude/settings.json` (merge it if the file already exists):

```jsonc
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          { "type": "command", "command": "python3 \"$HOME/.claude/skills/acc/scripts/acc_session_start.py\"", "timeout": 15 }
        ]
      }
    ]
  }
}
```

On Windows use `python` and `%USERPROFILE%`. The hook is exit-0-safe (a misfire never blocks startup) and stays silent in projects with no archive, so it's safe to set globally in `~/.claude/settings.json`. `matcher: "startup"` fires on new sessions only, not resumes.

## Browse the archive

Once an archive has more than a handful of entries:

```bash
python scripts/list_acc.py                 # dated, focus-labeled table, newest first
python scripts/list_acc.py --markdown      # Markdown table you can paste into a README index
```

## Global vs per-project archive

By default every entry lands in `./docs/acc/` of the project you're in — checkpoints live with the code they describe. If you'd rather keep **one archive across all projects** (handy when you hop between many repos), pass `--global` to any of the scripts:

```bash
python scripts/new_acc.py --topic auth-rewrite --global   # writes ~/.claude/acc/NNN-…md
python scripts/find_latest_acc.py --global                # newest across all projects
python scripts/list_acc.py --global                       # browse the global archive
```

The global location is `~/.claude/acc`, overridable with the `ACC_GLOBAL_DIR` environment variable. `--global` and `--dir` are mutually exclusive. For the SessionStart hook, append `--global` to the command in `settings.json` to auto-load from the shared archive instead of the project one.

## Layout

| Path | Purpose |
|---|---|
| `SKILL.md` | Skill definition: process steps, rules, bundled resources |
| `scripts/new_acc.py` | Scaffold a new `acc` entry (produce mode); `--dry-run` to preview |
| `scripts/find_latest_acc.py` | Locate the newest entry (consume mode) |
| `scripts/list_acc.py` | Print the archive as an index (`--markdown` for a table) |
| `scripts/acc_session_start.py` | SessionStart hook: auto-load the latest entry into a fresh session |
| `assets/acc-template.md` | Canonical output skeleton |
| `assets/docs-acc-readme.md` | README seed dropped into `docs/acc/` on first run |
| `assets/session-start-settings.json` | Example `.claude/settings.json` for the hook |
| `references/necessity-check.md` | The Step 0 rubric, 9 criteria for `acc` vs. `HANDOFF` |
| `references/example-acc.md` | Good vs. bad worked example |
| `tests/` | Unit, skill-integrity, and usability tests (stdlib `unittest`) |
| `install.sh` / `install.ps1` / `Makefile` | One-command install + dev targets |
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
