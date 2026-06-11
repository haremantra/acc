#!/usr/bin/env bash
# Install the acc skill for Claude Code (macOS / Linux).
#
# Symlinks this checkout into your Claude skills dir so `/acc` resolves in any
# project, then verifies the install. Re-runnable (idempotent).
#
#   ./install.sh            # symlink (recommended; edits here take effect live)
#   ./install.sh --copy     # copy files instead of symlinking
#   CLAUDE_SKILLS_DIR=... ./install.sh   # override the skills dir
#
# Uninstall with: make uninstall   (or remove the symlink it reports below)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
DEST="$SKILLS_DIR/acc"
MODE="symlink"
[ "${1:-}" = "--copy" ] && MODE="copy"

if [ ! -f "$SRC/SKILL.md" ]; then
  echo "error: $SRC doesn't look like the acc skill (no SKILL.md)" >&2
  exit 1
fi

mkdir -p "$SKILLS_DIR"

# Clear a prior install. A symlink is always ours to replace; a real
# directory is only replaced in --copy mode (a prior copy install), keeping
# the command idempotent without clobbering something unexpected.
if [ -L "$DEST" ]; then
  rm "$DEST"
elif [ -d "$DEST" ] && [ "$MODE" = "copy" ]; then
  rm -rf "$DEST"
elif [ -e "$DEST" ]; then
  echo "error: $DEST already exists and is not replaceable in $MODE mode." >&2
  echo "       Remove it first if you want to reinstall." >&2
  exit 1
fi

if [ "$MODE" = "copy" ]; then
  cp -R "$SRC" "$DEST"
else
  ln -s "$SRC" "$DEST"
fi

# Verify the loader will find the entry point.
if [ -f "$DEST/SKILL.md" ]; then
  echo "Installed acc ($MODE) -> $DEST"
  echo "Open Claude Code in any project and run /acc to confirm."
else
  echo "error: install verification failed; $DEST/SKILL.md missing" >&2
  exit 1
fi
