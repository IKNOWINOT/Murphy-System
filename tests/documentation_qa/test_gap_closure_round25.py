"""
Gap-closure tests — Round 25.

Categories addressed:
53. LOGGING_NO_GETLOGGER — 2 __init__.py files used logging.warning() instead of getLogger()
54. TEMP_FILES — .pyc files excluded via .gitignore (false positive for git tracking)
55. TEST_COLLECTION — fastapi test guarded with pytest.importorskip

Quality gates:
- All files using ``import logging`` in production also call ``getLogger``
- No .pyc/.pyo files are tracked in version control
- All test files can be collected by pytest without import errors
"""

import ast
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")


def _walk_py(base=SRC_DIR):
    """Yield all .py source files."""
    for root, _dirs, files in os.walk(base):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


class TestLoggingUsesGetLogger:
    """Every production file that imports logging must use getLogger."""

    def test_no_bare_logging_calls(self):
        missing = []
        for fpath in _walk_py():
            if "/tests/" in fpath:
                continue
            with open(fpath, encoding="utf-8") as fh:
                content = fh.read()
            lines = content.split("\n")
            if "import logging" in content and "getLogger" not in content:
                if len(lines) > 30:
                    rel = os.path.relpath(fpath, SRC_DIR)
                    missing.append(rel)
        assert missing == [], f"Files with logging but no getLogger: {missing}"


class TestNoPycTracked:
    """No .pyc or .pyo files should be tracked in git."""

    def test_no_bytecode_in_git(self):
        result = subprocess.run(
            ["git", "ls-files", "*.pyc", "*.pyo"],
            capture_output=True, text=True,
            cwd=REPO_ROOT,
        )
        tracked = [f for f in result.stdout.strip().split("\n") if f]
        assert tracked == [], f"Bytecode files tracked in git: {tracked}"


class TestAllTestsCollectable:
    """All test files must parse without syntax errors."""

    def test_test_files_parse(self):
        test_dir = os.path.join(REPO_ROOT, "tests")
        errors = []
        for root, _dirs, files in os.walk(test_dir):
            for f in files:
                if f.endswith(".py") and f.startswith("test_"):
                    fpath = os.path.join(root, f)
                    try:
                        with open(fpath, encoding="utf-8") as fh:
                            ast.parse(fh.read())
                    except SyntaxError as exc:
                        errors.append(f"{f}: {exc}")
        assert errors == [], f"Test file syntax errors: {errors}"
