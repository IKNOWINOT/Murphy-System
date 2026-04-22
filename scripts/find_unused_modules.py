#!/usr/bin/env python3
"""
find_unused_modules.py — surface-area heatmap for `src/`.

Class S Roadmap, Item 20: a smaller, fully-wired codebase grades higher than
a sprawling one with gaps. This script identifies Python modules under
``src/`` that no other module in the repository imports, so that the
surface-area audit can decide which ones to move to ``experimental/`` or
delete.

What it does
------------
1. Walks ``src/`` and enumerates every ``.py`` module (skipping ``__init__``
   and tests).
2. For each module, computes both the ``src.foo.bar`` and ``foo.bar`` import
   forms (Murphy uses both styles in practice).
3. Greps the entire repo (``src/``, ``tests/``, ``scripts/``, root-level
   entrypoints) for any reference to those import forms.
4. Reports modules with **zero references**.

What it deliberately does NOT do
--------------------------------
* It does not trust dynamic imports. ``importlib.import_module(name)`` calls
  with computed names will not be detected; flagged modules must be
  reviewed manually before deletion. The ``--allowlist`` option lets the
  audit owner record those exceptions explicitly so they do not pollute
  future reports.
* It does not run the test suite. A module imported only at runtime via the
  module loader / registry / hot-load path may be reported as unused; use
  the allowlist for those.

What it does catch (in addition to plain ``import x`` / ``from x import y``)
---------------------------------------------------------------------------
* Relative imports inside the module's own package: ``from .leaf import X``,
  ``from ..pkg.leaf import X``, ``from . import leaf``. Without this the
  re-export pattern used by every package ``__init__.py`` in this repo
  would generate ~200 false positives.

Usage
-----
    python scripts/find_unused_modules.py
    python scripts/find_unused_modules.py --json > /tmp/unused.json
    python scripts/find_unused_modules.py --allowlist scripts/find_unused_modules.allowlist.txt

The allowlist file is one module path per line (e.g. ``src.foo.bar``),
``#`` comments allowed. Modules in the allowlist are excluded from the
"unused" report.

Exit codes
----------
* 0 — completed successfully (the report itself does not affect exit code).
* 2 — argument error.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"

# Directories to search for references.
_SEARCH_DIRS = ["src", "tests", "scripts"]

# Individual root-level entrypoint files that import from src/.
_ROOT_FILES = [
    "murphy_production_server.py",
    "murphy_terminal.py",
    "murphy_system_1.0_runtime.py",
    "two_phase_orchestrator.py",
    "universal_control_plane.py",
    "inoni_business_automation.py",
]

# File-name patterns excluded from the module enumeration. These are not
# user-facing modules (init shims and test files) so we never list them as
# candidates for being "unused".
_EXCLUDED_FILES_PATTERN = re.compile(r"__init__\.py$|test_.*\.py$|.*_test\.py$")


def _enumerate_modules() -> list[tuple[str, Path]]:
    """Return [(dotted_module_path, file_path), ...] for every module under src/."""
    out: list[tuple[str, Path]] = []
    for py in sorted(_SRC_DIR.rglob("*.py")):
        rel = py.relative_to(_REPO_ROOT)
        if py.name == "__init__.py":
            continue
        if _EXCLUDED_FILES_PATTERN.match(py.name):
            continue
        # src/foo/bar.py -> src.foo.bar
        dotted = ".".join(rel.with_suffix("").parts)
        out.append((dotted, py))
    return out


def _has_reference(dotted: str, exclude_file: Path) -> bool:
    """Return True if any file under the search dirs (other than ``exclude_file``)
    imports ``dotted``.

    Two passes:

    1. **Absolute imports.** Match the canonical ``src.foo.bar`` form and
       the bare ``foo.bar`` form Murphy also uses via the src-layout pythonpath.
    2. **Relative imports** scoped to the module's package root. Catches
       ``from .bar import X``, ``from ..pkg.bar import X``, and
       ``from . import bar`` — which is how every package in this repo
       re-exports its own submodules through ``__init__.py``. Without
       this pass the script reports ~200 false positives.
    """
    return _has_absolute_reference(dotted, exclude_file) or _has_relative_reference(
        dotted, exclude_file
    )


def _has_absolute_reference(dotted: str, exclude_file: Path) -> bool:
    """Pass 1: search for absolute-import references to ``dotted``."""
    canonical = dotted  # e.g. "src.foo.bar"
    bare = dotted.removeprefix("src.")  # e.g. "foo.bar"

    # Build a regex that matches either form as a whole token. We require a
    # word boundary on each side so "src.foo.bar" does not also match
    # "src.foo.bar_extras".
    pattern = (
        r"(?:from\s+|import\s+)("
        + re.escape(canonical)
        + r"|"
        + re.escape(bare)
        + r")(?:\s|$|\.|,)"
    )

    cmd = [
        "git",
        "grep",
        "-l",
        "--perl-regexp",
        pattern,
        "--",
    ]
    cmd.extend(_SEARCH_DIRS)
    cmd.extend(_ROOT_FILES)

    return _run_grep_returns_match(cmd, dotted, exclude_file)


def _has_relative_reference(dotted: str, exclude_file: Path) -> bool:
    """Pass 2: search for relative-import references inside the module's
    package root.

    For ``src/reconciliation/evaluators/code.py`` (dotted
    ``src.reconciliation.evaluators.code``), the package root is
    ``src/reconciliation/`` (the first directory under ``src/``) and the leaf
    name is ``code``. Relative imports of this module from anywhere inside
    the package look like one of:

    * ``from .code import X``
    * ``from .evaluators.code import X``
    * ``from ..evaluators.code import X``
    * ``from . import code``
    * ``from . import (other, code, more)``

    The grep is scoped to the package root so a leaf-name collision in an
    unrelated package does not produce a false negative for the unrelated
    module (it can only be imported from within its own package via the
    relative form).
    """
    parts = dotted.split(".")
    # Top-level modules in src/ (e.g. ``src.foo``) cannot be the target of
    # a relative import — there is no parent package to anchor a leading dot.
    if parts[0] != "src" or len(parts) < 3:
        return False

    package_root = _REPO_ROOT / "src" / parts[1]
    if not package_root.is_dir():
        return False
    leaf = parts[-1]

    # Pattern A: ``from .<...>leaf<token>`` — covers ``from .leaf``,
    # ``from .sub.leaf``, ``from ..pkg.leaf``, including the case where
    # the import opens a multi-line ``import (`` block on the same line.
    # Pattern B: ``from .<...>  import  <maybe parens>(...,) leaf`` — the
    # ``from . import x`` form. Restricted to the same line for simplicity;
    # the multi-line ``from . import (\n    leaf,\n)`` form is extremely
    # rare in this codebase and will be picked up by Pattern A's sibling
    # ``from .leaf import`` re-export when present.
    leaf_re = re.escape(leaf)
    pattern = (
        r"(?:from\s+\.+(?:\w+\.)*"
        + leaf_re
        + r"(?:\s|$|\.|,))"
        + r"|"
        + r"(?:from\s+\.+\s+import\s+[^#\n]*\b"
        + leaf_re
        + r"\b)"
    )

    package_root_rel = package_root.relative_to(_REPO_ROOT)
    cmd = [
        "git",
        "grep",
        "-l",
        "--perl-regexp",
        pattern,
        "--",
        str(package_root_rel),
    ]

    return _run_grep_returns_match(cmd, dotted, exclude_file)


def _run_grep_returns_match(
    cmd: list[str], dotted: str, exclude_file: Path
) -> bool:
    """Run ``cmd`` (a ``git grep -l ...``) and return True iff at least one
    matching file other than ``exclude_file`` is found.

    Centralises the timeout / non-zero-rc handling shared by both passes:
    on timeout or unexpected error we conservatively return True so the
    module is not flagged as unused. Repeated warnings make pathological
    cases (e.g. perf regression in git-grep) visible rather than silently
    biasing the report.
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        # On timeout we conservatively assume the module is referenced so we
        # do not falsely flag it as unused. Log so repeated timeouts surface
        # as a real problem (e.g. pathological repo size or git grep
        # performance regression) rather than silently skewing the report.
        # To investigate locally, re-run the failing query directly:
        #   git grep -l --perl-regexp '<pattern>' -- src tests scripts
        # and consider narrowing the search dirs or raising the 30s budget.
        sys.stderr.write(
            f"warning: git grep timed out after 30s for {dotted!r}; "
            "assuming referenced. Re-run manually with "
            f"`git grep -l --perl-regexp '...{dotted}...' -- src tests scripts` "
            "to investigate.\n"
        )
        return True

    if result.returncode not in (0, 1):
        # 0 = matches found, 1 = no match, anything else is a real error.
        sys.stderr.write(
            f"warning: git grep failed for {dotted!r} (rc={result.returncode}): "
            f"{result.stderr.strip()}\n"
        )
        return True

    matches = [
        Path(line.strip())
        for line in result.stdout.splitlines()
        if line.strip()
    ]
    exclude_rel = exclude_file.relative_to(_REPO_ROOT)
    matches = [m for m in matches if m != exclude_rel]
    return bool(matches)


def _load_allowlist(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    out: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="Path to an allowlist file; modules listed there are excluded.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of a human-readable summary.",
    )
    parser.add_argument(
        "--include-test-fixtures",
        action="store_true",
        help="Also search under tests/ for references (default behaviour). "
        "Disable with --no-include-test-fixtures.",
    )
    args = parser.parse_args(argv)

    if not _SRC_DIR.is_dir():
        sys.stderr.write(f"error: {_SRC_DIR} does not exist\n")
        return 2

    allowlist = _load_allowlist(args.allowlist)
    modules = _enumerate_modules()

    unused: list[dict[str, str]] = []
    for dotted, path in modules:
        if dotted in allowlist:
            continue
        if not _has_reference(dotted, path):
            unused.append({"module": dotted, "path": str(path.relative_to(_REPO_ROOT))})

    if args.json:
        json.dump(
            {
                "scanned": len(modules),
                "allowlisted": sum(1 for d, _ in modules if d in allowlist),
                "unused": unused,
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        print(f"Scanned {len(modules)} modules under src/.")
        if allowlist:
            print(f"Allowlist excluded {len(allowlist)} known-runtime-loaded modules.")
        print(f"Found {len(unused)} module(s) with no static import references:")
        for entry in unused:
            print(f"  {entry['path']:<60s}  ({entry['module']})")
        if unused:
            print()
            print(
                "Note: this is a STATIC scan — modules loaded via "
                "importlib.import_module(name) at runtime will appear here. "
                "Review each entry before moving to experimental/ or deleting."
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
