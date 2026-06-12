#!/usr/bin/env python3
"""Claude Code PreCompact hook: snapshot the raw transcript before compaction.

Compaction replaces a session's history with a machine-written summary. If a
checkpoint (`/acc` Mode A) hasn't been written by then, the full-fidelity
window is gone and any later checkpoint is a compression of that summary.
This hook fires in the gap between "compaction decided" and "history
rewritten" and does two things:

  * Tier 1 (always): copies the raw transcript (`transcript_path` from the
    hook's stdin payload) to `<cwd>/docs/acc/_snapshots/`, so a checkpoint
    can still be produced from the full window after compaction. Snapshots
    are pruned to the newest few, and a `.gitignore` is seeded (re-seeded
    whenever absent) so they are never committed — transcripts can contain
    secrets. The gitignore protects the git channel only: if the project
    tree is zipped, synced, or shared by other means, the snapshots travel
    with it. Point `--dest` somewhere outside the tree (e.g. under
    `~/.claude/`) if that matters for your project.
  * Tier 2 (auto-compaction only, unless --snapshot-only): prints a
    PreCompact JSON envelope whose `additionalContext` nudges the model to
    write the checkpoint now, while the window is still intact. Whether the
    harness surfaces PreCompact context before the summary pass is not
    contractual — Tier 1 carries the design; the nudge is best-effort.

Wire it into a project's `.claude/settings.json` (see
`assets/pre-compact-settings.json`): matcher `auto` runs both tiers,
matcher `manual` runs with --snapshot-only — when you typed `/compact`
yourself you don't need a nudge, just the insurance copy.

Mechanics worth knowing:

  * Snapshot names are `<UTCstamp>-<trigger>-<session8>-<NN>.jsonl` with a
    zero-padded counter in every name, so lexicographic order is
    chronological by construction even for same-second collisions.
  * The copy is atomic: data lands in a `.part` file first and is renamed
    into place, so a hook timeout mid-copy can never leave a truncated
    snapshot wearing a valid name.
  * Pruning deletes only files matching the naming contract above (plus
    stale `.part` leftovers) and tolerates per-file failures (e.g. Windows
    file locks) without giving up — and it runs after the Tier-2 envelope
    has been printed, so housekeeping trouble can't suppress the nudge.

Like the SessionStart hook, it is deliberately bulletproof: after argument
parsing, any error results in a clean exit 0 with no stdout, so a hook
misfire can never block compaction. (Unknown flags and invalid values still
exit 2 with argparse's usage message — flags live in settings.json, so a
config typo should surface, not vanish.) Both `transcript_path` and `cwd`
come from the harness's stdin payload — the same trust channel SessionStart
relies on.

Usage (manual / test):
    python acc_pre_compact.py --dest /tmp/snaps < payload.json
    python acc_pre_compact.py --snapshot-only < payload.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_KEEP = 5
SESSION_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9-]")

# The naming contract take_snapshot() writes and prune() trusts. Anything in
# the snapshot dir that doesn't match (user-parked files, foreign .jsonl) is
# never deleted and never counts against --keep.
SNAPSHOT_RE = re.compile(r"^\d{8}T\d{6}Z-(?:auto|manual|unknown)-[A-Za-z0-9-]+-\d{2,4}\.jsonl$")

# Ignore everything in the snapshot dir except the .gitignore itself, so a
# tracked docs/acc/ can never accidentally commit raw transcripts.
GITIGNORE_BODY = "*\n!.gitignore\n"

NUDGE = (
    "Auto-compaction is about to replace this session's history with a "
    "summary. Before continuing the task, write a session checkpoint per "
    "the /acc skill (Mode A: docs/acc/NNN-YYYY-MM-DD-topic.md, five "
    "sections, under 800 words) so the full-fidelity window is captured. "
    "The raw transcript was snapshotted to {display} in case the "
    "checkpoint must be reconstructed later."
)


def _payload_from_stdin() -> dict:
    """Claude Code passes a JSON payload on stdin (cwd, transcript_path, ...)."""
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _clean_trigger(raw: object) -> str:
    return raw if raw in ("auto", "manual") else "unknown"


def _clean_session_id(raw: object) -> str:
    if not isinstance(raw, str):
        return "session"
    cleaned = SESSION_ID_SAFE_RE.sub("", raw)[:8]
    return cleaned or "session"


def snapshot_stem(trigger: str, session_id: str, now: datetime) -> str:
    """`20260612T154233Z-auto-62a1011c` — take_snapshot appends `-NN.jsonl`.

    A naive `now` is treated as UTC (not reinterpreted as local time), so a
    caller passing `datetime.utcnow()` gets the stamp it expects.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{_clean_trigger(trigger)}-{_clean_session_id(session_id)}"


def ensure_gitignore(dest_dir: Path) -> None:
    """Seed `.gitignore` whenever absent; a user-modified file is left alone."""
    gitignore = dest_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(GITIGNORE_BODY, encoding="utf-8")


def take_snapshot(
    transcript: Path,
    dest_dir: Path,
    trigger: str,
    session_id: str,
    now: datetime | None = None,
) -> Path:
    """Copy the transcript into `dest_dir`, never overwriting an earlier copy.

    Every name carries a zero-padded counter (`-01`, `-02`, ...) so that
    same-second collisions still sort in creation order — prune's
    lexicographic ordering depends on it. The copy goes to a `.part` file
    first and is renamed into place (atomic on POSIX and Windows), so a
    kill mid-copy can't leave a truncated file under a valid name.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    ensure_gitignore(dest_dir)
    stem = snapshot_stem(trigger, session_id, now or datetime.now(timezone.utc))
    counter = 1
    target = dest_dir / f"{stem}-{counter:02d}.jsonl"
    while target.exists():
        counter += 1
        target = dest_dir / f"{stem}-{counter:02d}.jsonl"
    part = target.with_suffix(".part")
    shutil.copy2(transcript, part)
    os.replace(part, target)
    return target


def prune(dest_dir: Path, keep: int) -> list[Path]:
    """Delete all but the newest `keep` snapshots; returns what was removed.

    Only files matching the naming contract (`SNAPSHOT_RE`) are candidates —
    the `.gitignore` and anything a user parks here are never deleted and
    never displace a real snapshot from the keep window. Stale `.part`
    leftovers from a killed copy are swept too. Each deletion tolerates
    per-file failures (Windows locks, AV scans) so one stuck file can't
    abort the rest.
    """
    snapshots = sorted(p for p in dest_dir.glob("*.jsonl") if SNAPSHOT_RE.match(p.name))
    doomed = snapshots[:-keep] if keep > 0 else snapshots
    removed: list[Path] = []
    for path in [*doomed, *dest_dir.glob("*.part")]:
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            continue
    return removed


def _display_path(target: Path, base: Path) -> str:
    """Relativize under the project so transcripts don't carry machine layout."""
    try:
        return target.relative_to(base).as_posix()
    except ValueError:
        return str(target)


def _at_least_one(value: str) -> int:
    """argparse type for --keep: a config typo should surface, not vanish."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("--keep must be >= 1")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PreCompact hook: snapshot the transcript before compaction."
    )
    parser.add_argument(
        "--snapshot-only",
        action="store_true",
        help="Skip the checkpoint nudge; just copy the transcript (manual /compact).",
    )
    parser.add_argument(
        "--keep",
        type=_at_least_one,
        default=DEFAULT_KEEP,
        help=f"How many snapshots to retain, minimum 1 (default {DEFAULT_KEEP}).",
    )
    parser.add_argument(
        "--dest",
        default=None,
        help="Snapshot dir; relative paths are anchored to the payload cwd. "
        "Defaults to <cwd>/docs/acc/_snapshots.",
    )
    args = parser.parse_args(argv)

    try:
        payload = _payload_from_stdin()
        transcript_raw = payload.get("transcript_path")
        if not isinstance(transcript_raw, str):
            return 0  # Silent: nothing to snapshot.
        transcript = Path(transcript_raw)
        if not transcript.is_file():
            return 0

        cwd_raw = payload.get("cwd")
        base = Path(cwd_raw).resolve() if isinstance(cwd_raw, str) else Path.cwd()
        if args.dest:
            dest_dir = (base / args.dest).resolve()
        else:
            dest_dir = base / "docs" / "acc" / "_snapshots"

        trigger = _clean_trigger(payload.get("trigger"))
        target = take_snapshot(
            transcript, dest_dir, trigger, _clean_session_id(payload.get("session_id"))
        )
        display = _display_path(target, base)
        print(f"acc_pre_compact: snapshotted transcript to {display}", file=sys.stderr)

        # Nudge before housekeeping: a prune hiccup must not suppress Tier 2.
        if trigger == "auto" and not args.snapshot_only:
            envelope = {
                "hookSpecificOutput": {
                    "hookEventName": "PreCompact",
                    "additionalContext": NUDGE.format(display=display),
                }
            }
            print(json.dumps(envelope))

        try:
            prune(dest_dir, args.keep)
        except OSError:
            pass  # Housekeeping is best-effort; the snapshot already landed.
    except Exception:
        # Never let a hook failure block compaction.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
