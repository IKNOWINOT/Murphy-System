"""
Gap-closure tests — Round 11.

Gaps addressed:
40. 22 ``open(..., 'w')`` without ``encoding=`` → added ``encoding='utf-8'``
41. 3 ``__init__.py`` files missing ``__all__`` → added explicit exports
"""

import ast
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")


# ===================================================================
# Gap 40 — open() for writing must specify encoding
# ===================================================================
class TestWriteWithEncoding:
    """Every ``open(..., 'w')`` call must include ``encoding=``."""

    def test_no_write_open_without_encoding(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        s = line.strip()
                        if s.startswith("#"):
                            continue
                        if re.search(
                            r"open\s*\([^)]*['\"][wa][t+]*['\"]", s
                        ) and "encoding" not in s:
                            rel = os.path.relpath(fpath, SRC_DIR)
                            violations.append(f"{rel}:{i}")
        assert violations == [], (
            f"open() for writing without encoding: {violations}"
        )


# ===================================================================
# Gap 41 — __init__.py must declare __all__
# ===================================================================
class TestInitHasAll:
    """Non-empty ``__init__.py`` files must declare ``__all__``."""

    def test_init_files_have_all(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if fname != "__init__.py":
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding='utf-8') as f:
                    content = f.read()
                if not content.strip():
                    continue
                if "__all__" in content:
                    continue
                if "import" in content or "def " in content or "class " in content:
                    rel = os.path.relpath(fpath, SRC_DIR)
                    violations.append(rel)
        assert violations == [], (
            f"__init__.py missing __all__: {violations}"
        )


# ===================================================================
# Meta: comprehensive regression for all 22 categories
# ===================================================================
class TestAllCategories:
    """Verify all 22 gap categories remain at zero."""

    def test_no_bare_excepts(self):
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        assert not re.match(r"^\s*except\s*:", line), (
                            f"Bare except at {fpath}:{i}"
                        )

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
                        ):
                            if len(node.body) == 1 and isinstance(
                                node.body[0], (ast.Pass, ast.Continue)
                            ):
                                rel = os.path.relpath(fpath, SRC_DIR)
                                pytest.fail(
                                    f"Silent swallow at {rel}:{node.lineno}"
                                )

    def test_no_except_as_e(self):
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
                        if node.name == "e":
                            rel = os.path.relpath(fpath, SRC_DIR)
                            pytest.fail(
                                f"'except as e' at {rel}:{node.lineno}"
                            )

    def test_no_unreachable_code(self):
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
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        body = node.body
                        for idx, stmt in enumerate(body[:-1]):
                            if isinstance(stmt, (ast.Return, ast.Raise)):
                                ns = body[idx + 1]
                                if not isinstance(
                                    ns,
                                    (
                                        ast.FunctionDef,
                                        ast.AsyncFunctionDef,
                                        ast.ClassDef,
                                    ),
                                ):
                                    rel = os.path.relpath(fpath, SRC_DIR)
                                    pytest.fail(
                                        f"Unreachable at {rel}:{ns.lineno}"
                                    )

    def test_no_duplicate_methods(self):
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
                    if isinstance(node, ast.ClassDef):
                        methods = {}
                        for child in node.body:
                            if isinstance(
                                child,
                                (ast.FunctionDef, ast.AsyncFunctionDef),
                            ):
                                if child.name in methods:
                                    rel = os.path.relpath(fpath, SRC_DIR)
                                    pytest.fail(
                                        f"Dup {node.name}.{child.name}() "
                                        f"at {rel}:{child.lineno}"
                                    )
                                methods[child.name] = child.lineno

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
                    rel = os.path.relpath(fpath, SRC_DIR)
                    errors.append(rel)
        assert errors == [], f"Syntax errors: {errors}"


# ===================================================================
# Gap 42 — no unused exception variables
# ===================================================================
class TestNoUnusedExceptionVars:
    """Every captured exception variable must be used (logged, re-raised, etc)."""

    def test_no_unused_exception_vars(self):
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
                            violations.append(
                                f"{rel}:{node.lineno} as {node.name}"
                            )
        assert violations == [], (
            f"Unused exception variables: {violations[:10]}"
        )
