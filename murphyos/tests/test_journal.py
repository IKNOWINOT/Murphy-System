# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""Tests for murphy_journal — systemd journald structured logging."""

from __future__ import annotations

import pathlib
import sys
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# PYTHONPATH
# ---------------------------------------------------------------------------
_MURPHYOS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_MURPHYOS / "userspace" / "murphy-journal"))

import murphy_journal
from murphy_journal import (
    MurphyJournal,
    SYSLOG_IDENTIFIER,
    VALID_EVENT_TYPES,
    VALID_SEVERITIES,
    _validate_event_type,
    _validate_severity,
)


# ── initialisation ────────────────────────────────────────────────────────
class TestMurphyJournalInit:
    def test_init_default_identifier(self):
        j = MurphyJournal()
        assert j._syslog_id == SYSLOG_IDENTIFIER

    def test_init_custom_identifier(self):
        j = MurphyJournal(syslog_identifier="custom-id")
        assert j._syslog_id == "custom-id"

    def test_backend_property_returns_string(self):
        j = MurphyJournal()
        assert j.backend in ("systemd", "logger", "none")


# ── log_event with native systemd ────────────────────────────────────────
class TestLogEventNative:
    def test_log_event_calls_journal_send(self):
        j = MurphyJournal()
        j._use_native = True
        with mock.patch.object(j, "_send_native") as mock_send:
            j.log_event("confidence", "test message", severity="info")
            mock_send.assert_called_once()
            args = mock_send.call_args
            assert args[0][0] == "test message"

    def test_log_event_invalid_type_raises(self):
        j = MurphyJournal()
        with pytest.raises(ValueError, match="unknown event type"):
            j.log_event("invalid_type", "msg")

    def test_log_event_invalid_severity_raises(self):
        j = MurphyJournal()
        with pytest.raises(ValueError, match="unknown severity"):
            j.log_event("confidence", "msg", severity="fatal")


# ── log_event fallback to subprocess logger ───────────────────────────────
class TestLogEventFallback:
    def test_log_event_uses_logger_fallback(self):
        j = MurphyJournal()
        j._use_native = False
        j._logger_bin = "/usr/bin/logger"
        with mock.patch.object(j, "_send_logger") as mock_logger:
            j.log_event("gate", "gate test", severity="warning")
            mock_logger.assert_called_once()

    def test_log_event_no_backend_skips(self):
        j = MurphyJournal()
        j._use_native = False
        j._logger_bin = None
        # Should not raise
        j.log_event("swarm", "no backend available", severity="info")


# ── convenience methods ───────────────────────────────────────────────────
class TestConvenienceMethods:
    def test_log_confidence_change_formats_correctly(self):
        j = MurphyJournal()
        with mock.patch.object(j, "log_event") as mock_le:
            j.log_confidence_change(old_score=0.72, new_score=0.85)
            mock_le.assert_called_once()
            call_kwargs = mock_le.call_args
            assert "increased" in call_kwargs[1].get("message", call_kwargs[0][1])

    def test_log_confidence_change_decreased(self):
        j = MurphyJournal()
        with mock.patch.object(j, "log_event") as mock_le:
            j.log_confidence_change(old_score=0.90, new_score=0.50)
            msg = mock_le.call_args[1].get("message", mock_le.call_args[0][1])
            assert "decreased" in msg

    def test_log_gate_decision_includes_all_fields(self):
        j = MurphyJournal()
        with mock.patch.object(j, "log_event") as mock_le:
            j.log_gate_decision("deploy", "allow", confidence=0.85)
            mock_le.assert_called_once()
            kwargs = mock_le.call_args[1]
            assert kwargs.get("MURPHY_GATE_NAME") == "deploy"
            assert kwargs.get("MURPHY_GATE_ACTION") == "allow"

    def test_log_swarm_lifecycle_spawn(self):
        j = MurphyJournal()
        with mock.patch.object(j, "log_event") as mock_le:
            j.log_swarm_lifecycle("agent-42", "spawn", role="worker")
            mock_le.assert_called_once()
            kwargs = mock_le.call_args[1]
            assert kwargs.get("MURPHY_AGENT_ID") == "agent-42"
            assert kwargs.get("MURPHY_SWARM_ACTION") == "spawn"

    def test_log_swarm_lifecycle_error_sets_severity(self):
        j = MurphyJournal()
        with mock.patch.object(j, "log_event") as mock_le:
            j.log_swarm_lifecycle("agent-99", "error")
            kwargs = mock_le.call_args[1]
            assert kwargs.get("severity") == "error"

    def test_log_security_event_with_severity_mapping(self):
        j = MurphyJournal()
        with mock.patch.object(j, "log_event") as mock_le:
            j.log_security_event("network_sentinel", "brute force detected", severity="critical")
            mock_le.assert_called_once()
            kwargs = mock_le.call_args[1]
            assert kwargs.get("severity") == "critical"
            assert kwargs.get("MURPHY_SECURITY_ENGINE") == "network_sentinel"

    def test_log_llm_request_includes_provider_and_model(self):
        j = MurphyJournal()
        with mock.patch.object(j, "log_event") as mock_le:
            j.log_llm_request(provider="openai", model="gpt-4", tokens=1500, latency_ms=320.5)
            mock_le.assert_called_once()
            kwargs = mock_le.call_args[1]
            assert kwargs.get("MURPHY_LLM_PROVIDER") == "openai"
            assert kwargs.get("MURPHY_LLM_MODEL") == "gpt-4"
            assert kwargs.get("MURPHY_LLM_TOKENS") == "1500"


# ── query_events ──────────────────────────────────────────────────────────
class TestQueryEvents:
    def test_query_events_native_backend(self):
        j = MurphyJournal()
        j._use_native = True
        mock_reader = mock.MagicMock()
        mock_reader.__iter__ = mock.MagicMock(return_value=iter([
            {"MESSAGE": "test", "MURPHY_EVENT_TYPE": "confidence"},
        ]))
        with mock.patch.object(murphy_journal, "_journal_mod") as mock_jmod:
            mock_jmod.Reader.return_value = mock_reader
            results = j.query_events(event_type="confidence", limit=10)
        assert isinstance(results, list)
