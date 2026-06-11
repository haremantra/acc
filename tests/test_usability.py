#!/usr/bin/env python3
"""Tests for the usability helpers: list_acc.py and the SessionStart hook.

Stdlib-only, same as the rest of the suite:

    python -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

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
    header = f"# Context Compression\n**Focus:** {focus}\n" if focus else "# no header\n"
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


if __name__ == "__main__":
    unittest.main()
