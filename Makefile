# Convenience targets for developing and installing the acc skill.
.PHONY: help install uninstall test lint format

SKILLS_DIR ?= $(HOME)/.claude/skills
DEST := $(SKILLS_DIR)/acc

help:
	@echo "Targets:"
	@echo "  make install     Symlink this checkout into $(SKILLS_DIR) (./install.sh)"
	@echo "  make uninstall   Remove the acc skill symlink/dir from $(SKILLS_DIR)"
	@echo "  make test        Run the unit + integrity test suite"
	@echo "  make lint        Run ruff check + ruff format --check + compileall"
	@echo "  make format      Apply ruff formatting"

install:
	./install.sh

uninstall:
	@if [ -L "$(DEST)" ] || [ -d "$(DEST)" ]; then rm -rf "$(DEST)"; echo "Removed $(DEST)"; \
	else echo "Nothing to remove at $(DEST)"; fi

test:
	python -m unittest discover -s tests

lint:
	ruff check .
	ruff format --check .
	python -m compileall -q scripts tests

format:
	ruff format .
