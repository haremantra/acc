#!/usr/bin/env python3
"""Claude Code SessionStart hook: auto-load the latest ACC as inherited context.

Wire this into a project's .claude/settings.json so a fresh session inherits
the most recent ACC without anyone remembering to run `/acc invoke-last`
(Mode B, automated). See the README's "Auto-load on session start" section.

Behavior:
  * Finds the newest docs/acc/NNN-*.md (lexicographic; README.md and _*.md
    extractor outputs excluded).
  * With --global, the project archive still takes precedence; the
    cross-project archive (~/.claude/acc, or $ACC_GLOBAL_DIR) is consulted
    only when the project has no entries. A globally-sourced checkpoint is
    injected with a preamble naming its source project (stamped by
    new_acc.py --global) and framed as background context, not as work to
    continue — so a session in one project can't be misdirected into
    continuing another project's work.
  * If an entry is found, prints the SessionStart JSON envelope with its
    content in `hookSpecificOutput.additionalContext`, which Claude Code
    injects into the session context. Project-local paths are shown relative
    to the project so transcripts don't carry the machine layout.
  * If there's no archive/entry, prints nothing (no context injected) — no
    "starting fresh" noise on every project that doesn't use ACC.
  * Reads from the global archive are surfaced on stderr — louder when
    $ACC_GLOBAL_DIR points outside the home directory — so a redirected
    archive is visible rather than silent.

It is deliberately bulletproof: after argument parsing, any error results in
a clean exit 0 with no stdout, so a hook misfire can never block session
startup. (Unknown flags still exit 2 with argparse's usage message — the
flags live in settings.json, not in data, so a config typo should surface,
not vanish.) The cwd is taken from the hook's stdin payload (Claude Code
sends `{"cwd": ...}`), falling back to the process cwd; `--dir` overrides
both (used by tests).

Usage (manual / test):
    python acc_session_start.py --dir docs/acc
    python acc_session_start.py --global   # fall back to the cross-project archive
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Cap how much we inject; ACCs are tiny by design (<800 words), but guard
# against a hand-edited monster file blowing up the context window.
MAX_BYTES = 16_000

# new_acc.py --global stamps this line into global entries so a cross-project
# consumer can say where a checkpoint came from.
SOURCE_RE = re.compile(r"^\*\*Source project:\*\*\s*(.+?)\s*$", re.MULTILINE)


def global_dir() -> Path:
    """The cross-project archive: $ACC_GLOBAL_DIR if set, else ~/.claude/acc."""
    env = os.environ.get("ACC_GLOBAL_DIR")
    return Path(env) if env else Path.home() / ".claude" / "acc"


def find_latest(acc_dir: Path) -> Path | None:
    if not acc_dir.is_dir():
        return None
    candidates = sorted(
        p
        for p in acc_dir.glob("*.md")
        if p.name.lower() != "readme.md" and not p.name.startswith("_")
    )
    return candidates[-1] if candidates else None


def _cwd_from_stdin() -> str | None:
    """Claude Code passes a JSON payload on stdin including the project cwd."""
    if sys.stdin is None or sys.stdin.isatty():
        return None
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return None
    cwd = payload.get("cwd")
    return cwd if isinstance(cwd, str) else None


def _display_path(latest: Path, base: Path) -> str:
    """Relativize paths under `base` (the project) so transcripts don't carry
    usernames or machine layout; anything outside — e.g. the global archive —
    stays absolute, because relative would be ambiguous there."""
    try:
        return latest.relative_to(base).as_posix()
    except ValueError:
        return str(latest)


def _surface_global_read(gdir: Path) -> None:
    """Make a (possibly redirected) global-archive read visible on stderr."""
    suffix = " (set by $ACC_GLOBAL_DIR)" if "ACC_GLOBAL_DIR" in os.environ else ""
    print(f"acc_session_start: reading global archive {gdir}{suffix}", file=sys.stderr)
    try:
        gdir.relative_to(Path.home().resolve())
    except ValueError:
        print(
            f"acc_session_start: warning: {gdir} is outside your home directory — "
            "only trust this location if you pointed $ACC_GLOBAL_DIR there yourself",
            file=sys.stderr,
        )


def build_context(latest: Path, display: str, *, from_global: bool = False) -> str:
    body = latest.read_text(encoding="utf-8")
    # Look for the source stamp before truncation so a long entry can't hide it.
    source_match = SOURCE_RE.search(body) if from_global else None
    encoded = body.encode("utf-8")
    if len(encoded) > MAX_BYTES:
        # Slice by bytes (not characters) so the cap holds for non-ASCII;
        # errors="ignore" drops a trailing partial multibyte char cleanly.
        body = encoded[:MAX_BYTES].decode("utf-8", errors="ignore")
        body += "\n\n[...truncated; open the file for the full entry]"
    if from_global:
        produced_in = f"`{source_match.group(1)}`" if source_match else "an unspecified project"
        return (
            f"Inherited cross-project context, auto-loaded from the global ACC "
            f"archive ({display}) by the ACC SessionStart hook. This checkpoint "
            f"was produced in {produced_in}, which may not be the project you "
            f"are in now — treat it as background context, and only continue "
            f"its work if it clearly matches the current project. To reload "
            f"manually later, run `/acc invoke-last`.\n\n{body}"
        )
    return (
        f"Inherited context from a prior session, auto-loaded from "
        f"{display} by the ACC SessionStart hook. This is a "
        f"compressed, lossy checkpoint — continue the work from it rather than "
        f"replaying earlier conversation. To reload manually later, run "
        f"`/acc invoke-last`.\n\n{body}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SessionStart hook: load latest ACC.")
    where = parser.add_mutually_exclusive_group()
    where.add_argument(
        "--dir",
        default=None,
        help="Archive dir. Defaults to <cwd>/docs/acc (cwd from stdin or process).",
    )
    where.add_argument(
        "--global",
        dest="use_global",
        action="store_true",
        help="Fall back to the cross-project archive (~/.claude/acc, or "
        "$ACC_GLOBAL_DIR) when the project archive has no entries.",
    )
    args = parser.parse_args(argv)

    try:
        from_global = False
        if args.dir is not None:
            base = Path(os.getcwd()).resolve()
            latest = find_latest(Path(args.dir).resolve())
        else:
            base = Path(_cwd_from_stdin() or os.getcwd()).resolve()
            latest = find_latest(base / "docs" / "acc")
            if latest is None and args.use_global:
                gdir = global_dir().resolve()
                _surface_global_read(gdir)
                latest = find_latest(gdir)
                from_global = latest is not None

        if latest is None:
            return 0  # Silent: nothing to inherit.

        envelope = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": build_context(
                    latest, _display_path(latest, base), from_global=from_global
                ),
            }
        }
        print(json.dumps(envelope))
    except Exception:
        # Never let a hook failure block the session.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
