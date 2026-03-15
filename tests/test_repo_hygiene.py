"""
Test Suite: Repository Hygiene — DEFICIENCY-7

Verifies:
  - .vscode/ is in the root .gitignore
  - murphy_system_archive.md does NOT exist at repo root
  - full_system_assessment.md does NOT exist in repository root/ root

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_ROOT  # repo root (flattened — no more repository root/ subdir)


class TestRepoHygiene:
    def test_vscode_in_gitignore(self):
        gitignore = REPO_ROOT / ".gitignore"
        assert gitignore.exists(), ".gitignore not found at repo root"
        content = gitignore.read_text(encoding="utf-8", errors="replace")
        # Accept .vscode/ or .vscode (with or without trailing slash)
        lines = [line.strip() for line in content.splitlines()]
        assert any(
            line in (".vscode/", ".vscode") for line in lines
        ), ".vscode/ is not listed in root .gitignore"

    def test_murphy_system_archive_not_at_repo_root(self):
        archive_at_root = REPO_ROOT / "murphy_system_archive.md"
        assert not archive_at_root.exists(), (
            "murphy_system_archive.md should not exist at repo root; "
            "it should be in docs/archive/"
        )

    def test_full_system_assessment_not_in_murphy_system_root(self):
        assessment_at_root = PROJECT_ROOT / "full_system_assessment.md"
        assert not assessment_at_root.exists(), (
            "full_system_assessment.md should not exist in repository root/ root; "
            "it should be in docs/archive/internal/"
        )

    def test_murphy_system_archive_exists_in_archive(self):
        archive_correct = REPO_ROOT / "docs" / "archive" / "murphy_system_archive.md"
        assert archive_correct.exists(), (
            "murphy_system_archive.md should exist in docs/archive/ after move"
        )

    def test_full_system_assessment_exists_in_archive(self):
        assessment_correct = PROJECT_ROOT / "docs" / "archive" / "internal" / "full_system_assessment.md"
        assert assessment_correct.exists(), (
            "full_system_assessment.md should exist in docs/archive/internal/ after move"
        )
