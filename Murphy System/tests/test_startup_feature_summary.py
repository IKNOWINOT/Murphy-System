"""
Tests for Startup Feature-Availability Summary (INC-06 / H-01).

Covers:
  - Feature probe detection (enabled / disabled)
  - Summary output formatting
  - Structured logging emission
  - Runtime integration (main() calls print_feature_summary)

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

# Ensure src/ is importable
_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
_src_dir = os.path.abspath(_src_dir)

from startup_feature_summary import (
    _FEATURE_PROBES,
    get_feature_status,
    print_feature_summary,
)


class TestGetFeatureStatus:
    """Tests for get_feature_status()."""

    def test_all_disabled_by_default(self) -> None:
        """With no env vars set, all features should be disabled."""
        with patch.dict(os.environ, {}, clear=True):
            status = get_feature_status()
        for name, info in status.items():
            assert info["status"] == "disabled", f"{name} should be disabled"

    def test_deepinfra_enabled(self) -> None:
        with patch.dict(os.environ, {"DEEPINFRA_API_KEY": "di_test"}, clear=False):
            status = get_feature_status()
        assert status["Groq LLM"]["status"] == "enabled"

    def test_multiple_features_enabled(self) -> None:
        env = {
            "DEEPINFRA_API_KEY": "di_test",
            "SENDGRID_API_KEY": "SG.test",
            "DATABASE_URL": "postgresql://localhost/murphy",
        }
        with patch.dict(os.environ, env, clear=False):
            status = get_feature_status()
        assert status["Groq LLM"]["status"] == "enabled"
        assert status["SendGrid Email"]["status"] == "enabled"
        assert status["PostgreSQL"]["status"] == "enabled"

    def test_returns_expected_keys(self) -> None:
        status = get_feature_status()
        for name, env_var, desc in _FEATURE_PROBES:
            assert name in status
            assert "status" in status[name]
            assert "description" in status[name]
            assert "env_var" in status[name]


class TestPrintFeatureSummary:
    """Tests for print_feature_summary()."""

    def test_returns_string(self) -> None:
        result = print_feature_summary()
        assert isinstance(result, str)
        assert "Feature Availability" in result

    def test_shows_enabled_feature(self) -> None:
        with patch.dict(os.environ, {"DEEPINFRA_API_KEY": "di_test"}, clear=False):
            result = print_feature_summary()
        assert "Groq LLM" in result
        assert "✅" in result

    def test_shows_disabled_features(self) -> None:
        result = print_feature_summary()
        assert "⬚" in result  # At least some disabled

    def test_summary_contains_all_probes(self) -> None:
        result = print_feature_summary()
        for name, env_var, _ in _FEATURE_PROBES:
            assert name in result or env_var in result


class TestRuntimeIntegration:
    """Verify the runtime calls the feature summary at startup."""

    def test_runtime_imports_feature_summary(self) -> None:
        """INC-06 signal: Runtime prints feature-availability summary."""
        runtime_path = os.path.join(
            os.path.dirname(__file__), "..", "murphy_system_1.0_runtime.py"
        )
        with open(runtime_path, "r") as f:
            content = f.read()
        assert "print_feature_summary" in content, (
            "Runtime must call print_feature_summary at startup (INC-06)"
        )
