"""
Gap-Closure Verification — Round 38

Extends the audit with categories 51-65 (total 65 verified categories):
1. Zero deprecated ``logger.warn()`` calls (all use ``logger.warning()``)
2. Zero ``eval()`` in production code
3. Zero ``exec()`` outside REPL sandbox
4. Zero ``os.system()`` calls (use ``subprocess`` instead)
5. Zero hardcoded secrets/tokens in source
6. All ``__init__.py`` files define ``__all__``
7. All test files contain at least one test class or function
8. All 9 professional repo files present
"""

import ast
import os
import re

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
REPO_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))


class TestZeroDeprecatedLoggerWarn:
    """No deprecated logger.warn() calls — must use logger.warning()."""

    def test_no_logger_warn(self):
        found = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                with open(path, encoding="utf-8") as f:
                    source = f.read()
                try:
                    tree = ast.parse(source, path)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "warn"
                        and isinstance(node.func.value, ast.Name)
                        and "log" in node.func.value.id.lower()
                    ):
                        found.append(f"{path}:{node.lineno}")
        assert found == [], (
            "Deprecated logger.warn() found:\n" + "\n".join(found)
        )


class TestZeroEvalInProduction:
    """No eval() in production source code."""

    def test_no_eval(self):
        found = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py") or fn.lower().startswith("test_"):
                    continue
                path = os.path.join(root, fn)
                with open(path, encoding="utf-8") as f:
                    source = f.read()
                try:
                    tree = ast.parse(source, path)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "eval"
                    ):
                        found.append(f"{path}:{node.lineno}")
        assert found == [], "eval() found:\n" + "\n".join(found)


class TestZeroExecOutsideREPL:
    """No exec() outside the REPL sandbox."""

    def test_no_exec_outside_repl(self):
        found = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                if fn.lower().startswith("test_") or "murphy_repl" in fn:
                    continue
                path = os.path.join(root, fn)
                with open(path, encoding="utf-8") as f:
                    source = f.read()
                try:
                    tree = ast.parse(source, path)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "exec"
                    ):
                        found.append(f"{path}:{node.lineno}")
        assert found == [], "exec() outside REPL:\n" + "\n".join(found)


class TestZeroOsSystemCalls:
    """No os.system() calls — use subprocess instead."""

    def test_no_os_system(self):
        found = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py") or fn.lower().startswith("test_"):
                    continue
                path = os.path.join(root, fn)
                with open(path, encoding="utf-8") as f:
                    source = f.read()
                try:
                    tree = ast.parse(source, path)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "system"
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "os"
                    ):
                        found.append(f"{path}:{node.lineno}")
        assert found == [], "os.system() found:\n" + "\n".join(found)


class TestZeroHardcodedSecrets:
    """No hardcoded API keys, tokens, or passwords in source."""

    def test_no_hardcoded_secrets(self):
        secret_re = re.compile(
            r'(?:api[_-]?key|secret|token|password)\s*=\s*'
            r'["\'][a-zA-Z0-9+/=]{20,}["\']',
            re.I,
        )
        found = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py") or fn.lower().startswith("test_"):
                    continue
                path = os.path.join(root, fn)
                with open(path, encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if secret_re.search(line) and not line.strip().startswith("#"):
                            found.append(f"{path}:{i}")
        assert found == [], "Hardcoded secrets:\n" + "\n".join(found)


class TestAllInitFilesHaveAll:
    """Every __init__.py defines __all__."""

    def test_init_files_have_all(self):
        missing = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            if "__init__.py" in files:
                init_path = os.path.join(root, "__init__.py")
                with open(init_path, encoding="utf-8") as f:
                    content = f.read()
                if "__all__" not in content:
                    missing.append(init_path)
        assert missing == [], (
            "__init__.py without __all__:\n" + "\n".join(missing)
        )


class TestAllTestFilesHaveTests:
    """Every test_*.py file contains at least one test."""

    def test_all_test_files_have_tests(self):
        bad = []
        test_dir = os.path.join(PROJECT_ROOT, "tests")
        for root, _, files in os.walk(test_dir):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.startswith("test_") or not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                try:
                    tree = ast.parse(content, path)
                except SyntaxError:
                    bad.append(f"{path}: SyntaxError")
                    continue
                has_test = any(
                    (isinstance(n, ast.ClassDef) and n.name.startswith("Test"))
                    or (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_"))
                    for n in ast.walk(tree)
                )
                if not has_test:
                    bad.append(f"{path}: no test class/function")
        assert bad == [], "Test files without tests:\n" + "\n".join(bad)


class TestProfessionalRepoFiles:
    """All 9 professional repo files are present."""

    REQUIRED_FILES = [
        ("README.md", REPO_ROOT),
        ("CHANGELOG.md", REPO_ROOT),
        ("LICENSE", REPO_ROOT),
        ("CONTRIBUTING.md", REPO_ROOT),
        ("SECURITY.md", REPO_ROOT),
        ("CODE_OF_CONDUCT.md", REPO_ROOT),
        (".gitignore", REPO_ROOT),
        ("GETTING_STARTED.md", REPO_ROOT),
        ("pyproject.toml", PROJECT_ROOT),
    ]

    def test_all_professional_files_exist(self):
        missing = []
        for name, base in self.REQUIRED_FILES:
            if not os.path.isfile(os.path.join(base, name)):
                missing.append(name)
        assert missing == [], f"Missing: {', '.join(missing)}"
