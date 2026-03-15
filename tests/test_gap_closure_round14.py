"""
Gap-closure tests — Round 14.

Gaps addressed:
48. 70 f-strings without interpolation → converted to plain strings
"""

import ast
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")


class TestNoEmptyFstrings:
    """f-strings must contain at least one interpolation."""

    @staticmethod
    def _check_fstrings(node, is_format_spec=False):
        results = []
        if isinstance(node, ast.JoinedStr) and not is_format_spec:
            has_interpolation = any(
                isinstance(v, ast.FormattedValue) for v in node.values
            )
            if not has_interpolation:
                results.append(node.lineno)
        for child in ast.iter_child_nodes(node):
            child_is_spec = (
                isinstance(node, ast.FormattedValue)
                and child is node.format_spec
            )
            results.extend(
                TestNoEmptyFstrings._check_fstrings(child, child_is_spec)
            )
        return results

    def test_no_fstring_without_interpolation(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                hits = self._check_fstrings(tree)
                for lineno in hits:
                    rel = os.path.relpath(fpath, SRC_DIR)
                    violations.append(f"{rel}:{lineno}")
        assert violations == [], (
            f"f-strings without interpolation: {violations}"
        )


class TestRound14Regression:
    """Key regression checks."""

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

    def test_no_shadowed_builtins(self):
        shadowed = frozenset({
            "list", "dict", "set", "type", "id", "input", "map",
            "filter", "range", "hash", "format", "object", "int",
            "float", "str", "bool", "bytes", "tuple", "len",
        })
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ):
                        for arg in (
                            node.args.args
                            + node.args.posonlyargs
                            + node.args.kwonlyargs
                        ):
                            if arg.arg in shadowed:
                                rel = os.path.relpath(fpath, SRC_DIR)
                                violations.append(
                                    f"{rel}:{node.lineno}: '{arg.arg}'"
                                )
        assert violations == [], (
            f"Shadowed builtins: {violations}"
        )
