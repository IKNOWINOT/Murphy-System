"""
Tests for TOSAcceptanceGate — tos_acceptance_gate.py

Covers:
- PROVIDER_TOS_REGISTRY completeness and data integrity
- TOSAcceptanceGate lifecycle: request_approval, approve, reject, skip
- Audit log correctness
- format_approval_message output
- Thread-safety under concurrent approvals
- Liability note presence

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys
import threading
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tos_acceptance_gate import (
    PROVIDER_TOS_REGISTRY,
    TOSAcceptanceGate,
    TOSAcceptanceStatus,
    TOSApprovalRequest,
    _DEFAULT_LIABILITY_NOTE,
)

# ---------------------------------------------------------------------------
# Expected providers
# ---------------------------------------------------------------------------

EXPECTED_PROVIDERS = {
    "groq",
    "openai",
    "anthropic",
    "elevenlabs",
    "sendgrid",
    "stripe",
    "twilio",
    "heygen",
    "tavus",
    "vapi",
    "hubspot",
    "shopify",
    "coinbase",
    "github",
    "slack",
}


# ---------------------------------------------------------------------------
# PROVIDER_TOS_REGISTRY tests
# ---------------------------------------------------------------------------

class TestProviderTOSRegistry:
    def test_registry_has_all_15_providers(self):
        assert EXPECTED_PROVIDERS <= set(PROVIDER_TOS_REGISTRY.keys()), (
            f"Missing providers: {EXPECTED_PROVIDERS - set(PROVIDER_TOS_REGISTRY.keys())}"
        )

    @pytest.mark.parametrize("provider_key", list(EXPECTED_PROVIDERS))
    def test_every_entry_has_nonempty_tos_url(self, provider_key):
        entry = PROVIDER_TOS_REGISTRY[provider_key]
        assert entry.tos_url, f"Provider '{provider_key}' has empty tos_url"

    @pytest.mark.parametrize("provider_key", list(EXPECTED_PROVIDERS))
    def test_every_entry_has_nonempty_privacy_url(self, provider_key):
        entry = PROVIDER_TOS_REGISTRY[provider_key]
        assert entry.privacy_url, f"Provider '{provider_key}' has empty privacy_url"

    @pytest.mark.parametrize("provider_key", list(EXPECTED_PROVIDERS))
    def test_every_entry_has_nonempty_provider_name(self, provider_key):
        entry = PROVIDER_TOS_REGISTRY[provider_key]
        assert entry.provider_name, f"Provider '{provider_key}' has empty provider_name"

    @pytest.mark.parametrize("provider_key", list(EXPECTED_PROVIDERS))
    def test_tos_url_is_https(self, provider_key):
        entry = PROVIDER_TOS_REGISTRY[provider_key]
        assert entry.tos_url.startswith("https://"), (
            f"Provider '{provider_key}' tos_url is not HTTPS"
        )

    @pytest.mark.parametrize("provider_key", list(EXPECTED_PROVIDERS))
    def test_privacy_url_is_https(self, provider_key):
        entry = PROVIDER_TOS_REGISTRY[provider_key]
        assert entry.privacy_url.startswith("https://"), (
            f"Provider '{provider_key}' privacy_url is not HTTPS"
        )


# ---------------------------------------------------------------------------
# TOSAcceptanceGate — request_approval
# ---------------------------------------------------------------------------

class TestRequestApproval:
    def test_creates_pending_request(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        assert req.status == TOSAcceptanceStatus.PENDING

    def test_request_has_correct_provider_key(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("openai")
        assert req.provider_key == "openai"

    def test_request_has_correct_provider_name(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("openai")
        assert req.provider_name == "OpenAI"

    def test_request_has_tos_url(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("anthropic")
        assert req.tos_url == PROVIDER_TOS_REGISTRY["anthropic"].tos_url

    def test_request_has_privacy_url(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("anthropic")
        assert req.privacy_url == PROVIDER_TOS_REGISTRY["anthropic"].privacy_url

    def test_request_has_unique_id(self):
        gate = TOSAcceptanceGate()
        req1 = gate.request_approval("groq")
        req2 = gate.request_approval("groq")
        assert req1.request_id != req2.request_id

    def test_request_stored_in_gate(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        pending = gate.get_pending()
        assert any(r.request_id == req.request_id for r in pending)

    def test_unknown_provider_raises_key_error(self):
        gate = TOSAcceptanceGate()
        with pytest.raises(KeyError):
            gate.request_approval("nonexistent_provider_xyz")

    def test_screenshot_path_stored(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq", screenshot_path="/tmp/test.png")
        assert req.screenshot_path == "/tmp/test.png"

    def test_default_liability_note_present(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        assert req.liability_note == _DEFAULT_LIABILITY_NOTE
        assert len(req.liability_note) > 50


# ---------------------------------------------------------------------------
# TOSAcceptanceGate — approve
# ---------------------------------------------------------------------------

class TestApprove:
    def test_approve_transitions_to_accepted(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        result = gate.approve(req.request_id, approved_by="alice@example.com")
        assert result is True
        assert req.status == TOSAcceptanceStatus.ACCEPTED

    def test_approve_records_accepted_by(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        gate.approve(req.request_id, approved_by="bob@example.com")
        assert req.accepted_by == "bob@example.com"

    def test_approve_records_timestamp(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        gate.approve(req.request_id, approved_by="alice@example.com")
        assert req.accepted_at is not None
        assert "T" in req.accepted_at  # ISO 8601

    def test_approve_logs_audit_entry(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        gate.approve(req.request_id, approved_by="alice@example.com")
        log = gate.get_audit_log()
        assert len(log) == 1
        assert log[0]["action"] == "accepted"

    def test_approve_unknown_request_id_returns_false(self):
        gate = TOSAcceptanceGate()
        result = gate.approve("nonexistent-id", approved_by="alice@example.com")
        assert result is False

    def test_approve_already_approved_returns_false(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        gate.approve(req.request_id, approved_by="alice@example.com")
        result = gate.approve(req.request_id, approved_by="alice@example.com")
        assert result is False

    def test_approve_audit_entry_contains_provider(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("openai")
        gate.approve(req.request_id, approved_by="alice@example.com")
        log = gate.get_audit_log()
        assert log[0]["provider"] == "openai"

    def test_approve_audit_entry_contains_tos_url(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("openai")
        gate.approve(req.request_id, approved_by="alice@example.com")
        log = gate.get_audit_log()
        assert log[0]["tos_url"] == PROVIDER_TOS_REGISTRY["openai"].tos_url

    def test_approve_audit_entry_contains_privacy_url(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("openai")
        gate.approve(req.request_id, approved_by="alice@example.com")
        log = gate.get_audit_log()
        assert log[0]["privacy_url"] == PROVIDER_TOS_REGISTRY["openai"].privacy_url

    def test_approve_audit_entry_contains_liability_note(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        gate.approve(req.request_id, approved_by="alice@example.com")
        log = gate.get_audit_log()
        assert "liability_note" in log[0]
        assert len(log[0]["liability_note"]) > 20

    def test_approve_audit_entry_contains_timestamp(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        gate.approve(req.request_id, approved_by="alice@example.com")
        log = gate.get_audit_log()
        assert "timestamp" in log[0]


# ---------------------------------------------------------------------------
# TOSAcceptanceGate — reject
# ---------------------------------------------------------------------------

class TestReject:
    def test_reject_transitions_to_rejected(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        result = gate.reject(req.request_id, rejected_by="alice@example.com")
        assert result is True
        assert req.status == TOSAcceptanceStatus.REJECTED

    def test_reject_records_reason_in_audit(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        gate.reject(req.request_id, rejected_by="alice@example.com", reason="Not trusted")
        log = gate.get_audit_log()
        assert log[0]["reason"] == "Not trusted"

    def test_reject_unknown_request_id_returns_false(self):
        gate = TOSAcceptanceGate()
        result = gate.reject("nonexistent-id", rejected_by="alice@example.com")
        assert result is False

    def test_reject_logs_audit_entry(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        gate.reject(req.request_id, rejected_by="alice@example.com")
        log = gate.get_audit_log()
        assert len(log) == 1
        assert log[0]["action"] == "rejected"

    def test_reject_removes_from_pending(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        gate.reject(req.request_id, rejected_by="alice@example.com")
        pending = gate.get_pending()
        assert not any(r.request_id == req.request_id for r in pending)


# ---------------------------------------------------------------------------
# TOSAcceptanceGate — skip
# ---------------------------------------------------------------------------

class TestSkip:
    def test_skip_transitions_to_skipped(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        result = gate.skip(req.request_id)
        assert result is True
        assert req.status == TOSAcceptanceStatus.SKIPPED

    def test_skip_unknown_request_id_returns_false(self):
        gate = TOSAcceptanceGate()
        result = gate.skip("nonexistent-id")
        assert result is False

    def test_skip_removes_from_pending(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        gate.skip(req.request_id)
        pending = gate.get_pending()
        assert not any(r.request_id == req.request_id for r in pending)


# ---------------------------------------------------------------------------
# TOSAcceptanceGate — get_pending
# ---------------------------------------------------------------------------

class TestGetPending:
    def test_get_pending_only_returns_pending(self):
        gate = TOSAcceptanceGate()
        req1 = gate.request_approval("groq")
        req2 = gate.request_approval("openai")
        gate.approve(req1.request_id, approved_by="alice@example.com")
        pending = gate.get_pending()
        pending_ids = {r.request_id for r in pending}
        assert req1.request_id not in pending_ids
        assert req2.request_id in pending_ids

    def test_get_pending_empty_initially(self):
        gate = TOSAcceptanceGate()
        assert gate.get_pending() == []

    def test_get_pending_multiple_requests(self):
        gate = TOSAcceptanceGate()
        for provider in ["groq", "openai", "anthropic"]:
            gate.request_approval(provider)
        assert len(gate.get_pending()) == 3


# ---------------------------------------------------------------------------
# TOSAcceptanceGate — get_audit_log
# ---------------------------------------------------------------------------

class TestGetAuditLog:
    def test_audit_log_empty_initially(self):
        gate = TOSAcceptanceGate()
        assert gate.get_audit_log() == []

    def test_audit_log_grows_with_approvals(self):
        gate = TOSAcceptanceGate()
        for provider in ["groq", "openai"]:
            req = gate.request_approval(provider)
            gate.approve(req.request_id, approved_by="alice@example.com")
        log = gate.get_audit_log()
        assert len(log) == 2

    def test_audit_log_grows_with_rejection(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        gate.reject(req.request_id, rejected_by="alice@example.com")
        assert len(gate.get_audit_log()) == 1

    def test_get_audit_log_returns_copy(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        gate.approve(req.request_id, approved_by="alice@example.com")
        log1 = gate.get_audit_log()
        log1.clear()
        log2 = gate.get_audit_log()
        assert len(log2) == 1


# ---------------------------------------------------------------------------
# format_approval_message
# ---------------------------------------------------------------------------

class TestFormatApprovalMessage:
    def test_returns_nonempty_string(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        msg = gate.format_approval_message(req)
        assert isinstance(msg, str)
        assert len(msg) > 50

    def test_message_contains_provider_name(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        msg = gate.format_approval_message(req)
        assert "Groq" in msg

    def test_message_contains_tos_url(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        msg = gate.format_approval_message(req)
        assert req.tos_url in msg

    def test_message_contains_privacy_url(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        msg = gate.format_approval_message(req)
        assert req.privacy_url in msg

    def test_message_contains_request_id(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("openai")
        msg = gate.format_approval_message(req)
        assert req.request_id in msg

    def test_message_contains_liability_note_excerpt(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        msg = gate.format_approval_message(req)
        # The liability note is long; check a distinctive fragment
        assert "legal" in msg.lower() or "liability" in msg.lower()

    def test_message_contains_screenshot_path_when_set(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq", screenshot_path="/tmp/test.png")
        msg = gate.format_approval_message(req)
        assert "/tmp/test.png" in msg

    def test_message_no_screenshot_path_when_none(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("groq")
        msg = gate.format_approval_message(req)
        # Should not crash and should still mention key info
        assert "Groq" in msg


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_approvals_from_multiple_threads(self):
        """Multiple threads approving different requests must not corrupt state."""
        gate = TOSAcceptanceGate()
        providers = list(EXPECTED_PROVIDERS)
        requests = [gate.request_approval(p) for p in providers]

        results = []
        errors = []

        def approve_one(req):
            try:
                ok = gate.approve(req.request_id, approved_by="thread_user")
                results.append(ok)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=approve_one, args=(r,)) for r in requests]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert all(results), "Some approvals failed unexpectedly"
        log = gate.get_audit_log()
        assert len(log) == len(providers)

    def test_concurrent_request_and_approve(self):
        """Simultaneous request_approval and approve calls don't deadlock or corrupt."""
        gate = TOSAcceptanceGate()
        req_ids = []
        lock = threading.Lock()
        errors = []

        def requester():
            try:
                req = gate.request_approval("groq")
                with lock:
                    req_ids.append(req.request_id)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def approver():
            time.sleep(0.01)
            with lock:
                ids = list(req_ids)
            for rid in ids:
                try:
                    gate.approve(rid, approved_by="tester")
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

        t1 = threading.Thread(target=requester)
        t2 = threading.Thread(target=approver)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors


# ---------------------------------------------------------------------------
# Liability note
# ---------------------------------------------------------------------------

class TestLiabilityNote:
    @pytest.mark.parametrize("provider_key", list(EXPECTED_PROVIDERS))
    def test_every_request_has_default_liability_note(self, provider_key):
        gate = TOSAcceptanceGate()
        req = gate.request_approval(provider_key)
        assert req.liability_note == _DEFAULT_LIABILITY_NOTE

    def test_liability_note_mentions_human_operator(self):
        assert "human" in _DEFAULT_LIABILITY_NOTE.lower() or "operator" in _DEFAULT_LIABILITY_NOTE.lower()

    def test_liability_note_mentions_legal(self):
        assert "legal" in _DEFAULT_LIABILITY_NOTE.lower()
