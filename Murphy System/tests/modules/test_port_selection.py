"""
Port Selection Tests

Tests that the default port (8000) and environment variable overrides
(PORT, MURPHY_PORT) work correctly.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os


def _resolve_port():
    """Mirror the port-selection logic used in murphy_system_1.0_runtime.py."""
    return int(os.getenv('PORT') or os.getenv('MURPHY_PORT') or 8000)


def test_default_port_is_8000(monkeypatch):
    """When neither PORT nor MURPHY_PORT is set, default to 8000."""
    monkeypatch.delenv('PORT', raising=False)
    monkeypatch.delenv('MURPHY_PORT', raising=False)
    assert _resolve_port() == 8000


def test_murphy_port_overrides_default(monkeypatch):
    """MURPHY_PORT overrides the default when PORT is not set."""
    monkeypatch.delenv('PORT', raising=False)
    monkeypatch.setenv('MURPHY_PORT', '9090')
    assert _resolve_port() == 9090


def test_port_overrides_murphy_port(monkeypatch):
    """PORT takes highest precedence over MURPHY_PORT."""
    monkeypatch.setenv('PORT', '3000')
    monkeypatch.setenv('MURPHY_PORT', '9090')
    assert _resolve_port() == 3000


def test_port_overrides_default(monkeypatch):
    """PORT overrides the default when MURPHY_PORT is not set."""
    monkeypatch.setenv('PORT', '5000')
    monkeypatch.delenv('MURPHY_PORT', raising=False)
    assert _resolve_port() == 5000
