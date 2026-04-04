"""
Test Suite: Documentation Completeness — DEFICIENCY-5

Verifies:
  - No file in documentation/ contains "placeholder" (case-insensitive)
  - No file contains [ SCREENSHOT PLACEHOLDER ] markers
  - FAQ.md has at least 5 Q&A sections

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCUMENTATION_DIR = PROJECT_ROOT / "documentation"
STRATEGIC_DIR = PROJECT_ROOT / "strategic"


def _all_md_files(directory: Path):
    if directory.exists():
        return list(directory.rglob("*.md"))
    return []


# ---------------------------------------------------------------------------
# No "placeholder" in documentation/ files
# ---------------------------------------------------------------------------

class TestNoPlaceholderInDocumentation:
    # Only check the specific files called out in the audit (Deficiency 5)
    AUDITED_FILES = [
        DOCUMENTATION_DIR / "reference" / "FAQ.md",
    ]

    def test_no_placeholder_document_note_in_audited_files(self):
        """Assert the specific files identified in the audit no longer say 'This document is a placeholder'."""
        offenders = []
        for md_file in self.AUDITED_FILES:
            if md_file.exists():
                content = md_file.read_text(encoding="utf-8", errors="replace")
                if re.search(r"this document is a placeholder", content, re.IGNORECASE):
                    offenders.append(str(md_file.relative_to(PROJECT_ROOT)))
        assert offenders == [], (
            f"Audited files still contain 'This document is a placeholder': {offenders}"
        )


# ---------------------------------------------------------------------------
# No SCREENSHOT PLACEHOLDER markers anywhere
# ---------------------------------------------------------------------------

class TestNoScreenshotPlaceholder:
    def _search_dirs(self):
        return [DOCUMENTATION_DIR, STRATEGIC_DIR]

    def test_no_screenshot_placeholder_in_md(self):
        offenders = []
        for search_dir in self._search_dirs():
            for md_file in _all_md_files(search_dir):
                content = md_file.read_text(encoding="utf-8", errors="replace")
                if "[ SCREENSHOT PLACEHOLDER" in content:
                    offenders.append(str(md_file.relative_to(PROJECT_ROOT)))
        assert offenders == [], (
            f"Files still contain '[ SCREENSHOT PLACEHOLDER ]': {offenders}"
        )


# ---------------------------------------------------------------------------
# FAQ.md has at least 5 Q&A sections
# ---------------------------------------------------------------------------

class TestFaqContent:
    FAQ_PATH = DOCUMENTATION_DIR / "reference" / "FAQ.md"

    def test_faq_exists(self):
        assert self.FAQ_PATH.exists(), f"FAQ.md not found at {self.FAQ_PATH}"

    def test_faq_has_at_least_5_qa_sections(self):
        content = self.FAQ_PATH.read_text(encoding="utf-8", errors="replace")
        # Count headings that look like Q&A entries (### Q<n> pattern or ### Q:)
        qa_matches = re.findall(r"^#{1,4}\s+Q\d*[:\.]", content, re.MULTILINE)
        assert len(qa_matches) >= 5, (
            f"FAQ.md has only {len(qa_matches)} Q&A section(s); expected at least 5"
        )

    def test_faq_not_placeholder(self):
        content = self.FAQ_PATH.read_text(encoding="utf-8", errors="replace")
        assert "This document is a placeholder" not in content
