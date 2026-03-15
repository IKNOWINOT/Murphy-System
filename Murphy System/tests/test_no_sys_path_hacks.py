"""
Test: no sys.path hacks in src/ source files.

Enforces the import strategy documented in CONTRIBUTING.md:
- Package imports use proper ``from src.xxx import yyy`` style
- sys.path is managed via pyproject.toml [tool.pytest.ini_options] pythonpath
  and ``pip install -e .`` for editable installs

Whitelisted locations where sys.path manipulation is intentional:
- tests/ directories (legacy; redundant but harmless once pythonpath is set)
- strategic/ demo and integration scripts (standalone scripts, not importable)
- alembic/env.py (Alembic migration runner)
- Any file whose name contains "sandbox_quarantine" (legitimate sandboxing use)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Root of the Murphy System project
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directories that are allowed to keep sys.path manipulation
_ALLOWED_DIRS = {
    "tests",
    "strategic",
    "alembic",
}

# Individual filenames (stems) that are allowed to use sys.path
_ALLOWED_FILE_STEMS = {
    "sandbox_quarantine",
}

_SYS_PATH_PATTERN = re.compile(r"sys\.path\.(insert|append)\s*\(")


def _collect_violations() -> list[str]:
    """Return relative paths of src/ files that contain sys.path hacks."""
    violations: list[str] = []
    src_dir = PROJECT_ROOT / "src"

    for py_file in sorted(src_dir.rglob("*.py")):
        # Skip whitelisted filenames
        if py_file.stem in _ALLOWED_FILE_STEMS:
            continue

        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if _SYS_PATH_PATTERN.search(source):
            violations.append(str(py_file.relative_to(PROJECT_ROOT)))

    return violations


class TestNoSysPathHacks:
    """Ensure src/ files do not contain sys.path.insert / sys.path.append."""

    def test_no_sys_path_hacks_in_src(self):
        """No non-whitelisted file in src/ should call sys.path.insert or append."""
        violations = _collect_violations()
        assert not violations, (
            "The following src/ files still contain sys.path.insert/append hacks.\n"
            "Replace them with proper 'from src.xxx import yyy' imports and rely on\n"
            "'pip install -e .' + pyproject.toml pythonpath configuration.\n\n"
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
