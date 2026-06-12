#!/usr/bin/env python3
"""Tests for the deterministic ACC helper scripts.

Stdlib-only (unittest), so they run anywhere Python does without `pip`:

    python -m unittest discover -s tests       # from the repo root
    python -m pytest tests                      # if pytest is installed

The scripts encode the two pieces of logic the skill must get right every
time: which file is the *latest* ACC (Mode B) and what the *next* entry is
named (Mode A). These tests pin that behavior so a refactor can't silently
break selection or numbering.
"""

from __future__ import annotations

import importlib.util
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"


def _load(name: str):
    """Import a script by path (the dir name `scripts` isn't a package)."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


find_latest_acc = _load("find_latest_acc")
new_acc = _load("new_acc")


def _touch(directory: Path, name: str) -> Path:
    p = directory / name
    p.write_text("stub\n", encoding="utf-8")
    return p


class FindLatestTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_missing_dir_returns_none(self) -> None:
        self.assertIsNone(find_latest_acc.find_latest(self.dir / "nope"))

    def test_empty_dir_returns_none(self) -> None:
        self.assertIsNone(find_latest_acc.find_latest(self.dir))

    def test_only_readme_returns_none(self) -> None:
        _touch(self.dir, "README.md")
        self.assertIsNone(find_latest_acc.find_latest(self.dir))

    def test_picks_highest_lexicographically(self) -> None:
        _touch(self.dir, "001-2026-01-01-alpha.md")
        _touch(self.dir, "002-2026-02-01-beta.md")
        latest = _touch(self.dir, "010-2026-03-01-gamma.md")
        self.assertEqual(find_latest_acc.find_latest(self.dir), latest)

    def test_zero_padding_keeps_order_past_ten_and_hundred(self) -> None:
        _touch(self.dir, "009-2026-01-01-a.md")
        _touch(self.dir, "099-2026-01-01-b.md")
        latest = _touch(self.dir, "100-2026-01-01-c.md")
        self.assertEqual(find_latest_acc.find_latest(self.dir), latest)

    def test_readme_excluded_even_though_it_sorts_after_digits(self) -> None:
        # 'R' (0x52) sorts after digits (0x30-0x39); without the exclusion
        # README.md would be wrongly chosen as the newest entry.
        latest = _touch(self.dir, "001-2026-01-01-alpha.md")
        _touch(self.dir, "README.md")
        self.assertEqual(find_latest_acc.find_latest(self.dir), latest)

    def test_readme_exclusion_is_case_insensitive(self) -> None:
        latest = _touch(self.dir, "001-2026-01-01-alpha.md")
        _touch(self.dir, "readme.md")
        self.assertEqual(find_latest_acc.find_latest(self.dir), latest)

    def test_extractor_outputs_excluded_even_though_they_sort_after_digits(self) -> None:
        # '_' (0x5F) sorts after digits (0x30-0x39); without the exclusion the
        # /acc-extract outputs (_ledger.md, _backlog.md, _avoid.md) would be
        # wrongly chosen over the newest real entry.
        latest = _touch(self.dir, "007-2026-06-11-fixes.md")
        _touch(self.dir, "_ledger.md")
        _touch(self.dir, "_backlog.md")
        _touch(self.dir, "_avoid.md")
        self.assertEqual(find_latest_acc.find_latest(self.dir), latest)

    def test_only_extractor_outputs_returns_none(self) -> None:
        _touch(self.dir, "_ledger.md")
        self.assertIsNone(find_latest_acc.find_latest(self.dir))

    def test_main_missing_dir_exit_1(self) -> None:
        self.assertEqual(find_latest_acc.main(["--dir", str(self.dir / "nope")]), 1)

    def test_main_empty_dir_exit_1(self) -> None:
        self.assertEqual(find_latest_acc.main(["--dir", str(self.dir)]), 1)

    def test_main_success_exit_0_and_prints_path(self) -> None:
        _touch(self.dir, "001-2026-01-01-alpha.md")
        buf = StringIO()
        with redirect_stdout(buf):
            rc = find_latest_acc.main(["--dir", str(self.dir)])
        self.assertEqual(rc, 0)
        self.assertIn("001-2026-01-01-alpha.md", buf.getvalue().strip())


class SlugifyTests(unittest.TestCase):
    def test_basic_lowercase_and_hyphens(self) -> None:
        self.assertEqual(new_acc.slugify("Auth Rewrite"), "auth-rewrite")

    def test_collapses_runs_and_strips_edges(self) -> None:
        self.assertEqual(new_acc.slugify("  --Foo / Bar!!  "), "foo-bar")

    def test_keeps_digits(self) -> None:
        self.assertEqual(new_acc.slugify("v2 API migration"), "v2-api-migration")

    def test_empty_falls_back_to_session(self) -> None:
        self.assertEqual(new_acc.slugify("!!!"), "session")
        self.assertEqual(new_acc.slugify(""), "session")


class NextSeqTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_empty_starts_at_one(self) -> None:
        self.assertEqual(new_acc.next_seq(self.dir), 1)

    def test_missing_dir_starts_at_one(self) -> None:
        self.assertEqual(new_acc.next_seq(self.dir / "nope"), 1)

    def test_increments_past_highest(self) -> None:
        _touch(self.dir, "001-2026-01-01-a.md")
        _touch(self.dir, "007-2026-01-01-b.md")
        self.assertEqual(new_acc.next_seq(self.dir), 8)

    def test_ignores_non_sequence_names(self) -> None:
        _touch(self.dir, "README.md")
        _touch(self.dir, "notes.md")
        _touch(self.dir, "_ledger.md")
        _touch(self.dir, "003-2026-01-01-c.md")
        self.assertEqual(new_acc.next_seq(self.dir), 4)

    def test_handles_four_digit_sequences(self) -> None:
        _touch(self.dir, "1000-2026-01-01-a.md")
        self.assertEqual(new_acc.next_seq(self.dir), 1001)


class NewAccMainTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "docs" / "acc"
        self.addCleanup(self._tmp.cleanup)

    def _run(self, *args: str) -> int:
        return new_acc.main(["--dir", str(self.dir), *args])

    def test_creates_entry_with_padded_name(self) -> None:
        rc = self._run("--topic", "Auth Rewrite", "--date", "2026-05-27")
        self.assertEqual(rc, 0)
        out = self.dir / "001-2026-05-27-auth-rewrite.md"
        self.assertTrue(out.is_file())

    def test_seeds_readme_on_first_run(self) -> None:
        self._run("--topic", "alpha", "--date", "2026-01-01")
        self.assertTrue((self.dir / "README.md").is_file())

    def test_substitutes_date_and_focus(self) -> None:
        self._run("--topic", "alpha", "--focus", "the auth layer", "--date", "2026-01-01")
        body = (self.dir / "001-2026-01-01-alpha.md").read_text(encoding="utf-8")
        self.assertNotIn("{{DATE}}", body)
        self.assertNotIn("{{FOCUS}}", body)
        self.assertIn("2026-01-01", body)
        self.assertIn("the auth layer", body)

    def test_focus_defaults_to_topic(self) -> None:
        self._run("--topic", "auth-rewrite", "--date", "2026-01-01")
        body = (self.dir / "001-2026-01-01-auth-rewrite.md").read_text(encoding="utf-8")
        self.assertIn("auth-rewrite", body)

    def test_second_run_increments_sequence(self) -> None:
        self._run("--topic", "alpha", "--date", "2026-01-01")
        self._run("--topic", "beta", "--date", "2026-01-02")
        self.assertTrue((self.dir / "002-2026-01-02-beta.md").is_file())

    def test_invalid_date_exit_2(self) -> None:
        self.assertEqual(self._run("--topic", "alpha", "--date", "not-a-date"), 2)

    def test_dry_run_prints_path_without_writing(self) -> None:
        buf = StringIO()
        with redirect_stdout(buf):
            rc = self._run("--topic", "alpha", "--date", "2026-01-01", "--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn("001-2026-01-01-alpha.md", buf.getvalue())
        # Nothing should have been created on disk.
        self.assertFalse((self.dir / "001-2026-01-01-alpha.md").exists())
        self.assertFalse((self.dir / "README.md").exists())
        self.assertFalse(self.dir.exists())

    def test_dry_run_reports_next_seq(self) -> None:
        self._run("--topic", "alpha", "--date", "2026-01-01")
        buf = StringIO()
        with redirect_stdout(buf):
            rc = self._run("--topic", "beta", "--date", "2026-01-02", "--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn("002-2026-01-02-beta.md", buf.getvalue())
        self.assertFalse((self.dir / "002-2026-01-02-beta.md").exists())

    def test_refuses_overwrite_exit_3(self) -> None:
        # The guard is defensive: under normal flow next_seq is always fresh,
        # so a collision only happens if numbering is forced backwards. Pin
        # next_seq to 1 with 001 already on disk to exercise the guard.
        self.dir.mkdir(parents=True, exist_ok=True)
        _touch(self.dir, "001-2026-01-01-alpha.md")
        original = new_acc.next_seq
        new_acc.next_seq = lambda _dir: 1
        self.addCleanup(setattr, new_acc, "next_seq", original)
        self.assertEqual(self._run("--topic", "alpha", "--date", "2026-01-01"), 3)


if __name__ == "__main__":
    unittest.main()
