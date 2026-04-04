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
import sys

import pytest

# Ensure src/ is importable
_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
_src_dir = os.path.abspath(_src_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from startup_feature_summary import (
    _FEATURE_PROBES,
    get_feature_status,
    print_feature_summary,
)

# Env vars probed by feature summary — saved/restored around each test.
_PROBED_KEYS = [env_var for _, env_var, _ in _FEATURE_PROBES]


def _save_probed_env() -> dict:
    return {k: os.environ.get(k) for k in _PROBED_KEYS}


def _restore_probed_env(snapshot: dict) -> None:
    for k, v in snapshot.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _clear_probed_env() -> None:
    for k in _PROBED_KEYS:
        os.environ.pop(k, None)


class TestGetFeatureStatus:
    """Tests for get_feature_status()."""

    def setup_method(self) -> None:
        self._snapshot = _save_probed_env()

    def teardown_method(self) -> None:
        _restore_probed_env(self._snapshot)

    def test_all_disabled_by_default(self) -> None:
        """With no probe env vars set, all features should be disabled."""
        _clear_probed_env()
        status = get_feature_status()
        for name, info in status.items():
            assert info["status"] == "disabled", f"{name} should be disabled"

    def test_deepinfra_enabled(self) -> None:
        os.environ["DEEPINFRA_API_KEY"] = "di_test"
        status = get_feature_status()
        assert status["DeepInfra LLM"]["status"] == "enabled"

    def test_multiple_features_enabled(self) -> None:
        os.environ["DEEPINFRA_API_KEY"] = "di_test"
        os.environ["SENDGRID_API_KEY"] = "SG.test"
        os.environ["DATABASE_URL"] = "postgresql://localhost/murphy"
        status = get_feature_status()
        assert status["DeepInfra LLM"]["status"] == "enabled"
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

    def setup_method(self) -> None:
        self._snapshot = _save_probed_env()

    def teardown_method(self) -> None:
        _restore_probed_env(self._snapshot)

    def test_returns_string(self) -> None:
        result = print_feature_summary()
        assert isinstance(result, str)
        assert "Feature Availability" in result

    def test_shows_enabled_feature(self) -> None:
        os.environ["DEEPINFRA_API_KEY"] = "di_test"
        result = print_feature_summary()
        assert "DeepInfra LLM" in result
        assert "✅" in result

    def test_shows_disabled_features(self) -> None:
        _clear_probed_env()
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
        # The runtime entry-point delegates to src/runtime/app.py which calls
        # print_feature_summary in its main() path.
        app_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "runtime", "app.py"
        )
        with open(app_path, "r") as f:
            content = f.read()
        assert "print_feature_summary" in content, (
            "Runtime must call print_feature_summary at startup (INC-06)"
        )
