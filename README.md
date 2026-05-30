# acc — Adaptive Context Compressor

A Claude Code skill that compresses a working session into a small, portable, version-controlled handoff artifact, so a fresh session can resume the work without replaying the conversation.

---

## Requirements

- **Claude Code** — any recent version
- **Git** — for clone + updates
- **Python 3.8+** — the helper scripts use stdlib only; nothing to `pip install`

---

## Install

Claude Code discovers skills at `~/.claude/skills/<name>/SKILL.md`. The simplest install is to clone this repo directly into that path.

### macOS / Linux

```bash
git clone https://github.com/haremantra/acc.git ~/.claude/skills/acc
```

### Windows — PowerShell

```powershell
git clone https://github.com/haremantra/acc.git "$HOME\.claude\skills\acc"
```

### Windows — Command Prompt

```cmd
git clone https://github.com/haremantra/acc.git "%USERPROFILE%\.claude\skills\acc"
```

### Alternative: clone elsewhere, then symlink (development workflow)

Useful if you want the working tree in `~/code/` (or similar) and just expose it to Claude Code via a link.

**macOS / Linux:**
```bash
git clone https://github.com/haremantra/acc.git ~/code/acc
ln -s ~/code/acc ~/.claude/skills/acc
```

**Windows (PowerShell, run as Administrator or with Developer Mode enabled):**
```powershell
git clone https://github.com/haremantra/acc.git C:\code\acc
New-Item -ItemType SymbolicLink -Path "$HOME\.claude\skills\acc" -Target "C:\code\acc"
```

---

## Verify

Open Claude Code in any project and run:

```
/acc
```

The skill should activate (it will analyze whether an ACC is even warranted before producing one — that's the Step-0 necessity gate). To load the most recent archived ACC into a fresh session, run:

```
/acc invoke-last
```

If `/acc` isn't recognized, restart Claude Code and confirm `SKILL.md` is at the expected path (`~/.claude/skills/acc/SKILL.md` on macOS/Linux, `%USERPROFILE%\.claude\skills\acc\SKILL.md` on Windows).

---

## What it does

Most session-handoff tooling optimizes for *retention* — preserve as much as possible. `acc` makes the opposite bet: it optimizes for *signal density* (under 800 words, lossy by design) and ships with a **necessity gate** that decides whether an artifact should be produced at all — defaulting to `HANDOFF.md` when an `acc` would add no inter-session leverage.

### Modes

- **Mode A — produce.** `/acc [focus]` extracts five dimensions from the current session (Decisions / Current State / Open Questions / Rejected Approaches / Next Actions) and writes `docs/acc/NNN-YYYY-MM-DD-topic.md` in the project being worked on.
- **Mode B — consume.** `/acc invoke-last` loads the newest archive entry into a fresh session as inherited context.

---

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

---

## Update

Pull the latest from `main`:

**macOS / Linux:**
```bash
git -C ~/.claude/skills/acc pull
```

**Windows (PowerShell):**
```powershell
git -C "$HOME\.claude\skills\acc" pull
```

---

## Uninstall

**macOS / Linux:**
```bash
rm -rf ~/.claude/skills/acc
```

**Windows (PowerShell):**
```powershell
Remove-Item -Recurse -Force "$HOME\.claude\skills\acc"
```

---

## Troubleshooting

**`/acc` doesn't appear in Claude Code.**
Confirm the file exists at the expected path:
- macOS/Linux: `ls ~/.claude/skills/acc/SKILL.md`
- Windows (PowerShell): `Get-ChildItem "$HOME\.claude\skills\acc\SKILL.md"`

Then restart Claude Code.

**Windows: helper scripts fail with `python3: command not found` or open the Microsoft Store.**
On Windows, invoke the scripts as `python new_acc.py …`, not `python3 …`. The `python3` alias often resolves to the Microsoft Store install shim, which fails silently. Either remove the shim from PATH or use the `python` launcher.

**`fatal: detected dubious ownership` when running `git` against the repo.**
This appears on filesystems that don't record ownership (FAT/exFAT, some external drives, network shares). Mark the directory safe:

```bash
git config --global --add safe.directory <absolute-path-to-repo>
```

Or, for a one-off invocation without touching global config:

```bash
git -c safe.directory=<absolute-path-to-repo> <command>
```

**ACC entries are landing in the wrong project.**
The scripts write to `./docs/acc/` relative to the **current working directory** at the moment the skill runs — not to a global location. If entries end up in the wrong place, check Claude Code's working directory.

---

## License

MIT. See `LICENSE`.
