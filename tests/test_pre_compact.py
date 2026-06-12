#!/usr/bin/env python3
"""Tests for the PreCompact hook script (`acc_pre_compact.py`).

Stdlib-only (unittest), same as the rest of the suite:

    python -m unittest discover -s tests

The hook's contract has three load-bearing pieces these tests pin:
the snapshot is a faithful, atomic, never-overwriting copy whose names sort
in creation order (the prune ordering depends on it), with a seeded
`.gitignore` (raw transcripts must never be committable); pruning deletes
only contract-named snapshots, keeps the newest N, and never suppresses the
Tier-2 envelope; and the exit-0-safe behavior — nudge on `auto` only,
silence on malformed input — so a misfire can never block compaction.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"


def _load(name: str):
    """Import a script by path (the dir name `scripts` isn't a package)."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pre_compact = _load("acc_pre_compact")

NOW = datetime(2026, 6, 12, 15, 42, 33, tzinfo=timezone.utc)


class SnapshotStemTests(unittest.TestCase):
    def test_format_is_stamp_trigger_session(self) -> None:
        self.assertEqual(
            pre_compact.snapshot_stem("auto", "62a1011c-086e", NOW),
            "20260612T154233Z-auto-62a1011c",
        )

    def test_naive_datetime_is_treated_as_utc(self) -> None:
        # A naive datetime must not be reinterpreted as local time — a
        # shifted stamp would break chronological ordering against stamps
        # from the aware default path.
        naive = datetime(2026, 6, 12, 15, 42, 33)
        self.assertEqual(
            pre_compact.snapshot_stem("auto", "abc", naive),
            "20260612T154233Z-auto-abc",
        )

    def test_unknown_trigger_is_normalized(self) -> None:
        self.assertEqual(
            pre_compact.snapshot_stem("../evil", "abc", NOW),
            "20260612T154233Z-unknown-abc",
        )

    def test_session_id_is_sanitized_and_capped(self) -> None:
        # Unsafe chars stripped, then capped at 8.
        self.assertEqual(
            pre_compact.snapshot_stem("manual", "a/b\\c:d*e?f|g<h>i", NOW),
            "20260612T154233Z-manual-abcdefgh",
        )

    def test_non_string_session_id_falls_back(self) -> None:
        self.assertTrue(pre_compact.snapshot_stem("auto", None, NOW).endswith("-auto-session"))

    def test_lexicographic_order_is_chronological(self) -> None:
        earlier = pre_compact.snapshot_stem("auto", "s", NOW)
        later = pre_compact.snapshot_stem(
            "auto", "s", datetime(2026, 6, 12, 15, 42, 34, tzinfo=timezone.utc)
        )
        self.assertLess(earlier, later)


class TakeSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.transcript = self.tmp / "transcript.jsonl"
        self.transcript.write_text('{"turn": 1}\n', encoding="utf-8")
        self.dest = self.tmp / "snaps"

    def test_copies_content_and_creates_dirs(self) -> None:
        target = pre_compact.take_snapshot(self.transcript, self.dest, "auto", "abc", now=NOW)
        self.assertEqual(target.read_text(encoding="utf-8"), '{"turn": 1}\n')
        self.assertEqual(target.parent, self.dest)

    def test_name_matches_the_prune_contract(self) -> None:
        # If the writer and the prune filter ever drift apart, snapshots
        # become unprunable (or worse, invisible to retention).
        target = pre_compact.take_snapshot(self.transcript, self.dest, "auto", "abc", now=NOW)
        self.assertEqual(target.name, "20260612T154233Z-auto-abc-01.jsonl")
        self.assertRegex(target.name, pre_compact.SNAPSHOT_RE)

    def test_no_part_file_left_behind(self) -> None:
        pre_compact.take_snapshot(self.transcript, self.dest, "auto", "abc", now=NOW)
        self.assertEqual(list(self.dest.glob("*.part")), [])

    def test_seeds_gitignore(self) -> None:
        pre_compact.take_snapshot(self.transcript, self.dest, "auto", "abc", now=NOW)
        gitignore = self.dest / ".gitignore"
        self.assertEqual(gitignore.read_text(encoding="utf-8"), "*\n!.gitignore\n")

    def test_user_modified_gitignore_untouched(self) -> None:
        self.dest.mkdir(parents=True)
        (self.dest / ".gitignore").write_text("# mine\n", encoding="utf-8")
        pre_compact.take_snapshot(self.transcript, self.dest, "auto", "abc", now=NOW)
        self.assertEqual((self.dest / ".gitignore").read_text(encoding="utf-8"), "# mine\n")

    def test_never_overwrites_and_collisions_sort_in_creation_order(self) -> None:
        first = pre_compact.take_snapshot(self.transcript, self.dest, "auto", "abc", now=NOW)
        self.transcript.write_text('{"turn": 2}\n', encoding="utf-8")
        second = pre_compact.take_snapshot(self.transcript, self.dest, "auto", "abc", now=NOW)
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_text(encoding="utf-8"), '{"turn": 1}\n')
        self.assertEqual(second.read_text(encoding="utf-8"), '{"turn": 2}\n')
        # Load-bearing for prune: the newer same-second copy must sort AFTER
        # the older one, or retention deletes the wrong file.
        self.assertLess(first.name, second.name)
        self.assertRegex(second.name, pre_compact.SNAPSHOT_RE)


class PruneTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _seed(self, *names: str) -> None:
        for name in names:
            (self.dir / name).write_text("x\n", encoding="utf-8")

    def test_keeps_newest_n(self) -> None:
        self._seed(
            "20260601T000000Z-auto-a-01.jsonl",
            "20260602T000000Z-auto-a-01.jsonl",
            "20260603T000000Z-auto-a-01.jsonl",
        )
        removed = pre_compact.prune(self.dir, keep=2)
        self.assertEqual([p.name for p in removed], ["20260601T000000Z-auto-a-01.jsonl"])
        survivors = sorted(p.name for p in self.dir.glob("*.jsonl"))
        self.assertEqual(
            survivors,
            ["20260602T000000Z-auto-a-01.jsonl", "20260603T000000Z-auto-a-01.jsonl"],
        )

    def test_same_second_collision_prunes_the_older_copy(self) -> None:
        # Regression: with a non-sorting collision suffix, retention would
        # delete the NEWER copy and keep the stale one.
        self._seed(
            "20260601T000000Z-auto-a-01.jsonl",
            "20260601T000000Z-auto-a-02.jsonl",
        )
        pre_compact.prune(self.dir, keep=1)
        survivors = [p.name for p in self.dir.glob("*.jsonl")]
        self.assertEqual(survivors, ["20260601T000000Z-auto-a-02.jsonl"])

    def test_under_limit_removes_nothing(self) -> None:
        self._seed("20260601T000000Z-auto-a-01.jsonl")
        self.assertEqual(pre_compact.prune(self.dir, keep=5), [])

    def test_only_contract_named_files_are_candidates(self) -> None:
        # A user-parked .jsonl must neither be deleted nor displace a real
        # snapshot from the keep window.
        self._seed(
            "20260601T000000Z-auto-a-01.jsonl",
            "20260602T000000Z-auto-a-01.jsonl",
            "notes.jsonl",
        )
        (self.dir / ".gitignore").write_text("*\n", encoding="utf-8")
        (self.dir / "keep.md").write_text("keep me\n", encoding="utf-8")
        pre_compact.prune(self.dir, keep=2)
        names = sorted(p.name for p in self.dir.iterdir())
        self.assertEqual(
            names,
            [
                ".gitignore",
                "20260601T000000Z-auto-a-01.jsonl",
                "20260602T000000Z-auto-a-01.jsonl",
                "keep.md",
                "notes.jsonl",
            ],
        )

    def test_stale_part_files_are_swept(self) -> None:
        self._seed("20260601T000000Z-auto-a-01.jsonl")
        (self.dir / "20260601T000000Z-auto-a-02.part").write_text("trunc", encoding="utf-8")
        pre_compact.prune(self.dir, keep=5)
        self.assertEqual(list(self.dir.glob("*.part")), [])
        self.assertTrue((self.dir / "20260601T000000Z-auto-a-01.jsonl").exists())

    def test_a_stuck_file_does_not_abort_the_rest(self) -> None:
        self._seed(
            "20260601T000000Z-auto-a-01.jsonl",
            "20260602T000000Z-auto-a-01.jsonl",
            "20260603T000000Z-auto-a-01.jsonl",
        )
        real_unlink = Path.unlink

        def flaky_unlink(self: Path, *args: object, **kwargs: object) -> None:
            if self.name.startswith("20260601"):
                raise PermissionError("locked")
            real_unlink(self, *args, **kwargs)

        with mock.patch.object(Path, "unlink", flaky_unlink):
            removed = pre_compact.prune(self.dir, keep=1)
        # The locked file survives, but the other doomed file still went.
        self.assertEqual([p.name for p in removed], ["20260602T000000Z-auto-a-01.jsonl"])
        self.assertTrue((self.dir / "20260601T000000Z-auto-a-01.jsonl").exists())


class MainTests(unittest.TestCase):
    """End-to-end through main() with a fabricated harness payload."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.transcript = self.tmp / "session.jsonl"
        self.transcript.write_text('{"role": "user"}\n', encoding="utf-8")

    def _run(self, payload: object, argv: list[str] | None = None) -> tuple[int, str, str]:
        stdin = StringIO(payload if isinstance(payload, str) else json.dumps(payload))
        out, err = StringIO(), StringIO()
        with mock.patch.object(pre_compact.sys, "stdin", stdin):
            with redirect_stdout(out), redirect_stderr(err):
                rc = pre_compact.main(argv or [])
        return rc, out.getvalue(), err.getvalue()

    def _payload(self, **overrides: object) -> dict:
        payload: dict[str, object] = {
            "session_id": "62a1011c-086e-4ac3",
            "transcript_path": str(self.transcript),
            "cwd": str(self.tmp),
            "hook_event_name": "PreCompact",
            "trigger": "auto",
        }
        payload.update(overrides)
        return payload

    def test_auto_trigger_snapshots_and_nudges(self) -> None:
        rc, out, err = self._run(self._payload())
        self.assertEqual(rc, 0)
        snaps = list((self.tmp / "docs" / "acc" / "_snapshots").glob("*.jsonl"))
        self.assertEqual(len(snaps), 1)
        envelope = json.loads(out)
        self.assertEqual(envelope["hookSpecificOutput"]["hookEventName"], "PreCompact")
        context = envelope["hookSpecificOutput"]["additionalContext"]
        self.assertIn("docs/acc/_snapshots/", context)
        self.assertIn("/acc", context)
        self.assertIn("snapshotted transcript", err)
        # stderr carries the relative display path, not the machine layout.
        self.assertNotIn(str(self.tmp), err)

    def test_snapshot_only_suppresses_nudge(self) -> None:
        rc, out, _ = self._run(self._payload(trigger="manual"), ["--snapshot-only"])
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        snaps = list((self.tmp / "docs" / "acc" / "_snapshots").glob("*.jsonl"))
        self.assertEqual(len(snaps), 1)
        self.assertIn("-manual-", snaps[0].name)

    def test_manual_trigger_without_flag_also_stays_silent(self) -> None:
        # The nudge is gated on trigger == "auto", not only on the flag.
        rc, out, _ = self._run(self._payload(trigger="manual"))
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_missing_transcript_is_silent_success(self) -> None:
        rc, out, _ = self._run(self._payload(transcript_path=str(self.tmp / "gone.jsonl")))
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertFalse((self.tmp / "docs").exists())

    def test_no_transcript_field_is_silent_success(self) -> None:
        rc, out, _ = self._run({"cwd": str(self.tmp), "trigger": "auto"})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_malformed_stdin_is_silent_success(self) -> None:
        rc, out, _ = self._run("{not json")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_prune_failure_does_not_suppress_the_nudge(self) -> None:
        # Housekeeping trouble (Windows file locks, AV scans) must not
        # disable Tier 2: the envelope prints before pruning runs.
        with mock.patch.object(pre_compact, "prune", side_effect=OSError("locked")):
            rc, out, err = self._run(self._payload())
        self.assertEqual(rc, 0)
        envelope = json.loads(out)
        self.assertEqual(envelope["hookSpecificOutput"]["hookEventName"], "PreCompact")
        self.assertIn("snapshotted transcript", err)

    def test_dest_override_wins_over_cwd(self) -> None:
        dest = self.tmp / "elsewhere"
        rc, _, _ = self._run(self._payload(), ["--dest", str(dest)])
        self.assertEqual(rc, 0)
        self.assertEqual(len(list(dest.glob("*.jsonl"))), 1)
        self.assertFalse((self.tmp / "docs").exists())

    def test_relative_dest_is_anchored_to_payload_cwd(self) -> None:
        rc, _, _ = self._run(self._payload(), ["--dest", "snaps-here"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(list((self.tmp / "snaps-here").glob("*.jsonl"))), 1)

    def test_keep_is_enforced_through_main(self) -> None:
        dest = self.tmp / "snaps"
        dest.mkdir()
        # Epoch-dated seeds sort before any real clock, so the test can't
        # rot as wall time advances.
        for stamp in ("19700101T000000Z", "19700102T000000Z", "19700103T000000Z"):
            (dest / f"{stamp}-auto-old-01.jsonl").write_text("x\n", encoding="utf-8")
        rc, _, _ = self._run(self._payload(), ["--dest", str(dest), "--keep", "2"])
        self.assertEqual(rc, 0)
        survivors = sorted(p.name for p in dest.glob("*.jsonl"))
        self.assertEqual(len(survivors), 2)
        # The just-written snapshot is the newest and must survive.
        self.assertTrue(survivors[-1].endswith("-auto-62a1011c-01.jsonl"))

    def test_keep_zero_is_rejected_at_parse_time(self) -> None:
        # keep<=0 would delete the snapshot just taken — a config typo that
        # must surface (exit 2), not silently self-destruct the insurance.
        for value in ("0", "-1"):
            with self.assertRaises(SystemExit) as ctx:
                with redirect_stderr(StringIO()):
                    pre_compact.main(["--keep", value])
            self.assertEqual(ctx.exception.code, 2)

    def test_unknown_flag_exits_2(self) -> None:
        # Config typos in settings.json should surface, not vanish.
        with self.assertRaises(SystemExit) as ctx:
            with redirect_stderr(StringIO()):
                pre_compact.main(["--no-such-flag"])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
