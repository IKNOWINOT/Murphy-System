"""
Tests for audit findings — proves each fix is resolved.

Covers:
  B-001: load_dotenv called at import time
  M-005: License footer says BSL 1.1 (not Apache 2.0) in .env.example
  G-003: BUSINESS_MODEL.md exists
  M-001: STATUS.md exists with regulatory alignment section
  Terminology: No "hipaa_compliant" in docs (should be "hipaa_aligned")
"""

import os
import re
import sys

import pytest

# Ensure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestAuditB001LoadDotenv:
    """B-001: load_dotenv must be called after importing it."""

    def test_load_dotenv_called_at_import(self):
        # After INC-13 refactor, load_dotenv lives in src/runtime/_deps.py
        deps_path = os.path.join(ROOT, "src", "runtime", "_deps.py")
        with open(deps_path, encoding="utf-8") as f:
            content = f.read()
        # Must have the import AND a call BEFORE the main create_app
        assert "from dotenv import load_dotenv" in content
        # The call should appear near the import, not only inside create_app
        import_idx = content.index("from dotenv import load_dotenv")
        # Find the first actual call after import
        call_match = re.search(r"_load_dotenv\(", content[import_idx:])
        assert call_match is not None, "load_dotenv is imported but never called"
        # The call should be within 500 chars of the import (top-level, not buried)
        assert call_match.start() < 500, (
            "load_dotenv call is too far from import — should be at module level"
        )


class TestAuditM005LicenseFooter:
    """M-005: .env.example should say BSL 1.1, not Apache 2.0."""

    def test_env_example_license_is_bsl(self):
        env_path = os.path.join(ROOT, ".env.example")
        with open(env_path, encoding="utf-8") as f:
            content = f.read()
        assert "BSL 1.1" in content, ".env.example must reference BSL 1.1"
        # Ensure old Apache reference is gone from the license line
        for line in content.splitlines():
            if line.startswith("# License:"):
                assert "Apache" not in line, (
                    f"License line still says Apache: {line}"
                )


class TestAuditG003BusinessModel:
    """G-003: BUSINESS_MODEL.md must exist."""

    def test_business_model_exists(self):
        path = os.path.join(ROOT, "BUSINESS_MODEL.md")
        assert os.path.isfile(path), "BUSINESS_MODEL.md is missing"

    def test_business_model_has_content(self):
        path = os.path.join(ROOT, "BUSINESS_MODEL.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 200, "BUSINESS_MODEL.md is too short"
        assert "BSL 1.1" in content


class TestAuditM001StatusMd:
    """M-001: STATUS.md must exist with honest status."""

    def test_status_md_exists(self):
        path = os.path.join(ROOT, "STATUS.md")
        assert os.path.isfile(path), "STATUS.md is missing"

    def test_status_md_uses_aligned_not_compliant(self):
        path = os.path.join(ROOT, "STATUS.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "Aligned" in content
        assert "aligned with" in content.lower()
        # Should not claim formal compliance
        assert "formally compliant" not in content.lower()

    def test_status_md_no_inflated_percentages(self):
        path = os.path.join(ROOT, "STATUS.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "~99%" not in content
        assert "Security: 100%" not in content


class TestAuditTerminology:
    """Regulatory terminology: use 'aligned' not 'compliant' for unattested frameworks."""

    def test_no_hipaa_compliant_in_docs(self):
        """Docs should say hipaa_aligned, not hipaa_compliant."""
        docs_dir = os.path.join(ROOT, "documentation")
        if not os.path.isdir(docs_dir):
            pytest.skip("documentation/ directory not found")
        violations = []
        for dirpath, _dirs, files in os.walk(docs_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(dirpath, fname)
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
                if "hipaa_compliant" in content.lower():
                    rel = os.path.relpath(fpath, ROOT)
                    violations.append(rel)
        assert violations == [], (
            f"Files still using 'hipaa_compliant' instead of 'hipaa_aligned': {violations}"
        )
