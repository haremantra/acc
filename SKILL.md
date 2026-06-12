---
name: acc
description: Adaptive Context Compressor — bidirectional. Mode A (default): compresses chat history into a load-bearing summary; commit to docs/acc/NNN-…md for cross-session reuse. Mode B (invoke-last): loads the most recent ACC from docs/acc/ (or the global archive at ~/.claude/acc as fallback) into the current session as inherited context — call at session start to skip replaying prior conversation.
user-invocable: true
argument-hint: [optional focus area | "invoke-last" to load most recent ACC]
---

# ACC — Adaptive Context Compressor

You are compressing the current conversation into a minimal, high-signal context document. The goal is to reduce token consumption while preserving every fact needed to continue working without loss.

## Input

Optional focus area: **$ARGUMENTS**

If provided, weight the compression toward that area. If not, compress everything.

## Modes — branch on argument

This skill has **two modes**. Read the argument first and pick the mode:

- **If `$ARGUMENTS` is exactly `invoke-last` or `load-last` (case-insensitive, whitespace stripped) → run Mode B below.** Skip the entire Process section.
- **Otherwise → run Mode A (the Process section below).** The argument, if present, is the focus area for compression.

### Mode B — Invoke last ACC (consumer mode)

The user wants to load a prior ACC into the current session as inherited context. Do NOT produce a new ACC.

Steps:
1. **Locate the archive directory.** Check `docs/acc/` in the current working directory. If it doesn't exist or contains no ACC entries (nothing besides `README.md` and `_*.md`), but the global archive has entries (`~/.claude/acc`, or `$ACC_GLOBAL_DIR` if set), use the global archive instead — pass `--global` to the script in step 2. If neither has entries, report `No docs/acc/ archive found in current directory (and no global archive) — nothing to invoke` and stop. Suggest the user `cd` into the right project or reference a specific ACC path.
2. **Find the latest ACC.** From the project root, run `python "<skill-dir>/scripts/find_latest_acc.py"` (`python3` on macOS/Linux), where `<skill-dir>` is this skill's directory — see [Bundled resources](#bundled-resources). It globs `docs/acc/*.md`, excludes `README.md` and `_*.md` extractor outputs, sorts lexicographically, and prints the newest path; it exits non-zero with a message if the archive is missing or empty. (Add `--global` to read the cross-project archive — `~/.claude/acc`, or `$ACC_GLOBAL_DIR` if set — instead. If the script reports the project archive is empty and you haven't tried the global archive yet, rerun with `--global` before stopping.) **Fallback** (if you can't run the script): glob `docs/acc/*.md` yourself, skip `README.md` and `_*.md` files, and take the lexicographically highest filename — convention `NNN-YYYY-MM-DD-topic.md`, so highest `NNN` is most recent.
3. **Read the file** via the Read tool (full file, no offset/limit).
4. **Acknowledge** in one or two sentences: *"Loaded ACC NNN — [date] [focus from header]. Continuing from there."* Surface any unblocked next-actions or open questions worth flagging.
5. **Do NOT run Step 0 necessity check** — that gate is for production. Consumption is always cheap (the file is small by construction; that's the whole point).

If the user wants a *specific* ACC (not the latest), they should pass the path directly via Read or `cat`, not via this skill.

If multiple `docs/acc/` archives exist across nested directories (rare), only consider the one in or directly under the working directory.

After Mode B completes, stop. Do not produce new compression — that's Mode A.

## Process

### Step 0 — Necessity check (run before compressing)

ACC's only leverage is **inter-session**: it produces a portable artifact that lets a future thread skip replaying this one. Within the current session it adds tokens, not removes them.

**Apply the rubric in `references/necessity-check.md`** (read it now). If ≥4 of its criteria favor HANDOFF, **abort with "ACC not needed — HANDOFF covers it"** and tell the user why. Otherwise proceed to Step 1.

If the user explicitly invoked `/acc`, you may still produce one — but lead with the necessity finding so the user can decide whether to keep it. Don't silently produce a low-value artifact.

### Step 1 — Extract the five dimensions

Scan the full conversation and extract ONLY the following. Everything else is discarded.

**1. DECISIONS MADE (what was decided and why)**
```
- D: [decision] — because [one-line reason]
```
Only include decisions that affect future work. Skip exploratory dead ends unless they were explicitly ruled out (those become "rejected approaches").

**2. CURRENT STATE (what exists right now)**
```
- [artifact]: [status] — [one-line description]
```
Files created, tests passing, versions bumped, branches, uncommitted changes. Facts, not narrative.

**3. OPEN QUESTIONS / BLOCKERS**
```
- Q: [question or blocker] — affects [what downstream work]
```
Only unresolved items. If it was answered during the conversation, it goes in DECISIONS, not here.

**4. REJECTED APPROACHES (what was tried and why it failed)**
```
- X: [approach] — rejected because [reason]
```
These prevent re-exploring dead ends. Only include if the approach was seriously considered, not just mentioned.

**5. NEXT ACTIONS (what to do next, in order)**
```
1. [action] — [target file or artifact]
2. [action] — [target file or artifact]
```
Ordered by dependency. Each action should be specific enough to execute without re-reading the conversation.

### Step 2 — Compress to token budget

Target: **under 800 words total** across all five dimensions. If the conversation was short, the compression can be shorter. Never pad.

Rules:
- One line per item. No paragraphs.
- File paths are cited as `file:line` only when the line number matters for future work
- No recapping what tools were used or how — only WHAT was produced
- No emotional language, no "we explored", no "interestingly" — just facts
- Timestamps only if they affect sequencing decisions
- If a decision references a governing document, keep the citation (e.g., "per ICS-001 §4.2")

### Step 3 — Scaffold the file, then fill it

Create the output file by running, from the project root:

```
python "<skill-dir>/scripts/new_acc.py" --topic <slug> --focus "<focus area>"
```

(`python3` on macOS/Linux; `<skill-dir>` is this skill's directory — see [Bundled resources](#bundled-resources). Add `--date YYYY-MM-DD` only to override today; add `--dry-run` to print the path and next `NNN` without writing; add `--global` to write the cross-project archive — `~/.claude/acc`, or `$ACC_GLOBAL_DIR` if set — instead of `docs/acc/`.) The script computes the next zero-padded `NNN`, seeds `docs/acc/README.md` on first run, renders `assets/acc-template.md`, and writes `docs/acc/NNN-YYYY-MM-DD-topic.md`, printing the path.

Then **fill the five sections** in that file (the script scaffolds the skeleton only) and replace the `{{TOKENS_BEFORE}}` / `{{TOKENS_AFTER}}` placeholders with your estimates. The canonical format is `assets/acc-template.md`; its shape is:

```markdown
# Session Checkpoint — [date]
**Focus:** [focus area or "full session"]
**Token estimate before:** ~[estimate]k
**Token estimate after:** ~[estimate]k

## Decisions
- D: ...
## Current State
- ...
## Open Questions
- Q: ...
## Rejected Approaches
- X: ...
## Next Actions
1. ...
```

**Fallback** (if you can't run the script): write the file yourself in the `assets/acc-template.md` format, naming it `docs/acc/NNN-YYYY-MM-DD-topic.md` with the next `NNN`.

### Step 4 — Verify nothing load-bearing was dropped

After compression, scan for:
- Any file path referenced in NEXT ACTIONS that isn't mentioned in CURRENT STATE (missing context)
- Any decision that depends on an assumption not captured (hidden dependency)
- Any blocker that was resolved mid-conversation but not moved to DECISIONS

If found, add the missing item to the appropriate dimension.

## Rules

1. This is LOSSY compression — that's the point. Drop all exploratory chat, tool output, intermediate reasoning, and social exchange
2. Preserve exact version numbers, file paths, test counts, and branch names — these are the facts that prevent re-discovery
3. If HANDOFF.md exists and is current, reference it rather than duplicating: "See HANDOFF.md for full state"
4. The compressed output replaces the need to re-read the conversation — if someone couldn't continue working from the compression alone, it's incomplete
5. Never compress governing document citations (ADR-001A, ICS-001, REQ-004) — these are load-bearing references
6. **Don't run ACC on momentum.** If Step 0 says HANDOFF covers it, abort and surface the rubric finding to the user. Producing a low-leverage ACC trains the habit of running it everywhere — which dilutes the archive and makes the high-value entries harder to find later

## Gotchas

Highest-signal failure points, accreted from real runs. Read before invoking — most apply to Mode A.

- **Don't run ACC on momentum** (the most common misuse). If Step 0's necessity check favors HANDOFF, abort and surface the finding. A low-leverage ACC dilutes the archive and buries the high-value entries — see Rule 6 and `references/necessity-check.md`.
- **Scripts write to the *current working directory*, not a global path.** Entries land in `./docs/acc/` of wherever Claude Code is running. If they show up in the wrong project, check the working directory before re-running — don't move files by hand. (Prefer one shared archive across projects? Pass `--global` to write/read `~/.claude/acc` instead, overridable with `$ACC_GLOBAL_DIR`.)
- **Windows: invoke scripts as `python`, not `python3`.** The `python3` alias usually resolves to the Microsoft Store shim, which fails silently or opens the Store. Use `python "<skill-dir>/scripts/new_acc.py" …`.
- **Never rename archive files out of `NNN-YYYY-MM-DD-topic` order.** Latest-ACC selection is a lexicographic sort on filename; off-convention names break `find_latest_acc.py` and Mode B. `README.md` is excluded by design — don't give it a number.
- **`git` "dubious ownership" on FAT/exFAT or network shares.** Mark the repo safe once: `git config --global --add safe.directory <path>` (or `git -c safe.directory=<path> …` for a single command).
- **Every script-backed step has a manual fallback — use it, don't abort.** If Python can't run: Mode B → glob `docs/acc/*.md`, skip `README.md` and `_*.md` files, take the lexicographically highest; Mode A → write the `assets/acc-template.md` shape yourself as `docs/acc/NNN-YYYY-MM-DD-topic.md` with the next `NNN`.

The README's Troubleshooting section carries longer-form fixes for the install/path issues above.

## Bundled resources

This skill ships with helper files in its own directory (`<skill-dir>` = the folder containing this `SKILL.md`; Claude Code makes this path available when the skill runs). Only one install is active at a time, so substitute that install's absolute path.

| File | Used in | Purpose |
|---|---|---|
| `scripts/new_acc.py` | Step 3 (Mode A) | Compute next `NNN`, seed archive README, render template, write `docs/acc/NNN-YYYY-MM-DD-topic.md` |
| `scripts/find_latest_acc.py` | Mode B step 2 | Print the newest ACC path (glob + lexicographic sort, README excluded); non-zero if archive empty/missing |
| `scripts/list_acc.py` | (browsing) | Print the archive as a dated, focus-labeled index; `--markdown` for a README table |
| `scripts/acc_session_start.py` | (Mode B, automated) | SessionStart hook that auto-loads the latest ACC into a fresh session; exit-0-safe |
| `assets/acc-template.md` | Step 3 | Canonical output skeleton with `{{DATE}}` / `{{FOCUS}}` / `{{TOKENS_*}}` tokens |
| `assets/docs-acc-readme.md` | (by `new_acc.py`) | README seed dropped into `docs/acc/` on first run |
| `assets/global-acc-readme.md` | (by `new_acc.py --global`) | README seed dropped into the global archive on first run |
| `assets/session-start-settings.json` | (setup) | Example `.claude/settings.json` wiring the SessionStart hook |
| `references/necessity-check.md` | Step 0 | The 9-criterion ACC-vs-HANDOFF rubric; read on demand |
| `references/example-acc.md` | Step 1–2 | Good vs bad worked example; read to calibrate the quality bar |

Run scripts with `python` (Windows) or `python3` (macOS/Linux). Scripts write `docs/acc/` relative to the **current working directory** (the project), and locate their own `assets/` relative to themselves — so they work from either install location. Every script-dependent step above has a manual fallback if execution isn't available.
