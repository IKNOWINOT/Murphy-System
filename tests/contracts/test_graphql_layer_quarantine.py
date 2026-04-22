"""
ADR-0008 quarantine guard for `src/graphql_api_layer.py`.

ADR-0008 declared the bespoke GraphQL layer **experimental** with a defined
removal window (next major version, or 90 days from 2026-04-22 — whichever
comes first). During the cooling-off window the module must remain importable
so that any out-of-tree caller does not break overnight, but it MUST NOT be
re-wired into the production HTTP surface.

This test fails if either of those invariants breaks:

1. The module no longer emits a ``DeprecationWarning`` at import time.
2. Any other module under ``src/`` gains a real Python import of
   ``graphql_api_layer`` (string-literal references in registry files are
   permitted — those are resolved through the optional-load registry and
   do not pull the module into the import graph unless the operator opts in).

When the calendar gate elapses, the deletion PR removes both the source
file and this test in the same commit, citing ADR-0008.
"""

from __future__ import annotations

import ast
import importlib
import warnings
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _REPO_ROOT / "src"
_QUARANTINED_MODULE = "src.graphql_api_layer"
_QUARANTINED_LEAF = "graphql_api_layer"
_SELF = _SRC / "graphql_api_layer.py"


def _module_imports(py_file: Path) -> set[str]:
    """Return the set of module names reachable via real Python import statements.

    A ``string literal`` mentioning ``graphql_api_layer`` (e.g. inside a registry
    dict) is *not* a real import and is intentionally not flagged here.
    """
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            for alias in node.names:
                names.add(f"{node.module}.{alias.name}")
    return names


def test_graphql_layer_emits_deprecation_warning_on_import() -> None:
    """Invariant from ADR-0008 §Decision step 1: module emits DeprecationWarning."""
    # Force a fresh import so the warning is observable.
    import sys
    sys.modules.pop(_QUARANTINED_MODULE, None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module(_QUARANTINED_MODULE)
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecations, (
        "ADR-0008 requires src/graphql_api_layer.py to emit a DeprecationWarning "
        "at import. None observed. Either restore the warning or, if the deletion "
        "calendar gate has elapsed, delete the module and this test together."
    )
    assert any("ADR-0008" in str(w.message) for w in deprecations), (
        "DeprecationWarning is emitted but does not cite ADR-0008. The citation "
        "is the audit trail required by the ADR — restore it."
    )


def test_no_production_module_imports_graphql_layer() -> None:
    """No `import` statement under src/ may reach the quarantined module.

    String mentions in registries (matrix bridge, command registry) are
    fine — those are resolved lazily via the optional-load registry and
    only materialise when an operator explicitly opts the module in.
    """
    offenders: list[str] = []
    for py in _SRC.rglob("*.py"):
        if py == _SELF:
            continue
        imports = _module_imports(py)
        for imp in imports:
            if (
                imp == _QUARANTINED_MODULE
                or imp.startswith(_QUARANTINED_MODULE + ".")
                or imp == _QUARANTINED_LEAF
                or imp.startswith(_QUARANTINED_LEAF + ".")
            ):
                offenders.append(f"{py.relative_to(_REPO_ROOT)}: import {imp!r}")
    assert not offenders, (
        "ADR-0008 quarantine breached: the following src/ modules now have "
        "real Python imports of the deprecated graphql_api_layer module. "
        "Either remove the import or write a superseding ADR explaining why "
        "the layer is being graduated:\n  " + "\n  ".join(offenders)
    )


def test_module_self_marker_is_set() -> None:
    """ADR-0008 §Decision step 1 requires `__experimental__ = True`."""
    mod = importlib.import_module(_QUARANTINED_MODULE)
    assert getattr(mod, "__experimental__", False) is True, (
        "src/graphql_api_layer.py must export `__experimental__ = True` while "
        "ADR-0008 is in effect. The marker is what `find_unused_modules` and "
        "downstream tooling use to keep the module visible in the audit."
    )


if __name__ == "__main__":  # pragma: no cover - manual run
    raise SystemExit(pytest.main([__file__, "-v"]))
