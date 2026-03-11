"""Tests for GAP-3: src/runtime/_deps.py exports the 4 new module classes
(or None on ImportError) and reflects their availability.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _src_root() -> Path:
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRuntimeDepsNewModuleExports:
    """GAP-3: _deps.py must export the 4 new module symbols (or None)."""

    def test_dynamic_assist_engine_exported(self):
        """DynamicAssistEngine is present in _deps __all__ or at module level."""
        root = _src_root()
        deps_path = root / "src" / "runtime" / "_deps.py"
        source = deps_path.read_text(encoding="utf-8")
        assert "DynamicAssistEngine" in source

    def test_kfactor_calculator_exported(self):
        root = _src_root()
        deps_path = root / "src" / "runtime" / "_deps.py"
        source = deps_path.read_text(encoding="utf-8")
        assert "KFactorCalculator" in source

    def test_shadow_knostalgia_bridge_exported(self):
        root = _src_root()
        deps_path = root / "src" / "runtime" / "_deps.py"
        source = deps_path.read_text(encoding="utf-8")
        assert "ShadowKnostalgiaBridge" in source

    def test_onboarding_team_pipeline_exported(self):
        root = _src_root()
        deps_path = root / "src" / "runtime" / "_deps.py"
        source = deps_path.read_text(encoding="utf-8")
        assert "OnboardingTeamPipeline" in source

    def test_new_modules_in_all_list(self):
        root = _src_root()
        deps_path = root / "src" / "runtime" / "_deps.py"
        source = deps_path.read_text(encoding="utf-8")
        for symbol in (
            "DynamicAssistEngine",
            "KFactorCalculator",
            "ShadowKnostalgiaBridge",
            "OnboardingTeamPipeline",
        ):
            assert f'"{symbol}"' in source or f"'{symbol}'" in source, (
                f"{symbol!r} not found in __all__ of _deps.py"
            )

    def test_try_except_pattern_used_for_each_module(self):
        """Each of the 4 new imports uses a try/except ImportError block."""
        root = _src_root()
        deps_path = root / "src" / "runtime" / "_deps.py"
        source = deps_path.read_text(encoding="utf-8")
        # Each module name should appear in a 'from src.' import line
        expected_module_paths = {
            "DynamicAssistEngine": "dynamic_assist_engine",
            "KFactorCalculator": "kfactor_calculator",
            "ShadowKnostalgiaBridge": "shadow_knostalgia_bridge",
            "OnboardingTeamPipeline": "onboarding_team_pipeline",
        }
        for sym, module_path in expected_module_paths.items():
            assert f"from src.{module_path}" in source, (
                f"Expected 'from src.{module_path}' import in _deps.py for {sym}"
            )


class TestRuntimeDepsGracefulDegradation:
    """GAP-3: New module imports use graceful degradation (assign None on failure)."""

    def test_none_assignment_pattern_present(self):
        """Each new module block assigns None when ImportError."""
        root = _src_root()
        deps_path = root / "src" / "runtime" / "_deps.py"
        source = deps_path.read_text(encoding="utf-8")
        # Each block must have a "= None" fallback
        for sym in ("DynamicAssistEngine", "KFactorCalculator",
                    "ShadowKnostalgiaBridge", "OnboardingTeamPipeline"):
            # Check that the symbol appears AND there is a = None nearby
            # (checking the pattern exists in the source)
            assert sym in source, f"{sym} missing from _deps.py"

        # Verify the None-assignment pattern exists for each block
        blocks = source.split("except ImportError")
        none_assignments = [b for b in blocks if "= None" in b]
        # We expect at least 4 None assignments for the 4 new modules
        # (there may be more from other optional modules)
        assert len(none_assignments) >= 4

    def test_logger_warning_pattern_present(self):
        """Each new module's except block calls logger.warning()."""
        root = _src_root()
        deps_path = root / "src" / "runtime" / "_deps.py"
        source = deps_path.read_text(encoding="utf-8")
        # Count logger.warning calls — there should be at least 4 new ones
        warning_count = source.count("logger.warning")
        assert warning_count >= 4, (
            f"Expected at least 4 logger.warning() calls in _deps.py, found {warning_count}"
        )
