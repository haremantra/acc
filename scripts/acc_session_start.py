#!/usr/bin/env python3
"""Claude Code SessionStart hook: auto-load the latest ACC as inherited context.

Wire this into a project's .claude/settings.json so a fresh session inherits
the most recent ACC without anyone remembering to run `/acc invoke-last`
(Mode B, automated). See the README's "Auto-load on session start" section.

Behavior:
  * Finds the newest docs/acc/NNN-*.md (lexicographic, README.md excluded).
  * If found, prints the SessionStart JSON envelope with the entry's content
    in `hookSpecificOutput.additionalContext`, which Claude Code injects into
    the session context.
  * If there's no archive/entry, prints nothing (no context injected) — no
    "starting fresh" noise on every project that doesn't use ACC.

It is deliberately bulletproof: any error results in a clean exit 0 with no
output, so a hook misfire can never block session startup. The cwd is taken
from the hook's stdin payload (Claude Code sends `{"cwd": ...}`), falling
back to the process cwd; `--dir` overrides both (used by tests).

Usage (manual / test):
    python acc_session_start.py --dir docs/acc
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Cap how much we inject; ACCs are tiny by design (<800 words), but guard
# against a hand-edited monster file blowing up the context window.
MAX_BYTES = 16_000


def find_latest(acc_dir: Path) -> Path | None:
    if not acc_dir.is_dir():
        return None
    candidates = sorted(p for p in acc_dir.glob("*.md") if p.name.lower() != "readme.md")
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


def build_context(latest: Path) -> str:
    body = latest.read_text(encoding="utf-8")
    encoded = body.encode("utf-8")
    if len(encoded) > MAX_BYTES:
        # Slice by bytes (not characters) so the cap holds for non-ASCII;
        # errors="ignore" drops a trailing partial multibyte char cleanly.
        body = encoded[:MAX_BYTES].decode("utf-8", errors="ignore")
        body += "\n\n[...truncated; open the file for the full entry]"
    return (
        f"Inherited context from a prior session, auto-loaded from "
        f"docs/acc/{latest.name} by the ACC SessionStart hook. This is a "
        f"compressed, lossy checkpoint — continue the work from it rather than "
        f"replaying earlier conversation. To reload manually later, run "
        f"`/acc invoke-last`.\n\n{body}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SessionStart hook: load latest ACC.")
    parser.add_argument(
        "--dir",
        default=None,
        help="Archive dir. Defaults to <cwd>/docs/acc (cwd from stdin or process).",
    )
    args = parser.parse_args(argv)

    try:
        if args.dir is not None:
            acc_dir = Path(args.dir)
        else:
            base = _cwd_from_stdin() or os.getcwd()
            acc_dir = Path(base) / "docs" / "acc"

        latest = find_latest(acc_dir.resolve())
        if latest is None:
            return 0  # Silent: nothing to inherit.

        envelope = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": build_context(latest),
            }
        }
        print(json.dumps(envelope))
    except Exception:
        # Never let a hook failure block the session.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
