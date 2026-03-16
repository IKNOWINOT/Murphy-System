"""
Test Suite: Analytics Backend — DEFICIENCY-3

Verifies:
  - LoggingBackend captures events
  - WebhookBackend formats correct payload (HTTP call mocked)
  - Backend registration and routing

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


import importlib
import analytics as analytics_mod  # noqa: E402


def _fresh_module():
    """Reload analytics module so global state is reset between tests."""
    importlib.reload(analytics_mod)
    return analytics_mod


# ---------------------------------------------------------------------------
# LoggingBackend
# ---------------------------------------------------------------------------

class TestLoggingBackend:
    def test_track_emits_log(self, caplog):
        mod = _fresh_module()
        backend = mod.LoggingBackend()
        with caplog.at_level(logging.INFO):
            backend.track("test_event", {"key": "value"})
        assert any("test_event" in r.message for r in caplog.records)

    def test_track_includes_data(self, caplog):
        mod = _fresh_module()
        backend = mod.LoggingBackend()
        with caplog.at_level(logging.INFO):
            backend.track("purchase", {"amount": 42})
        combined = " ".join(r.message for r in caplog.records)
        assert "purchase" in combined

    def test_implements_protocol(self):
        mod = _fresh_module()
        backend = mod.LoggingBackend()
        assert isinstance(backend, mod.AnalyticsBackend)


# ---------------------------------------------------------------------------
# WebhookBackend
# ---------------------------------------------------------------------------

class TestWebhookBackend:
    def test_posts_to_url(self):
        mod = _fresh_module()
        backend = mod.WebhookBackend("https://example.com/track")
        with patch.object(urllib.request, "urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = lambda s: s
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            backend.track("page_view", {"page": "/home"})
        assert mock_urlopen.called
        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "https://example.com/track"

    def test_payload_format(self):
        mod = _fresh_module()
        backend = mod.WebhookBackend("https://example.com/track")
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["data"] = json.loads(req.data.decode())
            captured["content_type"] = req.get_header("Content-type")
            ctx = MagicMock()
            ctx.__enter__ = lambda s: s
            ctx.__exit__ = MagicMock(return_value=False)
            return ctx

        with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
            backend.track("signup", {"user_id": "u123"})

        assert captured["data"]["event"] == "signup"
        assert captured["data"]["properties"] == {"user_id": "u123"}
        assert "json" in captured["content_type"].lower()

    def test_network_error_does_not_raise(self):
        mod = _fresh_module()
        backend = mod.WebhookBackend("https://invalid.example.com/track")
        with patch.object(urllib.request, "urlopen", side_effect=OSError("network error")):
            # Should NOT raise — errors are swallowed with a warning
            backend.track("event", {})

    def test_implements_protocol(self):
        mod = _fresh_module()
        backend = mod.WebhookBackend("https://example.com/track")
        assert isinstance(backend, mod.AnalyticsBackend)


# ---------------------------------------------------------------------------
# Backend registration and routing
# ---------------------------------------------------------------------------

class TestBackendRegistration:
    def test_default_backend_is_logging(self):
        mod = _fresh_module()
        assert isinstance(mod._backend, mod.LoggingBackend)

    def test_register_backend_replaces_active(self):
        mod = _fresh_module()
        new_backend = mod.WebhookBackend("https://example.com")
        mod.register_backend(new_backend)
        assert mod._backend is new_backend

    def test_track_event_routes_to_registered_backend(self):
        mod = _fresh_module()
        calls = []

        class DummyBackend:
            def track(self, name, data):
                calls.append((name, data))

        mod.register_backend(DummyBackend())
        mod.enable()
        mod.track_event("click", {"button": "submit"})
        assert len(calls) == 1
        assert calls[0] == ("click", {"button": "submit"})

    def test_track_event_disabled_does_not_route(self):
        mod = _fresh_module()
        calls = []

        class DummyBackend:
            def track(self, name, data):
                calls.append((name, data))

        mod.register_backend(DummyBackend())
        # _enabled is False after reload — do NOT call enable()
        mod.track_event("click", {})
        assert calls == []

    def test_enable_activates_tracking(self):
        mod = _fresh_module()
        calls = []

        class DummyBackend:
            def track(self, name, data):
                calls.append(name)

        mod.register_backend(DummyBackend())
        mod.enable()
        mod.track_event("login", {})
        assert "login" in calls
