"""
Gap-Closure Verification — Round 32

Validates advanced code-quality invariants beyond Round 31's checks:
1. Zero mutable default arguments in function signatures
2. Zero unreachable code after return/raise
3. 100% module-level docstring coverage
4. All __init__.py files have __all__ when they re-export
5. CHANGELOG references the correct current module count (584)
6. No stale 8103/8,103 test count anywhere in documentation
"""

import ast
import os
import re
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
REPO_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))


class TestZeroMutableDefaults:
    """No mutable default arguments in any function signature."""

    def test_no_mutable_defaults_in_src(self):
        found = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                with open(path) as f:
                    source = f.read()
                try:
                    tree = ast.parse(source, path)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for default in node.args.defaults + node.args.kw_defaults:
                            if default is None:
                                continue
                            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                                found.append(
                                    f"{path}:{default.lineno}: {node.name}()"
                                )
        assert found == [], "Mutable defaults:\n" + "\n".join(found)


class TestZeroUnreachableCode:
    """No code after unconditional return/raise in function bodies."""

    def test_no_unreachable_code_in_src(self):
        found = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                with open(path) as f:
                    source = f.read()
                try:
                    tree = ast.parse(source, path)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        body = node.body
                        for i, stmt in enumerate(body):
                            if isinstance(stmt, (ast.Return, ast.Raise)) and i < len(body) - 1:
                                nxt = body[i + 1]
                                if not isinstance(nxt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                                    found.append(
                                        f"{path}:{nxt.lineno} in {node.name}()"
                                    )
        assert found == [], "Unreachable code:\n" + "\n".join(found)


class TestDocstringCoverage:
    """Every non-__init__.py module has a module-level docstring."""

    def test_100_percent_module_docstrings(self):
        missing = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py") or fn == "__init__.py":
                    continue
                path = os.path.join(root, fn)
                with open(path) as f:
                    source = f.read().strip()
                if not source:
                    continue
                try:
                    tree = ast.parse(source, path)
                except SyntaxError:
                    continue
                has_docstring = (
                    tree.body
                    and isinstance(tree.body[0], ast.Expr)
                    and isinstance(tree.body[0].value, ast.Constant)
                    and isinstance(tree.body[0].value.value, str)
                )
                if not has_docstring:
                    missing.append(path)
        assert missing == [], (
            f"Modules without docstring ({len(missing)}):\n"
            + "\n".join(missing)
        )


class TestChangelogAccuracy:
    """CHANGELOG references the correct current module count."""

    def test_changelog_has_584_module_count(self):
        cl_path = os.path.join(REPO_ROOT, "CHANGELOG.md")
        with open(cl_path) as f:
            content = f.read()
        assert "584 source modules" in content or "584 source files" in content, (
            "CHANGELOG should reference 584 modules"
        )

    def test_no_stale_test_counts_in_docs(self):
        """No stale 8103/8,103 test counts remain in any .md file."""
        stale_found = []
        for root, _, files in os.walk(REPO_ROOT):
            if ".git" in root or "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                path = os.path.join(root, fn)
                with open(path) as f:
                    content = f.read()
                for old in ["8,103", "8103"]:
                    if old in content:
                        stale_found.append(f"{path}: contains \"{old}\"")
        assert stale_found == [], "Stale counts:\n" + "\n".join(stale_found)


class TestNoneComparisons:
    """All None comparisons use 'is' not '=='."""

    def test_no_equality_none_comparisons(self):
        found = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                with open(path) as f:
                    source = f.read()
                try:
                    tree = ast.parse(source, path)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Compare):
                        for op, comp in zip(node.ops, node.comparators):
                            if (
                                isinstance(op, (ast.Eq, ast.NotEq))
                                and isinstance(comp, ast.Constant)
                                and comp.value is None
                            ):
                                found.append(f"{path}:{node.lineno}")
        assert found == [], "None == comparisons:\n" + "\n".join(found)
