# Copyright © 2020 Inoni Limited Liability Company / Creator: Corey Post / License: BSL 1.1
"""
PROD-HARD A6 — Meta-test: no `assert` statements in production source.

Bare `assert` statements are stripped by `python -O` / ``PYTHONOPTIMIZE=1``.
Any invariant expressed as `assert` in production code becomes a silent
no-op when operators run optimized Python (e.g. Gunicorn ``--preload`` with
``-O``).  This meta-test walks the AST of every module under ``src/`` and
fails if it finds any ``ast.Assert`` node outside the ``tests/`` tree (which
is intentionally not present under ``src/`` after PR-A14).

Allowed locations:
    * nothing inside ``src/`` should contain an ``ast.Assert``.

If this test fails, replace ``assert <cond>[, msg]`` with an explicit
``if not <cond>: raise <DomainError | RuntimeError>(msg)``.  Docstring
examples that *mention* ``assert`` are fine — only the AST-level
``ast.Assert`` node is flagged.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"


def _collect_asserts() -> list[tuple[Path, int]]:
    findings: list[tuple[Path, int]] = []
    if not _SRC_ROOT.is_dir():
        pytest.skip(f"src/ not present at {_SRC_ROOT}")
    for py in _SRC_ROOT.rglob("*.py"):
        # Defensive: tests that may still be misplaced under src/ (should be empty after PR-A14).
        if "/tests/" in py.as_posix():
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            # Parsing failure is a separate concern; skip here so this test
            # remains focused on assert-in-src detection.
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                findings.append((py.relative_to(_REPO_ROOT), node.lineno))
    return findings


def test_no_assert_statements_in_src() -> None:
    """Production code must not rely on ``assert`` for invariants."""
    findings = _collect_asserts()
    if findings:
        rendered = "\n".join(f"  {p}:{line}" for p, line in findings)
        pytest.fail(
            "PROD-HARD A6 violation — `assert` found in production source.\n"
            "`assert` is stripped by `python -O` / PYTHONOPTIMIZE=1, which\n"
            "silently disables every invariant. Replace with an explicit\n"
            "`if not <cond>: raise <DomainError>(...)` — keeping the\n"
            "same condition and error message so capability is preserved.\n\n"
            f"Offending sites ({len(findings)}):\n{rendered}"
        )
