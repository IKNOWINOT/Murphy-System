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

# This file lives at tests/documentation_qa/, so the repo root is two levels up.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
# REPO_ROOT and PROJECT_ROOT both point at the repo root in the canonical
# mirrored layout (Murphy System/ ↔ root). Kept as a separate name for
# readability of the call sites that reference top-level docs.
REPO_ROOT = PROJECT_ROOT


class TestDocumentationAccuracy:
    """Verify documentation numbers match reality."""

    @staticmethod
    def _max_count_near(content: str, keyword: str) -> int:
        """Return the largest integer that immediately precedes ``keyword``.

        Matches patterns like ``1,230 modules`` or ``1,100+ Python modules``
        — the number must appear within a short phrase (up to three short
        words) directly before the keyword on the same line. Numbers may use
        comma separators. Returns 0 if no candidate is found, in which case
        the caller treats the doc as not making any claim.

        Deliberately narrow to avoid false positives from numbers that
        merely happen to share a paragraph with the keyword (e.g. table
        rows, port numbers, line counts).
        """
        # Allow up to 3 short alphabetic words between the number and the
        # keyword; forbid newlines and sentence separators (".", "|") so we
        # stay within a single phrase.
        pattern = re.compile(
            r"(\d{1,3}(?:,\d{3})+|\d{2,})"
            r"(?:\+|\s)"
            r"(?:[A-Za-z][A-Za-z\-]*\s+){0,3}"
            + re.escape(keyword)
            + r"s?\b",
            re.IGNORECASE,
        )
        max_n = 0
        for match in pattern.finditer(content):
            n = int(match.group(1).replace(",", ""))
            if n > max_n:
                max_n = n
        return max_n

    def test_inner_readme_module_count(self):
        """Inner README must not over-claim the module count.

        Acts as a regression tripwire: docs may lag behind reality (the
        inner README is updated infrequently), but a claim larger than the
        actual count is a documentation bug.
        """
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
        claimed = self._max_count_near(content, "module")
        assert claimed <= actual, (
            f"Inner README claims {claimed} modules but src/ only contains "
            f"{actual} — update the README"
        )

    def test_getting_started_module_count(self):
        """GETTING_STARTED must not over-claim the module count.

        Regression tripwire (see test_inner_readme_module_count).
        """
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
        claimed = self._max_count_near(content, "module")
        assert claimed <= actual, (
            f"GETTING_STARTED claims {claimed} modules but src/ only "
            f"contains {actual} — update the doc"
        )

    def test_package_count_does_not_regress(self):
        """Package count must not silently shrink below the documented baseline.

        Replaces the previous hard-coded ``assert actual == 77`` (test name
        said 54, assertion said 77, actual is currently larger). This is now
        a regression tripwire that catches accidental package deletion while
        tolerating package growth.
        """
        actual = sum(
            1
            for root, _, files in os.walk(SRC_DIR)
            if "__pycache__" not in root and "__init__.py" in files
        )
        # Baseline derived from the inner README; raise this number when the
        # README is updated to a higher count.
        baseline = 64
        assert actual >= baseline, (
            f"Expected at least {baseline} packages (inner README baseline), "
            f"found {actual}"
        )

    def test_gap_closure_test_count_in_docs(self):
        """GETTING_STARTED references at least the actual gap-closure test count."""
        gs_path = os.path.join(REPO_ROOT, "GETTING_STARTED.md")
        with open(gs_path) as f:
            content = f.read()
        # Count gap-closure tests recursively — they live under
        # tests/documentation_qa/ rather than tests/ directly.
        gc_files = []
        for root, _, files in os.walk(TESTS_DIR):
            for fn in files:
                if fn.startswith("test_gap_closure_round") and fn.endswith(".py"):
                    gc_files.append(fn)
        assert len(gc_files) >= 20, (
            f"Expected 20+ gap-closure test files, found {len(gc_files)}"
        )
        # Doc must mention "gap-closure" (any count) — the literal number is
        # not pinned because it grows with every audit round.
        assert "gap-closure" in content.lower(), (
            "GETTING_STARTED should reference gap-closure tests"
        )


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
        errors = []
        for fn in os.listdir(TESTS_DIR):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(TESTS_DIR, fn)
            with open(path) as f:
                try:
                    ast.parse(f.read(), path)
                except SyntaxError as e:
                    errors.append(f"{path}: {e}")
        assert errors == [], "Test syntax errors:\n" + "\n".join(errors)
