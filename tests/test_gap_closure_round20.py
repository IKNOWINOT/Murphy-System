"""
Gap-closure tests — Round 20.

Gaps addressed:
44. 1 duplicate function (_record_submission) in form_intake/handlers.py → renamed
45. 220 public classes missing docstrings → added
"""

import ast
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")


class TestNoDuplicateFunctions:
    """No duplicate function/method names within same scope."""

    def test_no_module_level_duplicates(self):
        dupes = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    tree = ast.parse(open(fpath, encoding="utf-8").read())
                except SyntaxError:
                    continue
                names = [
                    n.name
                    for n in tree.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                seen: set[str] = set()
                for nm in names:
                    if nm in seen:
                        rel = os.path.relpath(fpath, SRC_DIR)
                        dupes.append(f"{rel}::{nm}")
                    seen.add(nm)
        assert dupes == [], f"Duplicate module-level functions: {dupes}"

    def test_no_class_level_duplicates(self):
        dupes = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    tree = ast.parse(open(fpath, encoding="utf-8").read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ClassDef):
                        continue
                    mnames = [
                        n.name
                        for n in node.body
                        if isinstance(
                            n, (ast.FunctionDef, ast.AsyncFunctionDef)
                        )
                    ]
                    seen: set[str] = set()
                    for nm in mnames:
                        if nm in seen:
                            rel = os.path.relpath(fpath, SRC_DIR)
                            dupes.append(
                                f"{rel}::{node.name}.{nm}"
                            )
                        seen.add(nm)
        assert dupes == [], f"Duplicate class methods: {dupes}"


class TestPublicClassDocstrings:
    """All public classes must have a docstring."""

    def test_all_public_classes_have_docstrings(self):
        missing = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    tree = ast.parse(
                        open(fpath, encoding="utf-8").read()
                    )
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ClassDef):
                        continue
                    if node.name.startswith("_"):
                        continue
                    has_doc = (
                        node.body
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(
                            node.body[0].value, ast.Constant
                        )
                        and isinstance(
                            node.body[0].value.value, str
                        )
                    )
                    if not has_doc:
                        rel = os.path.relpath(fpath, SRC_DIR)
                        missing.append(f"{rel}::{node.name}")
        assert missing == [], (
            f"Public classes without docstrings: {missing}"
        )


class TestRound20Regression:
    """All source files compile after round 20 changes."""

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
                    errors.append(
                        os.path.relpath(fpath, SRC_DIR)
                    )
        assert errors == [], f"Syntax errors: {errors}"
