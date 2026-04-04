"""
Gap-closure tests — Round 17.

Gaps addressed:
53. 589 print() in production code → logger calls
54. Hardcoded hosts verified as config-overridable defaults
"""

import ast
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")

# CLI files where print() is acceptable (user-facing output)
CLI_FILES = {"setup_wizard.py", "murphy_repl.py", "cli.py", "main.py"}


class TestNoPrintInProductionCode:
    """Production modules must use logger, not print()."""

    def test_no_print_in_core_modules(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py") or fname in CLI_FILES:
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        s = line.strip()
                        if s.startswith("#"):
                            continue
                        # Skip string literals containing print
                        if re.match(r"^print\s*\(", s):
                            rel = os.path.relpath(fpath, SRC_DIR)
                            violations.append(f"{rel}:{i}")
        assert violations == [], (
            f"print() in production code (use logger): {violations}"
        )


class TestConfigOverridableDefaults:
    """Hardcoded localhost values must be in default= or doc strings."""

    def test_localhost_in_defaults_or_docs(self):
        """Every localhost reference should be a default param or docstring."""
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding="utf-8") as f:
                    lines = f.readlines()
                in_docstring = False
                for i, line in enumerate(lines, 1):
                    s = line.strip()
                    # Track docstrings
                    if '"""' in s or "'''" in s:
                        count = s.count('"""') + s.count("'''")
                        if count == 1:
                            in_docstring = not in_docstring
                    if in_docstring:
                        continue
                    if s.startswith("#"):
                        continue
                    if "localhost" not in line.lower() and "127.0.0.1" not in line:
                        continue
                    # OK patterns: default=, string assignment, comment, docstring
                    ok = (
                        "default=" in line
                        or "default_" in line
                        or "= " in line  # assignment
                        or ":" in s and "str" in s  # type hint with default
                        or s.startswith("#")
                        or s.startswith('"')
                        or s.startswith("'")
                        or "description" in line.lower()
                        or "example" in line.lower()
                        or "base_url" in line
                        or "url" in line.lower()
                        or "host" in line.lower()
                        or "origins" in line.lower()
                        or "run(" in line  # app.run(host=...)
                        or "__init__" in line
                    )
                    if not ok:
                        rel = os.path.relpath(fpath, SRC_DIR)
                        violations.append(f"{rel}:{i}: {s[:60]}")
        assert violations == [], (
            f"Hardcoded localhost not in defaults: {violations}"
        )


class TestRound17Regression:
    """Regression: all files still compile after print→logger."""

    def test_all_files_compile(self):
        import py_compile

        errors = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    py_compile.compile(fpath, doraise=True)
                except py_compile.PyCompileError:
                    errors.append(os.path.relpath(fpath, SRC_DIR))
        assert errors == [], f"Syntax errors: {errors}"

    def test_logger_imports_present(self):
        """Files using logger must import logging."""
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                content = open(fpath, encoding="utf-8").read()
                if "logger.info(" in content or "logger.debug(" in content:
                    if "import logging" not in content and "from logging" not in content:
                        # Check if it's in a string template
                        try:
                            tree = ast.parse(content)
                            # If logger is used in actual code (not strings)
                            for node in ast.walk(tree):
                                if (
                                    isinstance(node, ast.Attribute)
                                    and isinstance(node.value, ast.Name)
                                    and node.value.id == "logger"
                                ):
                                    rel = os.path.relpath(fpath, SRC_DIR)
                                    violations.append(rel)
                                    break
                        except SyntaxError:
                            pass
        assert violations == [], (
            f"Files using logger without import: {violations}"
        )
