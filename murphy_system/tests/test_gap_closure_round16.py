"""
Gap-closure tests — Round 16.

Gaps addressed:
51. 3 comparisons to empty collections (== [], == {}) → isinstance + len
52. 1 exec() in REPL → annotated with noqa marker (by-design)
"""

import ast
import os
import re

import pytest


SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")


class TestNoCompareEmptyCollection:
    """``== []``, ``== {}``, ``== ()`` should use ``not x`` or isinstance+len."""

    def test_no_compare_to_empty_collection(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Compare):
                        for op, comp in zip(node.ops, node.comparators):
                            if isinstance(op, (ast.Eq, ast.NotEq)):
                                is_empty = False
                                if isinstance(comp, (ast.List, ast.Tuple)):
                                    is_empty = len(comp.elts) == 0
                                elif isinstance(comp, ast.Dict):
                                    is_empty = len(comp.keys) == 0
                                elif isinstance(comp, ast.Set):
                                    is_empty = len(comp.elts) == 0
                                if is_empty:
                                    rel = os.path.relpath(fpath, SRC_DIR)
                                    violations.append(
                                        f"{rel}:{node.lineno}"
                                    )
        assert violations == [], (
            f"Comparisons to empty collections: {violations}"
        )


class TestExecOnlyInRepl:
    """``exec()`` must only appear in the REPL module."""

    def test_exec_only_in_repl(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        s = line.strip()
                        if s.startswith("#"):
                            continue
                        if re.search(r"(?<!\w)exec\s*\(", s):
                            if "security_audit" in fpath:
                                continue
                            rel = os.path.relpath(fpath, SRC_DIR)
                            if "repl" not in rel.lower():
                                violations.append(f"{rel}:{i}")
        assert violations == [], (
            f"exec() outside REPL: {violations}"
        )


class TestRound16Regression:
    """Regression checks for round 16."""

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

    def test_no_inherit_object(self):
        """Classes should not explicitly inherit from ``object``."""
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        for base in node.bases:
                            if (
                                isinstance(base, ast.Name)
                                and base.id == "object"
                            ):
                                rel = os.path.relpath(fpath, SRC_DIR)
                                violations.append(
                                    f"{rel}:{node.lineno}: {node.name}"
                                )
        assert violations == [], (
            f"Explicit object inheritance: {violations}"
        )

    def test_no_return_value_in_init(self):
        """``__init__`` must not return a value."""
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        for child in node.body:
                            if (
                                isinstance(child, ast.FunctionDef)
                                and child.name == "__init__"
                            ):
                                for sub in ast.walk(child):
                                    if (
                                        isinstance(sub, ast.Return)
                                        and sub.value is not None
                                    ):
                                        rel = os.path.relpath(fpath, SRC_DIR)
                                        violations.append(
                                            f"{rel}:{sub.lineno}"
                                        )
        assert violations == [], (
            f"Return value in __init__: {violations}"
        )
