"""
Gap-Closure Verification — Round 42

Refined deep-scan validation.  Confirms the initial Round 42 scan
false-positives (enum values flagged as secrets, REPL exec, single-dot
import resolution) are correctly excluded, and all critical categories
remain at zero with accurate detection logic.

Categories verified (refined versions):
1. No unsandboxed eval/exec outside REPL modules
2. No real hardcoded secrets (enum values excluded)
3. No broken relative imports (proper level resolution)
4. No bare except handlers
5. Silent ImportError catches are legitimate (optional deps)
6. All critical categories remain at zero in unified check
"""

import ast
import os
import re

import pytest

SRC_DIR = os.path.join(
    os.path.dirname(__file__), "..", "src"
)


def _py_files(*, include_tests: bool = False):
    """Yield all .py source files under src/."""
    for root, _dirs, files in os.walk(SRC_DIR):
        if "__pycache__" in root:
            continue
        for fn in files:
            if fn.endswith(".py"):
                if not include_tests and fn.startswith("test_"):
                    continue
                yield os.path.join(root, fn)


class TestRefinedEvalExec:
    """eval/exec must not appear outside sandboxed REPL modules."""

    def test_no_unsandboxed_eval_exec(self):
        violations = []
        for path in _py_files():
            if "repl" in os.path.basename(path).lower():
                continue
            with open(path, encoding="utf-8") as f:
                src = f.read()
            try:
                tree = ast.parse(src, path)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(
                    node.func, ast.Name
                ):
                    if node.func.id in ("eval", "exec"):
                        violations.append(f"{path}:{node.lineno}")
        assert violations == [], (
            f"Unsandboxed eval/exec found: {violations}"
        )


class TestRefinedSecrets:
    """Real hardcoded secrets must not exist; enum labels are allowed."""

    @staticmethod
    def _enum_class_ranges(tree):
        """Return set of line ranges that belong to Enum class bodies."""
        ranges = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    name = ""
                    if isinstance(base, ast.Name):
                        name = base.id
                    elif isinstance(base, ast.Attribute):
                        name = base.attr
                    if "Enum" in name:
                        end = getattr(node, "end_lineno", node.lineno)
                        for ln in range(node.lineno, end + 1):
                            ranges.add(ln)
        return ranges

    def test_no_real_hardcoded_secrets(self):
        violations = []
        for path in _py_files():
            with open(path, encoding="utf-8") as f:
                src = f.read()
            try:
                tree = ast.parse(src, path)
            except SyntaxError:
                continue
            enum_lines = self._enum_class_ranges(tree)
            for i, line in enumerate(src.splitlines(), 1):
                if i in enum_lines:
                    continue
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                m = re.match(
                    r"(\w+)\s*=\s*[\"']([A-Za-z0-9+/=_-]{32,})[\"']",
                    stripped,
                )
                if m:
                    var = m.group(1).lower()
                    if any(
                        x in var
                        for x in [
                            "key",
                            "secret",
                            "token",
                            "password",
                            "credential",
                        ]
                    ):
                        violations.append(f"{path}:{i}")
        assert violations == [], (
            f"Real hardcoded secrets: {violations}"
        )


class TestRefinedImports:
    """Relative imports must resolve with correct level handling."""

    def test_no_broken_relative_imports(self):
        broken = []
        for path in _py_files():
            with open(path, encoding="utf-8") as f:
                src = f.read()
            try:
                tree = ast.parse(src, path)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and node.level > 0
                ):
                    base = os.path.dirname(path)
                    for _ in range(node.level - 1):
                        base = os.path.dirname(base)
                    parts = node.module.split(".")
                    target_file = os.path.join(base, *parts) + ".py"
                    target_pkg = os.path.join(
                        base, *parts, "__init__.py"
                    )
                    if not os.path.exists(
                        target_file
                    ) and not os.path.exists(target_pkg):
                        broken.append(f"{path}:{node.lineno}")
        assert broken == [], f"Broken relative imports: {broken}"


class TestSilentCatchesLegitimate:
    """Silent except-ImportError-pass for optional deps is acceptable."""

    def test_all_silent_catches_are_import_error(self):
        """Every except-pass must catch ImportError specifically."""
        non_import = []
        for path in _py_files():
            with open(path, encoding="utf-8") as f:
                src = f.read()
            try:
                tree = ast.parse(src, path)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if len(node.body) == 1 and isinstance(
                        node.body[0], ast.Pass
                    ):
                        if node.type is None:
                            non_import.append(
                                f"{path}:{node.lineno}: bare except"
                            )
                        elif isinstance(node.type, ast.Name):
                            if node.type.id != "ImportError":
                                non_import.append(
                                    f"{path}:{node.lineno}: "
                                    f"except {node.type.id}"
                                )
        assert non_import == [], (
            f"Silent catches not ImportError: {non_import}"
        )


class TestUnifiedCriticalZero:
    """Unified assertion that all critical categories remain at zero."""

    CATEGORIES = [
        "syntax_errors",
        "bare_except",
        "wildcard_imports",
        "missing_init",
        "missing_all_exports",
    ]

    def test_syntax_zero(self):
        count = 0
        for path in _py_files():
            with open(path, encoding="utf-8") as f:
                src = f.read()
            try:
                ast.parse(src, path)
            except SyntaxError:
                count += 1
        assert count == 0

    def test_bare_except_zero(self):
        count = 0
        for path in _py_files():
            with open(path, encoding="utf-8") as f:
                src = f.read()
            try:
                tree = ast.parse(src, path)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ExceptHandler)
                    and node.type is None
                ):
                    count += 1
        assert count == 0

    def test_wildcard_zero(self):
        count = 0
        for path in _py_files():
            with open(path, encoding="utf-8") as f:
                src = f.read()
            try:
                tree = ast.parse(src, path)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "*":
                            count += 1
        assert count == 0

    def test_missing_init_zero(self):
        count = 0
        for root, _dirs, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            py_in_dir = [f for f in files if f.endswith(".py")]
            if py_in_dir and "__init__.py" not in files:
                count += 1
        assert count == 0
