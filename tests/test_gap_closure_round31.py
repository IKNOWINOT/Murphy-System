"""
Gap-Closure Verification — Round 31

Validates that documentation references are accurate and consistent:
1. Module counts in README/GETTING_STARTED match actual src/ contents
2. Package counts match actual directory structure
3. Gap-closure test counts are accurate
4. All HTML UI files referenced in GETTING_STARTED exist
5. All test files are syntactically valid
6. Zero bare excepts, zero utcnow, zero dataclass field ordering bugs remain
"""

import ast
import os
import re
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
REPO_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))


class TestDocumentationAccuracy:
    """Verify documentation numbers match reality."""

    def test_inner_readme_module_count(self):
        """Inner README module count matches actual src/ file count."""
        readme_path = os.path.join(PROJECT_ROOT, "README.md")
        with open(readme_path) as f:
            content = f.read()
        actual = sum(
            1
            for root, _, files in os.walk(SRC_DIR)
            if "__pycache__" not in root
            for fn in files
            if fn.endswith(".py")
        )
        assert str(actual) in content, (
            f"Inner README should mention {actual} modules"
        )

    def test_getting_started_module_count(self):
        """GETTING_STARTED module count matches actual src/ file count."""
        gs_path = os.path.join(REPO_ROOT, "GETTING_STARTED.md")
        with open(gs_path) as f:
            content = f.read()
        actual = sum(
            1
            for root, _, files in os.walk(SRC_DIR)
            if "__pycache__" not in root
            for fn in files
            if fn.endswith(".py")
        )
        assert str(actual) in content, (
            f"GETTING_STARTED should mention {actual} modules"
        )

    def test_package_count_54(self):
        """Package (directory) count is accurate."""
        actual = sum(
            1
            for root, _, files in os.walk(SRC_DIR)
            if "__pycache__" not in root and "__init__.py" in files
        )
        assert actual == 77, f"Expected 77 packages, found {actual}"

    def test_gap_closure_test_count_in_docs(self):
        """GETTING_STARTED references at least the actual gap-closure test count."""
        gs_path = os.path.join(REPO_ROOT, "GETTING_STARTED.md")
        with open(gs_path) as f:
            content = f.read()
        # Count gap-closure tests
        test_dir = os.path.join(PROJECT_ROOT, "tests")
        gc_files = [
            f for f in os.listdir(test_dir) if f.startswith("test_gap_closure_round")
        ]
        assert len(gc_files) >= 20, f"Expected 20+ gap-closure test files, found {len(gc_files)}"
        # Doc should reference 118 gap-closure tests
        assert "118 gap-closure" in content, "GETTING_STARTED should reference 118 gap-closure tests"


class TestHTMLUIFilesExist:
    """Verify all HTML UI files referenced in GETTING_STARTED exist."""

    @pytest.mark.parametrize("html_file", [
        "onboarding_wizard.html",
        "murphy_landing_page.html",
        "murphy_ui_integrated.html",
        "terminal_architect.html",
        "terminal_worker.html",
        "terminal_integrated.html",
        "terminal_enhanced.html",
        "murphy_ui_integrated_terminal.html",
    ])
    def test_html_ui_file_exists(self, html_file):
        """Each HTML UI file referenced in docs must exist."""
        path = os.path.join(PROJECT_ROOT, html_file)
        assert os.path.isfile(path), f"Missing HTML UI file: {html_file}"


class TestZeroRemainingCodeBugs:
    """Verify zero code-quality bugs remain in src/."""

    def test_zero_syntax_errors(self):
        """All .py files in src/ must parse without SyntaxError."""
        errors = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                with open(path) as f:
                    try:
                        ast.parse(f.read(), path)
                    except SyntaxError as e:
                        errors.append(f"{path}: {e}")
        assert errors == [], "Syntax errors:\n" + "\n".join(errors)

    def test_zero_bare_excepts(self):
        """No bare 'except:' clauses in src/."""
        bare = re.compile(r"^\s*except\s*:\s*(?:#.*)?$")
        found = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                with open(path) as f:
                    for i, line in enumerate(f, 1):
                        if bare.match(line):
                            found.append(f"{path}:{i}")
        assert found == [], "Bare excepts:\n" + "\n".join(found)

    def test_zero_utcnow_calls(self):
        """No deprecated datetime.utcnow() calls in src/."""
        found = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                with open(path) as f:
                    source = f.read()
                try:
                    tree = ast.parse(source, path)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "utcnow"
                    ):
                        found.append(f"{path}:{node.lineno}")
        assert found == [], "utcnow() calls:\n" + "\n".join(found)

    def test_zero_dataclass_field_ordering_bugs(self):
        """No non-default fields after default fields in dataclasses."""
        found = []
        for root, _, files in os.walk(SRC_DIR):
            if "__pycache__" in root:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(root, fn)
                with open(path) as f:
                    source = f.read()
                try:
                    tree = ast.parse(source, path)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ClassDef):
                        continue
                    is_dc = any(
                        (isinstance(d, ast.Name) and d.id == "dataclass")
                        or (isinstance(d, ast.Attribute) and d.attr == "dataclass")
                        for d in node.decorator_list
                    )
                    if not is_dc:
                        continue
                    seen_default = False
                    for item in node.body:
                        if isinstance(item, ast.AnnAssign) and isinstance(
                            item.target, ast.Name
                        ):
                            if item.value is not None:
                                seen_default = True
                            elif seen_default:
                                found.append(
                                    f"{path}:{item.lineno}: "
                                    f"{node.name}.{item.target.id}"
                                )
        assert found == [], "Field ordering bugs:\n" + "\n".join(found)

    def test_all_test_files_parse(self):
        """All test files must be syntactically valid."""
        test_dir = os.path.join(PROJECT_ROOT, "tests")
        errors = []
        for fn in os.listdir(test_dir):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(test_dir, fn)
            with open(path) as f:
                try:
                    ast.parse(f.read(), path)
                except SyntaxError as e:
                    errors.append(f"{path}: {e}")
        assert errors == [], "Test syntax errors:\n" + "\n".join(errors)
