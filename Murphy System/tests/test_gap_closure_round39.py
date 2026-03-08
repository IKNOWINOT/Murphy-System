"""
Gap-Closure Verification — Round 39

Final verification categories 66-80 (total 80 verified categories):
1. Custom exceptions properly inherit from Error/Exception
2. pyproject.toml has all required sections
3. README has all required sections (Quick Start, Architecture, License, Contributing, Installation)
4. GETTING_STARTED has all required sections
5. All source packages have test coverage
6. All README documentation links resolve to existing files
7. .gitignore has all standard Python patterns
"""

import ast
import os
import re

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
REPO_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))


class TestCustomExceptionHierarchy:
    """All custom Exception/Error classes inherit from proper base."""

    def test_exception_hierarchy(self):
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
                    if isinstance(node, ast.ClassDef):
                        if node.name.endswith(("Error", "Exception")):
                            has_exc = False
                            for base in node.bases:
                                name = ""
                                if isinstance(base, ast.Name):
                                    name = base.id
                                elif isinstance(base, ast.Attribute):
                                    name = base.attr
                                if "Error" in name or "Exception" in name:
                                    has_exc = True
                            if not has_exc and node.bases:
                                found.append(
                                    f"{path}:{node.lineno}: {node.name}"
                                )
        assert found == [], (
            "Bad exception hierarchy:\n" + "\n".join(found)
        )


class TestPyprojectCompleteness:
    """pyproject.toml has all required sections."""

    def test_required_sections(self):
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]

        pyproj_path = os.path.join(PROJECT_ROOT, "pyproject.toml")
        with open(pyproj_path, "rb") as f:
            data = tomllib.load(f)
        for key in ("project", "build-system"):
            assert key in data, f"Missing section: {key}"
        proj = data["project"]
        for key in ("name", "version", "description", "requires-python"):
            assert key in proj, f"Missing project key: {key}"


class TestReadmeRequiredSections:
    """README has all required sections for a professional repo."""

    REQUIRED = [
        "Quick Start",
        "Installation",
        "Architecture",
        "License",
        "Contributing",
    ]

    def test_all_sections_present(self):
        readme_path = os.path.join(REPO_ROOT, "README.md")
        with open(readme_path, encoding="utf-8") as f:
            content = f.read().lower()
        missing = [s for s in self.REQUIRED if s.lower() not in content]
        assert missing == [], f"README missing: {missing}"


class TestGettingStartedSections:
    """GETTING_STARTED.md has all required sections."""

    REQUIRED = ["Prerequisites", "Install", "CLI", "Web", "API"]

    def test_all_sections_present(self):
        gs_path = os.path.join(REPO_ROOT, "GETTING_STARTED.md")
        with open(gs_path, encoding="utf-8") as f:
            content = f.read().lower()
        missing = [s for s in self.REQUIRED if s.lower() not in content]
        assert missing == [], f"GETTING_STARTED missing: {missing}"


class TestAllPackagesTested:
    """Every source package has at least one reference in tests."""

    def test_all_packages_covered(self):
        src_packages = set()
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            rel = os.path.relpath(root, SRC_DIR)
            if rel != ".":
                pkg = rel.split(os.sep)[0]
                src_packages.add(pkg)
        test_dir = os.path.join(PROJECT_ROOT, "tests")
        test_content = ""
        for root, _, files in os.walk(test_dir):
            for fn in files:
                if fn.endswith(".py"):
                    with open(os.path.join(root, fn), encoding="utf-8") as f:
                        test_content += f.read()
        untested = [
            p
            for p in src_packages
            if p not in test_content and p.replace("_", "") not in test_content
        ]
        assert untested == [], (
            "Untested packages:\n" + "\n".join(sorted(untested))
        )


class TestReadmeDocLinksExist:
    """All relative links in README resolve to existing files."""

    def test_relative_links_exist(self):
        readme_path = os.path.join(REPO_ROOT, "README.md")
        with open(readme_path, encoding="utf-8") as f:
            content = f.read()
        # Match both <angle bracket> and standard (url) links
        angle_re = re.compile(r"\[([^\]]+)\]\(<([^>]+)>\)")
        std_re = re.compile(r"\[([^\]]+)\]\((?!http)(?!#)([^)<>]+)\)")
        broken = []
        seen = set()
        for pattern in (angle_re, std_re):
            for text, link in pattern.findall(content):
                link_path = link.split("#")[0].replace("%20", " ").strip()
                if not link_path or link_path.startswith("http"):
                    continue
                if link_path in seen:
                    continue
                seen.add(link_path)
                full = os.path.join(REPO_ROOT, link_path)
                if not os.path.exists(full):
                    broken.append(f"[{text}]({link})")
        assert broken == [], (
            "Broken README links:\n" + "\n".join(broken)
        )


class TestGitignoreCompleteness:
    """.gitignore has all standard Python patterns."""

    REQUIRED_PATTERNS = [
        "__pycache__",
        "*.pyc",
        ".env",
        "*.egg-info",
    ]

    def test_required_patterns(self):
        gitignore_path = os.path.join(REPO_ROOT, ".gitignore")
        with open(gitignore_path, encoding="utf-8") as f:
            content = f.read()
        missing = [p for p in self.REQUIRED_PATTERNS if p not in content]
        assert missing == [], f".gitignore missing: {missing}"
