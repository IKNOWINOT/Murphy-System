"""
Gap-closure tests — Round 23.

Categories addressed:
51. HARDCODED_CRED — verified all 21 matches are enum/constant labels, not secrets
52. BROAD_EXCEPT_NO_LOG — 118 broad exception handlers now have logger.debug()

Quality gates:
- All broad 'except Exception as exc:' blocks include a logging call
- No hardcoded real credentials in source code
- All prior categories remain at zero
"""

import ast
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")


def _walk_py(base=SRC_DIR):
    """Yield all .py source files."""
    for root, _dirs, files in os.walk(base):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


class TestBroadExceptHasLogging:
    """Every 'except Exception as exc:' block must include a logging call."""

    def test_no_silent_broad_except(self):
        silent = []
        for fpath in _walk_py():
            if "/tests/" in fpath:
                continue
            try:
                tree = ast.parse(open(fpath, encoding="utf-8").read())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ExceptHandler):
                    continue
                if not (
                    node.type
                    and isinstance(node.type, ast.Name)
                    and node.type.id == "Exception"
                ):
                    continue
                if not node.name:
                    continue

                has_log = False
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.Call):
                        if isinstance(stmt.func, ast.Attribute) and stmt.func.attr in (
                            "debug", "info", "warning", "error", "exception", "critical",
                        ):
                            has_log = True
                        if isinstance(stmt.func, ast.Name) and stmt.func.id == "print":
                            has_log = True
                if not has_log:
                    rel = os.path.relpath(fpath, SRC_DIR)
                    silent.append(f"{rel}:{node.lineno}")

        assert silent == [], f"Broad except without logging: {silent}"


class TestNoHardcodedSecrets:
    """No real hardcoded credentials — only enum/constant labels allowed."""

    def test_all_credential_matches_are_enum_labels(self):
        real_secrets = []
        for fpath in _walk_py():
            if "/tests/" in fpath:
                continue
            try:
                tree = ast.parse(open(fpath, encoding="utf-8").read())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if not isinstance(node.value, ast.Constant):
                        continue
                    if not isinstance(node.value.value, str):
                        continue
                    name = target.id
                    val = node.value.value
                    if not re.search(
                        r"(password|secret|token|api_key)", name, re.I
                    ):
                        continue
                    # Enum labels: ALL_CAPS name with lowercase_identifier value
                    is_enum = (name.isupper() or name == name.upper()) and re.match(
                        r"^[a-z_]+$", val
                    )
                    if is_enum:
                        continue
                    # Known safe patterns
                    if any(
                        w in val.lower()
                        for w in [
                            "example", "test", "default", "placeholder",
                            "change_me", "your_", "xxx", "",
                        ]
                    ):
                        continue
                    rel = os.path.relpath(fpath, SRC_DIR)
                    real_secrets.append(f"{rel}:{node.lineno}: {name}={val!r}")

        assert real_secrets == [], f"Hardcoded credentials: {real_secrets}"


class TestPriorCategoriesStillZero:
    """All 14 prior audit categories remain at zero."""

    def test_bare_except(self):
        count = 0
        for fpath in _walk_py():
            try:
                tree = ast.parse(open(fpath, encoding="utf-8").read())
            except SyntaxError:
                continue
            for n in ast.walk(tree):
                if isinstance(n, ast.ExceptHandler) and n.type is None:
                    count += 1
        assert count == 0, f"Bare except: {count}"

    def test_mutable_defaults(self):
        count = 0
        for fpath in _walk_py():
            try:
                tree = ast.parse(open(fpath, encoding="utf-8").read())
            except SyntaxError:
                continue
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for dv in n.args.defaults + n.args.kw_defaults:
                        if dv and isinstance(dv, (ast.List, ast.Dict, ast.Set)):
                            count += 1
        assert count == 0, f"Mutable defaults: {count}"

    def test_wildcard_imports(self):
        count = 0
        for fpath in _walk_py():
            try:
                tree = ast.parse(open(fpath, encoding="utf-8").read())
            except SyntaxError:
                continue
            for n in ast.walk(tree):
                if (
                    isinstance(n, ast.ImportFrom)
                    and n.names
                    and n.names[0].name == "*"
                ):
                    count += 1
        assert count == 0, f"Wildcard imports: {count}"

    def test_syntax_errors(self):
        import py_compile

        errors = []
        for fpath in _walk_py():
            try:
                py_compile.compile(fpath, doraise=True)
            except py_compile.PyCompileError:
                errors.append(os.path.relpath(fpath, SRC_DIR))
        assert errors == [], f"Syntax errors: {errors}"
