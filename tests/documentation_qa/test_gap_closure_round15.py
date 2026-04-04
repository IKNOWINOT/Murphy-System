"""
Gap-closure tests — Round 15.

Gaps addressed:
49. 4 silent ``except ValueError/SyntaxError: pass`` → added ``logger.debug``
50. 1 ``__del__`` method → replaced with ``close()`` + context manager protocol
"""

import ast
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")


class TestNoSilentSpecificExceptPass:
    """Specific exception handlers must not silently ``pass``."""

    _EXPECTED_GUARDS = frozenset({
        "ImportError", "ModuleNotFoundError", "AttributeError",
        "TypeError", "NotImplementedError", "StopIteration",
    })

    def test_no_silent_specific_except_pass(self):
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
                    if isinstance(node, ast.ExceptHandler):
                        if (
                            node.type
                            and isinstance(node.type, ast.Name)
                            and node.type.id not in (
                                "Exception", "BaseException",
                                *self._EXPECTED_GUARDS,
                            )
                        ):
                            if (
                                len(node.body) == 1
                                and isinstance(node.body[0], ast.Pass)
                            ):
                                rel = os.path.relpath(fpath, SRC_DIR)
                                violations.append(
                                    f"{rel}:{node.lineno}: "
                                    f"except {node.type.id}: pass"
                                )
        assert violations == [], (
            f"Silent specific-except pass: {violations}"
        )


class TestNoDelMethod:
    """Classes should not use ``__del__``; use context managers instead."""

    def test_no_del_methods(self):
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
                                and child.name == "__del__"
                            ):
                                rel = os.path.relpath(fpath, SRC_DIR)
                                violations.append(
                                    f"{rel}:{child.lineno}: "
                                    f"{node.name}.__del__"
                                )
        assert violations == [], f"__del__ methods found: {violations}"


class TestComputeServiceContextManager:
    """ComputeService supports context manager protocol."""

    def test_has_close_and_context_manager(self):
        fpath = os.path.join(SRC_DIR, "compute_plane", "service.py")
        with open(fpath, encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ComputeService":
                method_names = {
                    child.name
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                assert "close" in method_names, "Missing close()"
                assert "__enter__" in method_names, "Missing __enter__"
                assert "__exit__" in method_names, "Missing __exit__"
                return
        pytest.fail("ComputeService class not found")
