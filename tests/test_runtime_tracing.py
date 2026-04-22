"""Tests for src/runtime/tracing.py — Class S Roadmap, Item 6 scaffold.

These tests verify the contract that matters most for the scaffold:

1. Importing the module never fails, even when ``opentelemetry`` is not
   installed.
2. ``configure_tracing()`` is a true no-op when the env switch is off.
3. ``configure_tracing()`` is idempotent — repeat calls are safe.
4. ``configure_tracing()`` degrades gracefully (returns False, logs a
   warning, does not raise) when the env switch is on but the OTel SDK
   is missing.

The "OTel actually configured" path is intentionally not tested here:
that requires the real opentelemetry packages, which are an opt-in
production extra and are not in ``requirements_ci.txt``. Once a
follow-up PR adds them, an integration-flavoured test belongs in
``tests/integration/`` with a real OTLP collector or in-memory
exporter.
"""

from __future__ import annotations

import importlib
import logging
import sys

import pytest


@pytest.fixture
def tracing_module():
    """Import the tracing module fresh for each test and reset state."""
    if "src.runtime.tracing" in sys.modules:
        del sys.modules["src.runtime.tracing"]
    mod = importlib.import_module("src.runtime.tracing")
    mod.reset_for_tests()
    yield mod
    mod.reset_for_tests()


def test_module_imports_without_opentelemetry(tracing_module) -> None:
    """The scaffold must be importable in environments lacking OTel."""
    assert hasattr(tracing_module, "configure_tracing")
    assert hasattr(tracing_module, "is_enabled")
    assert hasattr(tracing_module, "reset_for_tests")


def test_is_enabled_default_false(monkeypatch, tracing_module) -> None:
    monkeypatch.delenv("MURPHY_OTEL_ENABLED", raising=False)
    assert tracing_module.is_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "On"])
def test_is_enabled_truthy_values(monkeypatch, tracing_module, value) -> None:
    monkeypatch.setenv("MURPHY_OTEL_ENABLED", value)
    assert tracing_module.is_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "maybe"])
def test_is_enabled_falsy_values(monkeypatch, tracing_module, value) -> None:
    monkeypatch.setenv("MURPHY_OTEL_ENABLED", value)
    assert tracing_module.is_enabled() is False


def test_configure_tracing_noop_when_disabled(
    monkeypatch, tracing_module
) -> None:
    monkeypatch.delenv("MURPHY_OTEL_ENABLED", raising=False)
    assert tracing_module.configure_tracing() is False
    # Calling again must remain a no-op.
    assert tracing_module.configure_tracing() is False


def test_configure_tracing_graceful_when_sdk_missing(
    monkeypatch, tracing_module, caplog
) -> None:
    """If the env switch is on but OTel is not installed, return False
    and emit a single WARNING — never raise."""
    monkeypatch.setenv("MURPHY_OTEL_ENABLED", "1")

    # Force the import inside configure_tracing to fail by inserting a
    # broken stub for one of its required modules. We restore it after
    # the test via the tracing_module fixture cleanup.
    monkeypatch.setitem(sys.modules, "opentelemetry", None)

    with caplog.at_level(logging.WARNING):
        result = tracing_module.configure_tracing()

    assert result is False
    assert any(
        "opentelemetry SDK is not installed" in rec.message
        for rec in caplog.records
    ), f"expected SDK-missing warning, got: {[r.message for r in caplog.records]}"
