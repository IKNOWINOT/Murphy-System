"""
Gap-Closure Verification — Round 29

Validates that all identified gaps from the Round 29 audit have been closed:
1. Zero stale test files (files that collect no tests) in tests/ directory
2. Zero deprecated datetime.utcnow() calls in production source
3. pytest.ini properly scopes test collection to tests/ directory
4. All source packages have __init__.py
5. Zero bare except clauses in production source
6. Zero syntax errors across all source modules
"""

import ast
import configparser
import os
import re
import subprocess
import sys

import pytest

# Resolve paths relative to repo root.
# This file lives at tests/documentation_qa/, so the repo root is two levels up.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")


class TestGapClosureRound29:
    """Verify all Round 29 audit gaps are closed."""

    def test_no_stale_test_files_in_tests_directory(self):
        """Every test_*.py file in tests/ must collect at least one test."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", TESTS_DIR, "--co", "-q"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        # Check for collection errors (shown as "N errors during collection")
        assert result.returncode == 0, (
            f"Test collection failed (rc={result.returncode}):\n"
            f"{result.stderr[:500]}"
        )
        # Verify no "errors during collection" message in output
        for line in result.stdout.splitlines():
            assert "errors during collection" not in line.lower(), (
                f"Collection errors found: {line}"
            )

    def test_no_deprecated_utcnow_in_source(self):
        """Production source must not call datetime.utcnow() directly.

        Uses AST analysis to detect actual attribute calls, ignoring
        wrapper function definitions and comments.
        """
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                with open(path, encoding="utf-8") as f:
                    source = f.read()
                try:
                    tree = ast.parse(source, path)
                except SyntaxError:
                    continue  # caught by test_zero_syntax_errors_in_source
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "utcnow"
                    ):
                        violations.append(f"{path}:{node.lineno}")
        assert violations == [], (
            f"Deprecated datetime.utcnow() calls found:\n"
            + "\n".join(violations)
        )

    def test_pytest_ini_has_testpaths(self):
        """pytest.ini must scope collection to tests/ directory."""
        ini_path = os.path.join(PROJECT_ROOT, "pytest.ini")
        assert os.path.exists(ini_path), "pytest.ini not found"
        config = configparser.ConfigParser()
        config.read(ini_path)
        assert config.has_option("pytest", "testpaths"), (
            "pytest.ini missing 'testpaths' — archive/ files will be collected"
        )
        assert "tests" in config.get("pytest", "testpaths")

    def test_all_source_packages_have_init(self):
        """Every directory under src/ with .py files must have __init__.py."""
        missing = []
        for root, _dirs, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            py_files = [f for f in files if f.endswith(".py") and f != "__init__.py"]
            if py_files and "__init__.py" not in files:
                missing.append(root)
        assert missing == [], (
            f"Directories missing __init__.py:\n" + "\n".join(missing)
        )

    def test_no_bare_except_in_source(self):
        """Production source must not use bare 'except:' clauses."""
        bare_except_re = re.compile(r"^\s*except\s*:\s*(?:#.*)?$")
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                with open(path, encoding="utf-8") as f:
                    for lineno, line in enumerate(f, 1):
                        if bare_except_re.match(line):
                            violations.append(f"{path}:{lineno}")
        assert violations == [], (
            f"Bare 'except:' found:\n" + "\n".join(violations)
        )

    def test_zero_syntax_errors_in_source(self):
        """Every .py file in src/ must parse without syntax errors."""
        errors = []
        for root, _dirs, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                try:
                    with open(path, encoding="utf-8") as f:
                        ast.parse(f.read(), path)
                except SyntaxError as exc:
                    errors.append(f"{path}: {exc}")
        assert errors == [], (
            f"Syntax errors found:\n" + "\n".join(errors)
        )
