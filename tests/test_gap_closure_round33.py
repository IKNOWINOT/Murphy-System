"""
Gap-Closure Verification — Round 33

Extends the audit with 5 additional scan categories (11–15):
1. Zero duplicate function/method definitions in any scope
2. Zero duplicate top-level imports in any module
3. Zero hardcoded secrets in source code
4. Zero open() calls missing encoding= for text mode
5. Professional repo file completeness (LICENSE, CONTRIBUTING, SECURITY, etc.)
6. Zero broken documentation links in active (non-archive) markdown
7. All 517+ source modules import without error
"""

import ast
import os
import re
import sys
import urllib.parse

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
REPO_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))


class TestZeroDuplicateFunctions:
    """No duplicate function/method definitions in any scope."""

    def test_no_duplicate_functions_in_src(self):
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
                    if isinstance(node, (ast.ClassDef, ast.Module)):
                        seen: dict[str, int] = {}
                        for item in node.body:
                            if isinstance(
                                item, (ast.FunctionDef, ast.AsyncFunctionDef)
                            ):
                                if item.name in seen:
                                    found.append(
                                        f"{path}:{item.lineno}: {item.name}() "
                                        f"also at line {seen[item.name]}"
                                    )
                                seen[item.name] = item.lineno
        assert found == [], "Duplicate functions:\n" + "\n".join(found)


class TestZeroDuplicateImports:
    """No duplicate top-level imports in any module."""

    def test_no_duplicate_imports_in_src(self):
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
                imports: list[str] = []
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            name = alias.asname or alias.name
                            if name in imports:
                                found.append(f"{path}:{node.lineno}: {name}")
                            imports.append(name)
                    elif isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            name = alias.asname or alias.name
                            if name in imports:
                                found.append(f"{path}:{node.lineno}: {name}")
                            imports.append(name)
        assert found == [], "Duplicate imports:\n" + "\n".join(found)


class TestZeroHardcodedSecrets:
    """No hardcoded passwords/API keys in source code."""

    def test_no_hardcoded_secrets_in_src(self):
        secret_re = re.compile(
            r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']',
            re.IGNORECASE,
        )
        safe_terms = [
            "test", "mock", "example", "dummy", "placeholder",
            "changeme", "none", '""', "''", "os.environ", "getenv",
            "settings.", "config.", "env",
        ]
        # Enum-style UPPER_CASE = "value" assignments are labels, not secrets
        enum_label_re = re.compile(r"^[A-Z][A-Z_0-9]+\s*=\s*[\"']")
        found = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                with open(path, encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if secret_re.search(line):
                            stripped = line.strip()
                            if any(x in stripped.lower() for x in safe_terms):
                                continue
                            if enum_label_re.match(stripped):
                                continue
                            found.append(f"{path}:{i}: {stripped[:80]}")
        assert found == [], "Hardcoded secrets:\n" + "\n".join(found)


class TestOpenWithEncoding:
    """All text-mode open() calls specify encoding=."""

    def test_no_open_without_encoding_in_src(self):
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
                    if isinstance(node, ast.Call) and isinstance(
                        node.func, ast.Name
                    ):
                        if node.func.id != "open":
                            continue
                        keywords = {kw.arg: kw for kw in node.keywords}
                        args = node.args
                        mode_val = ""
                        if len(args) >= 2 and isinstance(args[1], ast.Constant):
                            mode_val = str(args[1].value)
                        elif "mode" in keywords and isinstance(
                            keywords["mode"].value, ast.Constant
                        ):
                            mode_val = str(keywords["mode"].value.value)
                        if "b" in mode_val:
                            continue
                        if "encoding" not in keywords:
                            found.append(f"{path}:{node.lineno}")
        assert found == [], "open() without encoding:\n" + "\n".join(found)


class TestProfessionalRepoFiles:
    """All professional repo files exist and are non-empty."""

    @pytest.mark.parametrize(
        "filename,base",
        [
            ("LICENSE", REPO_ROOT),
            ("README.md", REPO_ROOT),
            ("CHANGELOG.md", REPO_ROOT),
            ("CONTRIBUTING.md", REPO_ROOT),
            ("SECURITY.md", REPO_ROOT),
            (".gitignore", REPO_ROOT),
            ("pyproject.toml", PROJECT_ROOT),
            ("pytest.ini", PROJECT_ROOT),
            ("requirements.txt", PROJECT_ROOT),
        ],
    )
    def test_required_file_exists(self, filename, base):
        path = os.path.join(base, filename)
        assert os.path.isfile(path), f"Missing: {filename}"
        assert os.path.getsize(path) > 0, f"Empty: {filename}"


class TestActiveDocLinks:
    """No broken markdown links in active (non-archive) documentation."""

    def test_no_broken_links_outside_archive(self):
        broken = []
        for dirpath, dirs, files in os.walk(REPO_ROOT):
            if ".git" in dirpath or "__pycache__" in dirpath or "/archive" in dirpath:
                continue
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                base = os.path.dirname(path)
                for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", content):
                    link = match.group(2)
                    if link.startswith(("http", "#", "mailto:")):
                        continue
                    link_clean = urllib.parse.unquote(link.strip("<>").split("#")[0])
                    target = os.path.normpath(os.path.join(base, link_clean))
                    if not os.path.exists(target):
                        broken.append(
                            f"{path}: [{match.group(1)}]({link})"
                        )
        assert broken == [], "Broken links:\n" + "\n".join(broken)


class TestFullImportSweep:
    """All source modules import without error."""

    def test_all_modules_importable(self):
        sys.path.insert(0, SRC_DIR)
        optional = {
            "fastapi", "matplotlib", "torch", "textual",
            "uvicorn", "openai", "anthropic", "transformers",
        }
        failed = []
        import importlib

        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py") or fn == "__init__.py":
                    continue
                path = os.path.join(root, fn)
                mod = path[len(SRC_DIR) + 1 :].replace(os.sep, ".").replace(".py", "")
                try:
                    importlib.import_module(mod)
                except Exception as exc:
                    msg = str(exc)[:150]
                    if not any(d in msg for d in optional):
                        failed.append(f"{mod}: {type(exc).__name__}: {msg}")
        assert failed == [], "Import failures:\n" + "\n".join(failed)
