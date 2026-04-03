"""
Test: no sys.path hacks in src/ source files or test files.

Enforces the import strategy documented in CONTRIBUTING.md:
- Package imports use proper ``from src.xxx import yyy`` style
- sys.path is managed via pyproject.toml [tool.pytest.ini_options] pythonpath
  and ``pip install -e .`` for editable installs

Whitelisted exceptions (legitimate sys.path manipulation):
- src/integration_engine/sandbox_quarantine.py — process isolation sandboxing
- tests/integration/conftest.py — adds local mocks/ fixture directory
- strategic/ — standalone demo scripts, not imported as packages
- alembic/ — Alembic migration runner
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Root of the Murphy System project
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Individual files (relative to PROJECT_ROOT) that are allowed to keep
# sys.path manipulation for a legitimate technical reason.
_ALLOWED_FILES: frozenset[Path] = frozenset([
    PROJECT_ROOT / "src" / "integration_engine" / "sandbox_quarantine.py",
    PROJECT_ROOT / "src" / "murphy_action_engine.py",  # discover_actions() dynamic plugin loader
    PROJECT_ROOT / "tests" / "integration" / "conftest.py",
])

# Top-level directory names whose entire tree is exempt (standalone scripts)
_ALLOWED_TREE_ROOTS: frozenset[str] = frozenset(["strategic", "alembic"])

_SYS_PATH_PATTERN = re.compile(r"sys\.path\.(insert|append)\s*\(")


def _collect_violations(search_roots: list[Path]) -> list[str]:
    """Return relative paths of files that contain sys.path hacks."""
    violations: list[str] = []

    for search_root in search_roots:
        for py_file in sorted(search_root.rglob("*.py")):
            # Skip explicitly whitelisted files
            if py_file in _ALLOWED_FILES:
                continue
            # Skip whitelisted top-level trees
            try:
                rel = py_file.relative_to(PROJECT_ROOT)
            except ValueError:
                continue
            if rel.parts and rel.parts[0] in _ALLOWED_TREE_ROOTS:
                continue

            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            if _SYS_PATH_PATTERN.search(source):
                violations.append(str(rel))

    return violations


class TestNoSysPathHacks:
    """Ensure src/ and tests/ files do not contain sys.path.insert / sys.path.append."""

    def test_no_sys_path_hacks_in_src(self):
        """No non-whitelisted file in src/ should call sys.path.insert or append."""
        violations = _collect_violations([PROJECT_ROOT / "src"])
        assert not violations, (
            "The following src/ files still contain sys.path.insert/append hacks.\n"
            "Replace them with proper 'from src.xxx import yyy' imports and rely on\n"
            "'pip install -e .' + pyproject.toml pythonpath configuration.\n\n"
            "Violations:\n  " + "\n  ".join(violations)
        )

    def test_no_sys_path_hacks_in_tests(self):
        """No non-whitelisted file in tests/ should call sys.path.insert or append."""
        violations = _collect_violations([PROJECT_ROOT / "tests"])
        assert not violations, (
            "The following test files still contain sys.path.insert/append hacks.\n"
            "Remove them — pyproject.toml pythonpath = ['.', 'src', 'strategic']\n"
            "makes sys.path manipulation redundant in pytest.\n"
            "For local fixture dirs (e.g. mocks/), add a conftest.py instead.\n\n"
            "Violations:\n  " + "\n  ".join(violations)
        )

    def test_no_sys_path_hacks_in_root_scripts(self):
        """Top-level standalone scripts should not use sys.path.insert."""
        violations: list[str] = []
        for py_file in sorted(PROJECT_ROOT.glob("*.py")):
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if _SYS_PATH_PATTERN.search(source):
                violations.append(str(py_file.relative_to(PROJECT_ROOT)))
        assert not violations, (
            "Top-level scripts still contain sys.path.insert/append hacks.\n"
            "Use 'from src.xxx import yyy' after 'pip install -e .' instead.\n\n"
            "Violations:\n  " + "\n  ".join(violations)
        )

    def test_conftest_no_sys_path(self):
        """tests/conftest.py must not use sys.path manipulation."""
        conftest = PROJECT_ROOT / "tests" / "conftest.py"
        if not conftest.exists():
            pytest.skip("tests/conftest.py not found")
        source = conftest.read_text(encoding="utf-8")
        assert not _SYS_PATH_PATTERN.search(source), (
            "tests/conftest.py still contains sys.path.insert/append. "
            "Use pyproject.toml [tool.pytest.ini_options] pythonpath instead."
        )
