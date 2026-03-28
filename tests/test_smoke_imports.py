"""
Smoke import tests — fail fast if a core module is broken.

These tests verify that key modules are importable with the canonical
root src/ package layout.  They run in every CI matrix leg and catch
broken imports before the full test suite.

Import resolution relies on pyproject.toml [tool.pytest.ini_options]
pythonpath = [".", "src", "strategic"] — no sys.path hacks needed.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _import(dotted: str) -> None:
    """Import *dotted* and raise on failure with a clear message."""
    importlib.import_module(dotted)


# ---------------------------------------------------------------------------
# Core runtime
# ---------------------------------------------------------------------------

class TestRuntimeImports:
    """Canonical runtime modules must be importable."""

    def test_runtime_app(self):
        _import("src.runtime.app")

    def test_runtime_murphy_system_core(self):
        _import("src.runtime.murphy_system_core")

    def test_runtime_boot(self):
        _import("src.runtime.boot")


# ---------------------------------------------------------------------------
# Rosetta subsystem
# ---------------------------------------------------------------------------

class TestRosettaImports:
    """Rosetta state-management modules must be importable."""

    def test_rosetta_archive_classifier(self):
        _import("src.rosetta.archive_classifier")

    def test_rosetta_global_aggregator(self):
        _import("src.rosetta.global_aggregator")

    def test_rosetta_subsystem_wiring(self):
        """RSW-001 wiring module — promoted from Murphy System/src/."""
        _import("src.rosetta_subsystem_wiring")


# ---------------------------------------------------------------------------
# Modular runtime / swarm
# ---------------------------------------------------------------------------

class TestModularRuntimeImports:
    """Modular-runtime and swarm orchestration must be importable."""

    def test_modular_runtime(self):
        _import("src.modular_runtime")

    def test_true_swarm_system(self):
        _import("src.true_swarm_system")


# ---------------------------------------------------------------------------
# Canonical src layout — guard against accidental path escapes
# ---------------------------------------------------------------------------

class TestCanonicalLayout:
    """Verify canonical root src/ is the resolved package location."""

    def test_src_is_package(self):
        """root src/__init__.py must exist."""
        assert (Path(__file__).parent.parent / "src" / "__init__.py").exists(), (
            "root src/ is missing __init__.py — it must be a Python package."
        )

    def test_deepinfra_provider_present(self):
        """runtime/app.py must reference DEEPINFRA_API_KEY (PR #440)."""
        app_py = Path(__file__).parent.parent / "src" / "runtime" / "app.py"
        if not app_py.exists():
            pytest.skip("src/runtime/app.py not found")
        assert "DEEPINFRA_API_KEY" in app_py.read_text(encoding="utf-8"), (
            "src/runtime/app.py must reference DEEPINFRA_API_KEY "
            "(Groq→DeepInfra migration, PR #440)."
        )
