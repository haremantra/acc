#!/usr/bin/env python3
"""Scaffold a new ACC entry in docs/acc/ (Mode A helper for the /acc skill).

Computes the next zero-padded sequence number, renders the bundled
assets/acc-template.md (substituting {{DATE}} and {{FOCUS}}), and writes
docs/acc/NNN-YYYY-MM-DD-topic.md under the current working directory. On first run
it also drops the README seed (assets/docs-acc-readme.md) as docs/acc/README.md.

The model fills the five body sections after this scaffolds the skeleton.

Usage:
    python new_acc.py --topic auth-rewrite
    python new_acc.py --topic auth-rewrite --focus "auth middleware" --date 2026-05-27
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path

# Bundled assets sit next to this script's parent: <skill>/assets/
ASSETS = Path(__file__).resolve().parent.parent / "assets"
TEMPLATE = ASSETS / "acc-template.md"
README_SEED = ASSETS / "docs-acc-readme.md"

SEQ_RE = re.compile(r"^(\d{3,})-")


def next_seq(acc_dir: Path) -> int:
    highest = 0
    if acc_dir.is_dir():
        for p in acc_dir.glob("*.md"):
            m = SEQ_RE.match(p.name)
            if m:
                highest = max(highest, int(m.group(1)))
    return highest + 1


def slugify(topic: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", topic.strip().lower()).strip("-")
    return s or "session"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold a new ACC entry.")
    parser.add_argument("--topic", required=True, help="Short focus slug, e.g. auth-rewrite.")
    parser.add_argument("--focus", default="", help="Human-readable focus (defaults to topic).")
    parser.add_argument("--date", default="", help="YYYY-MM-DD (default: today).")
    parser.add_argument(
        "--dir", default="docs/acc", help="Archive dir (default: docs/acc under cwd)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the path that would be created (it includes the next NNN) without writing.",
    )
    args = parser.parse_args(argv)

    if not TEMPLATE.is_file():
        print(f"Template missing: {TEMPLATE}", file=sys.stderr)
        return 2

    try:
        date = (_dt.date.fromisoformat(args.date) if args.date else _dt.date.today()).isoformat()
    except ValueError:
        print(f"Invalid --date {args.date!r} (expected YYYY-MM-DD).", file=sys.stderr)
        return 2

    focus = args.focus.strip() or args.topic.strip()
    slug = slugify(args.topic)

    # next_seq tolerates a missing dir, so we can compute the target path
    # before creating anything — required for an honest --dry-run.
    acc_dir = Path(args.dir).resolve()
    seq = next_seq(acc_dir)
    out = acc_dir / f"{seq:03d}-{date}-{slug}.md"

    if out.exists():
        print(f"Refusing to overwrite existing {out}", file=sys.stderr)
        return 3

    if args.dry_run:
        # No mkdir, no README seed, no write — just report the plan.
        print(out)
        return 0

    acc_dir.mkdir(parents=True, exist_ok=True)

    # Seed the archive README on first run.
    readme = acc_dir / "README.md"
    if not readme.exists() and README_SEED.is_file():
        readme.write_text(README_SEED.read_text(encoding="utf-8"), encoding="utf-8")

    body = TEMPLATE.read_text(encoding="utf-8")
    body = body.replace("{{DATE}}", date).replace("{{FOCUS}}", focus)
    out.write_text(body, encoding="utf-8")

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
