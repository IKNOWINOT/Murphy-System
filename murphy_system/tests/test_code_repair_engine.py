"""
Tests for the CodeRepairEngine.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os
import textwrap
import uuid

import pytest


from code_repair_engine import (
    BroadExceptionStrategy,
    CodeIssue,
    CodePatch,
    CodeRepairEngine,
    MissingDocstringStrategy,
    MissingHandlerStrategy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_tmp_file(tmp_path, content: str, filename: str = "sample.py") -> str:
    """Write content to a temp file and return the path."""
    fpath = str(tmp_path / filename)
    with open(fpath, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(content))
    return fpath


# ---------------------------------------------------------------------------
# Scan detection tests
# ---------------------------------------------------------------------------

class TestScanDetections:
    def test_scan_detects_missing_docstring(self, tmp_path):
        """scan_file should detect a public function without a docstring."""
        fpath = _write_tmp_file(
            tmp_path,
            """\
            def compute_value(x):
                return x * 2
            """,
        )
        engine = CodeRepairEngine()
        issues = engine.scan_file(fpath)
        doc_issues = [i for i in issues if i.issue_type == "missing_doc"]
        assert len(doc_issues) >= 1, "Expected at least one missing_doc issue"
        assert "compute_value" in doc_issues[0].description

    def test_scan_detects_broad_exception(self, tmp_path):
        """scan_file should detect a broad except Exception clause."""
        fpath = _write_tmp_file(
            tmp_path,
            """\
            def risky():
                try:
                    pass
                except Exception as exc:
                    pass
            """,
        )
        engine = CodeRepairEngine()
        issues = engine.scan_file(fpath)
        broad_issues = [i for i in issues if i.issue_type == "bug" and "broad" in i.description.lower()]
        assert len(broad_issues) >= 1, "Expected at least one broad exception issue"

    def test_scan_detects_missing_handler(self, tmp_path):
        """scan_file should detect an except block that only passes."""
        fpath = _write_tmp_file(
            tmp_path,
            """\
            def fetch():
                try:
                    return 1
                except ValueError as exc:
                    pass
            """,
        )
        engine = CodeRepairEngine()
        issues = engine.scan_file(fpath)
        handler_issues = [i for i in issues if i.issue_type == "missing_handler"]
        assert len(handler_issues) >= 1, "Expected missing_handler issue"

    def test_scan_handles_syntax_error_gracefully(self, tmp_path):
        """scan_file should return an empty list for unparseable files."""
        fpath = _write_tmp_file(tmp_path, "def broken(\n")
        engine = CodeRepairEngine()
        issues = engine.scan_file(fpath)
        assert issues == [], "Expected empty list for a file with syntax errors"

    def test_scan_skips_private_functions_for_docstrings(self, tmp_path):
        """Private functions (prefixed _) should not be flagged for missing docstrings."""
        fpath = _write_tmp_file(
            tmp_path,
            """\
            def _internal():
                return 42
            """,
        )
        engine = CodeRepairEngine()
        issues = engine.scan_file(fpath)
        doc_issues = [i for i in issues if i.issue_type == "missing_doc"]
        names_flagged = [i.ast_context.get("name") for i in doc_issues]
        assert "_internal" not in names_flagged


# ---------------------------------------------------------------------------
# Repair generation tests
# ---------------------------------------------------------------------------

class TestGenerateRepairs:
    def test_generate_repair_for_missing_docstring(self, tmp_path):
        """generate_repairs should produce a patch for a missing_doc issue."""
        fpath = _write_tmp_file(
            tmp_path,
            """\
            def greet(name):
                return f"Hello {name}"
            """,
        )
        engine = CodeRepairEngine()
        issues = engine.scan_file(fpath)
        doc_issues = [i for i in issues if i.issue_type == "missing_doc"]
        assert doc_issues, "No missing_doc issues detected"
        patches = engine.generate_repairs(doc_issues)
        assert len(patches) >= 1
        # The proposed content should contain a docstring
        patch = patches[0]
        assert '"""' in patch.proposed_content or "'''" in patch.proposed_content

    def test_all_patches_require_human_review(self, tmp_path):
        """All generated patches must have requires_human_review=True."""
        fpath = _write_tmp_file(
            tmp_path,
            """\
            def work():
                try:
                    pass
                except Exception as exc:
                    pass
            """,
        )
        engine = CodeRepairEngine()
        issues = engine.scan_file(fpath)
        patches = engine.generate_repairs(issues)
        assert patches, "Expected at least one patch"
        for patch in patches:
            assert patch.requires_human_review is True, (
                f"Patch {patch.patch_id} has requires_human_review=False"
            )


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidatePatch:
    def test_validate_patch_checks_syntax_valid(self, tmp_path):
        """validate_patch should return True for syntactically valid Python."""
        fpath = _write_tmp_file(tmp_path, "x = 1\n")
        issue = CodeIssue(
            issue_id=str(uuid.uuid4()),
            file_path=fpath,
            line_range=(1, 1),
            issue_type="style",
            description="test",
            severity="low",
            ast_context={},
        )
        patch = CodePatch(
            patch_id=str(uuid.uuid4()),
            file_path=fpath,
            original_content="x = 1\n",
            proposed_content="x = 2\n",
            diff_text="",
            issue_id=issue.issue_id,
            strategy="test",
            confidence=1.0,
            requires_human_review=True,
        )
        engine = CodeRepairEngine()
        assert engine.validate_patch(patch) is True

    def test_validate_patch_checks_syntax_invalid(self):
        """validate_patch should return False for syntactically invalid Python."""
        patch = CodePatch(
            patch_id=str(uuid.uuid4()),
            file_path="/tmp/fake.py",
            original_content="x = 1\n",
            proposed_content="def broken(\n",
            diff_text="",
            issue_id=str(uuid.uuid4()),
            strategy="test",
            confidence=0.0,
            requires_human_review=True,
        )
        engine = CodeRepairEngine()
        assert engine.validate_patch(patch) is False

    def test_validate_patch_empty_content_returns_false(self):
        """validate_patch with empty proposed_content should return False."""
        patch = CodePatch(
            patch_id=str(uuid.uuid4()),
            file_path="/tmp/fake.py",
            original_content="x = 1\n",
            proposed_content="",
            diff_text="",
            issue_id=str(uuid.uuid4()),
            strategy="test",
            confidence=0.0,
            requires_human_review=True,
        )
        engine = CodeRepairEngine()
        assert engine.validate_patch(patch) is False


# ---------------------------------------------------------------------------
# Sandbox apply tests
# ---------------------------------------------------------------------------

class TestApplyPatchToSandbox:
    def test_apply_patch_to_sandbox_writes_file(self, tmp_path):
        """apply_patch_to_sandbox should write the proposed content to the sandbox dir."""
        sandbox_dir = str(tmp_path / "sandbox")
        patch = CodePatch(
            patch_id=str(uuid.uuid4()),
            file_path="/src/module.py",
            original_content="x = 1\n",
            proposed_content="x = 2\n",
            diff_text="",
            issue_id=str(uuid.uuid4()),
            strategy="test",
            confidence=1.0,
            requires_human_review=True,
        )
        engine = CodeRepairEngine()
        result = engine.apply_patch_to_sandbox(patch, sandbox_dir)
        assert result is True
        written_path = os.path.join(sandbox_dir, "module.py")
        assert os.path.exists(written_path)
        with open(written_path, encoding="utf-8") as fh:
            content = fh.read()
        assert content == "x = 2\n"


# ---------------------------------------------------------------------------
# Directory scan test
# ---------------------------------------------------------------------------

class TestScanDirectory:
    def test_scan_directory_returns_issues_from_multiple_files(self, tmp_path):
        """scan_directory should aggregate issues from all .py files."""
        _write_tmp_file(tmp_path, "def foo():\n    return 1\n", "a.py")
        _write_tmp_file(tmp_path, "def bar():\n    return 2\n", "b.py")
        engine = CodeRepairEngine()
        issues = engine.scan_directory(str(tmp_path))
        # Both files have undocumented public functions
        names = {i.ast_context.get("name") for i in issues if i.issue_type == "missing_doc"}
        assert "foo" in names
        assert "bar" in names
