#!/usr/bin/env python3
"""Tests for the usability helpers: list_acc.py and the SessionStart hook.

Stdlib-only, same as the rest of the suite:

    python -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.util
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


list_acc = _load("list_acc")
acc_session_start = _load("acc_session_start")


def _entry(directory: Path, name: str, focus: str | None = None) -> Path:
    p = directory / name
    header = f"# Session Checkpoint\n**Focus:** {focus}\n" if focus else "# no header\n"
    p.write_text(header, encoding="utf-8")
    return p


class ListAccParseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_missing_dir_returns_empty(self) -> None:
        self.assertEqual(list_acc.parse_entries(self.dir / "nope"), [])

    def test_newest_first_and_excludes_readme(self) -> None:
        _entry(self.dir, "001-2026-01-01-alpha.md", "alpha focus")
        _entry(self.dir, "002-2026-02-01-beta.md", "beta focus")
        _entry(self.dir, "README.md")
        entries = list_acc.parse_entries(self.dir)
        self.assertEqual([e.seq for e in entries], ["002", "001"])

    def test_ignores_off_convention_names(self) -> None:
        _entry(self.dir, "notes.md", "x")
        _entry(self.dir, "003-2026-01-01-c.md", "c focus")
        entries = list_acc.parse_entries(self.dir)
        self.assertEqual([e.seq for e in entries], ["003"])

    def test_ignores_extractor_outputs(self) -> None:
        _entry(self.dir, "_ledger.md", "x")
        _entry(self.dir, "_backlog.md", "y")
        _entry(self.dir, "004-2026-01-01-d.md", "d focus")
        entries = list_acc.parse_entries(self.dir)
        self.assertEqual([e.seq for e in entries], ["004"])

    def test_focus_parsed_from_header(self) -> None:
        _entry(self.dir, "001-2026-01-01-alpha.md", "the auth layer")
        self.assertEqual(list_acc.parse_entries(self.dir)[0].focus, "the auth layer")

    def test_focus_falls_back_to_slug_when_missing(self) -> None:
        _entry(self.dir, "001-2026-01-01-auth-rewrite.md")  # no Focus header
        self.assertEqual(list_acc.parse_entries(self.dir)[0].focus, "auth-rewrite")

    def test_focus_ignores_unrendered_placeholder(self) -> None:
        _entry(self.dir, "001-2026-01-01-auth-rewrite.md", "{{FOCUS}}")
        self.assertEqual(list_acc.parse_entries(self.dir)[0].focus, "auth-rewrite")


class ListAccRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        _entry(self.dir, "001-2026-01-01-alpha.md", "alpha focus")

    def _run(self, *args: str) -> tuple[int, str]:
        buf = StringIO()
        with redirect_stdout(buf):
            rc = list_acc.main(["--dir", str(self.dir), *args])
        return rc, buf.getvalue()

    def test_text_table(self) -> None:
        rc, out = self._run()
        self.assertEqual(rc, 0)
        self.assertIn("ACC", out)
        self.assertIn("alpha focus", out)
        self.assertIn("001-2026-01-01-alpha.md", out)

    def test_markdown_table(self) -> None:
        rc, out = self._run("--markdown")
        self.assertEqual(rc, 0)
        self.assertIn("| ACC | Date | Focus | File |", out)
        self.assertIn("[`001-2026-01-01-alpha.md`](001-2026-01-01-alpha.md)", out)

    def test_missing_dir_exit_1(self) -> None:
        rc = list_acc.main(["--dir", str(self.dir / "nope")])
        self.assertEqual(rc, 1)

    def test_empty_dir_exit_1(self) -> None:
        with TemporaryDirectory() as empty:
            self.assertEqual(list_acc.main(["--dir", empty]), 1)


class SessionStartHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _run(self, *args: str) -> tuple[int, str]:
        buf = StringIO()
        with redirect_stdout(buf):
            rc = acc_session_start.main(["--dir", str(self.dir), *args])
        return rc, buf.getvalue()

    def test_find_latest_excludes_readme(self) -> None:
        _entry(self.dir, "001-2026-01-01-alpha.md", "a")
        _entry(self.dir, "README.md")
        latest = acc_session_start.find_latest(self.dir)
        self.assertEqual(latest.name, "001-2026-01-01-alpha.md")

    def test_find_latest_excludes_extractor_outputs(self) -> None:
        # In a project where /acc-extract has run, _ledger.md sorts after
        # NNN-*.md; the hook must inject the newest checkpoint, not the index.
        _entry(self.dir, "001-2026-01-01-alpha.md", "a")
        _entry(self.dir, "_ledger.md", "decision log")
        latest = acc_session_start.find_latest(self.dir)
        self.assertEqual(latest.name, "001-2026-01-01-alpha.md")

    def test_archive_with_only_extractor_outputs_is_silent(self) -> None:
        _entry(self.dir, "_ledger.md", "decision log")
        rc, out = self._run()
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "")

    def test_no_archive_is_silent_exit_0(self) -> None:
        rc, out = self._run()  # empty dir
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "")

    def test_missing_dir_is_silent_exit_0(self) -> None:
        buf = StringIO()
        with redirect_stdout(buf):
            rc = acc_session_start.main(["--dir", str(self.dir / "nope")])
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue().strip(), "")

    def test_emits_sessionstart_envelope_with_content(self) -> None:
        _entry(self.dir, "001-2026-01-01-alpha.md", "the auth layer")
        rc, out = self._run()
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        hso = payload["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "SessionStart")
        ctx = hso["additionalContext"]
        self.assertIn("001-2026-01-01-alpha.md", ctx)
        self.assertIn("the auth layer", ctx)
        self.assertIn("/acc invoke-last", ctx)

    def test_picks_newest_entry(self) -> None:
        _entry(self.dir, "001-2026-01-01-alpha.md", "old")
        _entry(self.dir, "002-2026-02-01-beta.md", "new")
        _, out = self._run()
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("002-2026-02-01-beta.md", ctx)
        self.assertNotIn("001-2026-01-01-alpha.md", ctx)

    def test_large_entry_is_truncated(self) -> None:
        big = "x" * (acc_session_start.MAX_BYTES + 500)
        (self.dir / "001-2026-01-01-alpha.md").write_text(big, encoding="utf-8")
        _, out = self._run()
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("truncated", ctx)

    def test_truncation_cap_holds_for_non_ascii(self) -> None:
        # 4-byte chars: a char-based slice would overshoot the byte cap.
        big = "\U0001f600" * (acc_session_start.MAX_BYTES // 2)
        (self.dir / "001-2026-01-01-alpha.md").write_text(big, encoding="utf-8")
        _, out = self._run()
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("truncated", ctx)
        body = ctx.split("\n\n", 1)[1]
        self.assertLessEqual(
            len(body.encode("utf-8")),
            acc_session_start.MAX_BYTES + 100,  # +100 for the truncation notice
        )


class GlobalArchiveUsabilityTests(unittest.TestCase):
    """--global support in list_acc and the SessionStart hook."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        root = Path(self._tmp.name)
        self.global_dir = root / "global-acc"
        self.global_dir.mkdir(parents=True)
        # A project root with no docs/acc, so hook tests exercise the global
        # fallback regardless of what the test runner's real cwd contains.
        self.project_root = root / "project"
        self.project_root.mkdir()
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"ACC_GLOBAL_DIR": str(self.global_dir)})
        patcher.start()
        self.addCleanup(patcher.stop)
        cwd_patcher = mock.patch.object(
            acc_session_start, "_cwd_from_stdin", return_value=str(self.project_root)
        )
        cwd_patcher.start()
        self.addCleanup(cwd_patcher.stop)
        _entry(self.global_dir, "001-2026-01-01-alpha.md", "cross-project focus")

    def test_list_acc_global(self) -> None:
        buf = StringIO()
        with redirect_stdout(buf):
            rc = list_acc.main(["--global"])
        self.assertEqual(rc, 0)
        self.assertIn("cross-project focus", buf.getvalue())

    def test_session_start_global_falls_back_when_project_has_no_archive(self) -> None:
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = acc_session_start.main(["--global"])
        self.assertEqual(rc, 0)
        ctx = json.loads(out.getvalue())["hookSpecificOutput"]["additionalContext"]
        self.assertIn("001-2026-01-01-alpha.md", ctx)
        self.assertIn("reading global archive", err.getvalue())

    def test_session_start_dir_and_global_mutually_exclusive(self) -> None:
        err = StringIO()
        with self.assertRaises(SystemExit) as ctx, redirect_stderr(err):
            acc_session_start.main(["--dir", str(self.global_dir), "--global"])
        self.assertEqual(ctx.exception.code, 2)


class GlobalHookPrecedenceTests(unittest.TestCase):
    """Issue #6: with --global the project archive wins; the global archive is
    a fallback, and globally-sourced checkpoints are labeled, not directive."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.project_root = root / "project"
        self.project_acc = self.project_root / "docs" / "acc"
        self.project_acc.mkdir(parents=True)
        self.global_dir = root / "global-acc"
        self.global_dir.mkdir()
        patcher = mock.patch.dict(os.environ, {"ACC_GLOBAL_DIR": str(self.global_dir)})
        patcher.start()
        self.addCleanup(patcher.stop)
        cwd_patcher = mock.patch.object(
            acc_session_start, "_cwd_from_stdin", return_value=str(self.project_root)
        )
        cwd_patcher.start()
        self.addCleanup(cwd_patcher.stop)

    def _run_hook(self) -> tuple[int, str, str]:
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = acc_session_start.main(["--global"])
        return rc, out.getvalue(), err.getvalue()

    def test_project_archive_takes_precedence(self) -> None:
        _entry(self.project_acc, "001-2026-01-01-local.md", "local focus")
        _entry(self.global_dir, "009-2026-05-01-foreign.md", "foreign focus")
        rc, out, err = self._run_hook()
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("001-2026-01-01-local.md", ctx)
        self.assertNotIn("foreign", ctx)
        self.assertEqual(err, "")  # the global archive was never read

    def test_project_local_path_is_relativized(self) -> None:
        _entry(self.project_acc, "001-2026-01-01-local.md", "local focus")
        _, out, _ = self._run_hook()
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("docs/acc/001-2026-01-01-local.md", ctx)
        self.assertNotIn(str(self.project_root), ctx)

    def test_global_fallback_uses_soft_labeled_preamble(self) -> None:
        entry = _entry(self.global_dir, "001-2026-01-01-foreign.md", "foreign focus")
        entry.write_text(
            "# Session Checkpoint — 2026-01-01\n"
            "**Focus:** foreign focus\n"
            "**Source project:** /home/someone/other-project\n",
            encoding="utf-8",
        )
        rc, out, err = self._run_hook()
        self.assertEqual(rc, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Inherited cross-project context", ctx)
        self.assertIn("`/home/someone/other-project`", ctx)
        self.assertIn("background context", ctx)
        self.assertNotIn("continue the work from it", ctx)
        self.assertIn("reading global archive", err)

    def test_global_fallback_without_stamp_says_unspecified(self) -> None:
        _entry(self.global_dir, "001-2026-01-01-foreign.md", "foreign focus")
        _, out, _ = self._run_hook()
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("an unspecified project", ctx)

    def test_no_archive_anywhere_is_silent_on_stdout(self) -> None:
        rc, out, err = self._run_hook()
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "")
        # The (empty) global archive was still consulted; that read is surfaced.
        self.assertIn("reading global archive", err)


class GlobalDirSurfacingTests(unittest.TestCase):
    """Issue #7: global-archive reads are visible on stderr, and an
    out-of-home $ACC_GLOBAL_DIR redirection warns loudly."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_env_override_is_named_in_stderr(self) -> None:
        gdir = (self.root / "global-acc").resolve()
        err = StringIO()
        with mock.patch.dict(os.environ, {"ACC_GLOBAL_DIR": str(gdir)}), redirect_stderr(err):
            acc_session_start._surface_global_read(gdir)
        self.assertIn("reading global archive", err.getvalue())
        self.assertIn("set by $ACC_GLOBAL_DIR", err.getvalue())

    def test_outside_home_warns(self) -> None:
        fake_home = self.root / "home"
        fake_home.mkdir()
        gdir = (self.root / "elsewhere").resolve()
        err = StringIO()
        with mock.patch.object(Path, "home", return_value=fake_home), redirect_stderr(err):
            acc_session_start._surface_global_read(gdir)
        self.assertIn("outside your home directory", err.getvalue())

    def test_under_home_does_not_warn(self) -> None:
        fake_home = self.root / "home"
        gdir = (fake_home / ".claude" / "acc").resolve()
        err = StringIO()
        with mock.patch.object(Path, "home", return_value=fake_home), redirect_stderr(err):
            acc_session_start._surface_global_read(gdir)
        self.assertIn("reading global archive", err.getvalue())
        self.assertNotIn("outside your home directory", err.getvalue())


class MessageFormatTests(unittest.TestCase):
    """Pin the injected preambles (issues #7/#8) — the framing is part of the
    security surface: a silent rewording could re-introduce directive framing
    for cross-project content, and nothing else asserts the message format."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.entry = _entry(self.dir, "001-2026-01-01-alpha.md", "the auth layer")

    def test_project_local_preamble_is_pinned(self) -> None:
        ctx = acc_session_start.build_context(self.entry, "docs/acc/001-2026-01-01-alpha.md")
        self.assertTrue(
            ctx.startswith(
                "Inherited context from a prior session, auto-loaded from "
                "docs/acc/001-2026-01-01-alpha.md by the ACC SessionStart hook."
            )
        )
        self.assertIn("continue the work from it rather than replaying", ctx)
        self.assertIn("`/acc invoke-last`", ctx)

    def test_global_preamble_is_pinned(self) -> None:
        ctx = acc_session_start.build_context(self.entry, str(self.entry), from_global=True)
        self.assertTrue(
            ctx.startswith(
                "Inherited cross-project context, auto-loaded from the global ACC archive"
            )
        )
        self.assertIn("treat it as background context", ctx)
        self.assertIn("`/acc invoke-last`", ctx)
        self.assertNotIn("continue the work from it rather than replaying", ctx)

    def test_source_stamp_is_read_before_truncation(self) -> None:
        big = "# Session Checkpoint\n**Focus:** x\n**Source project:** /src/proj\n" + "x" * (
            acc_session_start.MAX_BYTES + 500
        )
        self.entry.write_text(big, encoding="utf-8")
        ctx = acc_session_start.build_context(self.entry, str(self.entry), from_global=True)
        self.assertIn("`/src/proj`", ctx)
        self.assertIn("truncated", ctx)


if __name__ == "__main__":
    unittest.main()
