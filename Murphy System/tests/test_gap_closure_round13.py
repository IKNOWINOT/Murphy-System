"""
Gap-closure tests — Round 13.

Gaps addressed:
46. 8 shadowed Python builtins as parameter names (format → output_format, filter → doc_filter)
47. TODO/FIXME audit (tokenizer-based, template-aware)
"""

import ast
import io
import os
import re
import tokenize

import pytest


SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")

# Builtins that must not be used as parameter names
_SHADOWED_BUILTINS = frozenset({
    "list", "dict", "set", "type", "id", "input", "map", "filter",
    "range", "hash", "format", "object", "int", "float", "str",
    "bool", "bytes", "tuple", "len", "max", "min", "sum", "abs",
    "round", "sorted", "any", "all", "zip", "enumerate", "next",
    "iter", "open", "print", "repr", "dir", "vars",
})


class TestNoShadowedBuiltins:
    """No function/method parameter should shadow a Python builtin."""

    def test_no_shadowed_builtin_params(self):
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
                        all_args = (
                            node.args.args
                            + node.args.posonlyargs
                            + node.args.kwonlyargs
                        )
                        for arg in all_args:
                            if arg.arg in _SHADOWED_BUILTINS:
                                rel = os.path.relpath(fpath, SRC_DIR)
                                violations.append(
                                    f"{rel}:{node.lineno}: "
                                    f"'{arg.arg}' in {node.name}()"
                                )
        assert violations == [], (
            f"Parameters shadowing builtins: {violations}"
        )


class TestNoTodoInSource:
    """No TODO/FIXME/HACK/XXX comments in production source."""

    def test_no_todo_comments(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    source = open(fpath, encoding='utf-8').read()
                    tokens = list(
                        tokenize.generate_tokens(
                            io.StringIO(source).readline
                        )
                    )
                except (SyntaxError, tokenize.TokenError):
                    continue
                for tok in tokens:
                    if tok.type == tokenize.COMMENT:
                        if re.search(
                            r"\b(TODO|FIXME|HACK|XXX)\b",
                            tok.string,
                            re.I,
                        ):
                            rel = os.path.relpath(fpath, SRC_DIR)
                            violations.append(
                                f"{rel}:{tok.start[0]}: "
                                f"{tok.string.strip()[:60]}"
                            )
        assert violations == [], (
            f"TODO/FIXME comments in source: {violations}"
        )


class TestRound13Regression:
    """Key regression checks for round 13."""

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

    def test_no_silent_swallows(self):
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
                    if isinstance(node, ast.ExceptHandler):
                        if (
                            node.type
                            and isinstance(node.type, ast.Name)
                            and node.type.id == "Exception"
                            and len(node.body) == 1
                            and isinstance(
                                node.body[0], (ast.Pass, ast.Continue)
                            )
                        ):
                            rel = os.path.relpath(fpath, SRC_DIR)
                            pytest.fail(
                                f"Silent swallow at {rel}:{node.lineno}"
                            )

    def test_no_unused_exception_vars(self):
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
                    if isinstance(node, ast.ExceptHandler) and node.name:
                        used = any(
                            isinstance(child, ast.Name)
                            and child.id == node.name
                            and (
                                child.lineno != node.lineno
                                or child.col_offset != node.col_offset
                            )
                            for child in ast.walk(node)
                        )
                        if not used:
                            rel = os.path.relpath(fpath, SRC_DIR)
                            pytest.fail(
                                f"Unused exc var at {rel}:{node.lineno}"
                            )
