"""
Gap-closure tests — Round 12.

Gaps addressed:
43. 1 ``== False`` comparison → ``not x``
44. 24 ``open(..., 'r')`` without ``encoding=`` → added ``encoding='utf-8'``
45. 5 missing ``super().__init__()`` in delivery adapter subclasses
"""

import ast
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")


# ===================================================================
# Gap 43 — no == True / == False comparisons
# ===================================================================
class TestNoBoolEqComparison:
    """``== True`` and ``== False`` should use ``is`` or truthiness."""

    def test_no_eq_true_false(self):
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
                    if isinstance(node, ast.Compare):
                        for op, comp in zip(node.ops, node.comparators):
                            if isinstance(op, (ast.Eq, ast.NotEq)):
                                if isinstance(comp, ast.Constant) and isinstance(comp.value, bool):
                                    rel = os.path.relpath(fpath, SRC_DIR)
                                    violations.append(
                                        f"{rel}:{node.lineno}"
                                    )
        assert violations == [], (
            f"== True/False comparisons: {violations}"
        )


# ===================================================================
# Gap 44 — open('r') must specify encoding
# ===================================================================
class TestReadOpenHasEncoding:
    """Every ``open(..., 'r')`` call must include ``encoding=``."""

    def test_no_read_open_without_encoding(self):
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
                            r"\bopen\s*\([^)]*['\"]r['\"]", s
                        ) and "encoding" not in s:
                            if "'rb'" in s or '"rb"' in s:
                                continue
                            rel = os.path.relpath(fpath, SRC_DIR)
                            violations.append(f"{rel}:{i}")
        assert violations == [], (
            f"open('r') without encoding: {violations}"
        )


# ===================================================================
# Gap 45 — delivery adapter subclasses call super().__init__()
# ===================================================================
class TestDeliveryAdaptersSuperInit:
    """All BaseDeliveryAdapter subclasses must call super().__init__()."""

    def test_delivery_adapters_call_super(self):
        fpath = os.path.join(SRC_DIR, "delivery_adapters.py")
        with open(fpath, encoding='utf-8') as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            parent_names = [
                b.id for b in node.bases if isinstance(b, ast.Name)
            ]
            if "BaseDeliveryAdapter" not in parent_names:
                continue
            for child in node.body:
                if not (
                    isinstance(child, ast.FunctionDef)
                    and child.name == "__init__"
                ):
                    continue
                calls_super = any(
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "__init__"
                    and isinstance(sub.func.value, ast.Call)
                    and isinstance(sub.func.value.func, ast.Name)
                    and sub.func.value.func.id == "super"
                    for sub in ast.walk(child)
                )
                assert calls_super, (
                    f"{node.name}.__init__ does not call super().__init__()"
                )


# ===================================================================
# Meta: comprehensive regression for all 25 categories
# ===================================================================
class TestAllCategories:
    """Verify all 25 gap categories remain at zero."""

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
                    if isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ):
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

    def test_no_write_open_without_encoding(self):
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
                            pytest.fail(
                                f"write-open no encoding {rel}:{i}"
                            )
