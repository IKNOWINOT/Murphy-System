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
    CredentialRequest,
    CredentialRequestStatus,
    PROVIDER_TOS_REGISTRY,
    TOSAcceptanceGate,
    TOSAcceptanceStatus,
    TOSApprovalRequest,
    UserCredentialGate,
    _DEFAULT_LIABILITY_NOTE,
)

# ---------------------------------------------------------------------------
# Expected providers
# ---------------------------------------------------------------------------

EXPECTED_PROVIDERS = {
    "deepinfra",
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
        req = gate.request_approval("deepinfra")
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
        req1 = gate.request_approval("deepinfra")
        req2 = gate.request_approval("deepinfra")
        assert req1.request_id != req2.request_id

    def test_request_stored_in_gate(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        pending = gate.get_pending()
        assert any(r.request_id == req.request_id for r in pending)

    def test_unknown_provider_raises_key_error(self):
        gate = TOSAcceptanceGate()
        with pytest.raises(KeyError):
            gate.request_approval("nonexistent_provider_xyz")

    def test_screenshot_path_stored(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra", screenshot_path="/tmp/test.png")
        assert req.screenshot_path == "/tmp/test.png"

    def test_default_liability_note_present(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        assert req.liability_note == _DEFAULT_LIABILITY_NOTE
        assert len(req.liability_note) > 50


# ---------------------------------------------------------------------------
# TOSAcceptanceGate — approve
# ---------------------------------------------------------------------------

class TestApprove:
    def test_approve_transitions_to_accepted(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        result = gate.approve(req.request_id, approved_by="alice@example.com")
        assert result is True
        assert req.status == TOSAcceptanceStatus.ACCEPTED

    def test_approve_records_accepted_by(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        gate.approve(req.request_id, approved_by="bob@example.com")
        assert req.accepted_by == "bob@example.com"

    def test_approve_records_timestamp(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        gate.approve(req.request_id, approved_by="alice@example.com")
        assert req.accepted_at is not None
        assert "T" in req.accepted_at  # ISO 8601

    def test_approve_logs_audit_entry(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
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
        req = gate.request_approval("deepinfra")
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
        req = gate.request_approval("deepinfra")
        gate.approve(req.request_id, approved_by="alice@example.com")
        log = gate.get_audit_log()
        assert "liability_note" in log[0]
        assert len(log[0]["liability_note"]) > 20

    def test_approve_audit_entry_contains_timestamp(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        gate.approve(req.request_id, approved_by="alice@example.com")
        log = gate.get_audit_log()
        assert "timestamp" in log[0]


# ---------------------------------------------------------------------------
# TOSAcceptanceGate — reject
# ---------------------------------------------------------------------------

class TestReject:
    def test_reject_transitions_to_rejected(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        result = gate.reject(req.request_id, rejected_by="alice@example.com")
        assert result is True
        assert req.status == TOSAcceptanceStatus.REJECTED

    def test_reject_records_reason_in_audit(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        gate.reject(req.request_id, rejected_by="alice@example.com", reason="Not trusted")
        log = gate.get_audit_log()
        assert log[0]["reason"] == "Not trusted"

    def test_reject_unknown_request_id_returns_false(self):
        gate = TOSAcceptanceGate()
        result = gate.reject("nonexistent-id", rejected_by="alice@example.com")
        assert result is False

    def test_reject_logs_audit_entry(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        gate.reject(req.request_id, rejected_by="alice@example.com")
        log = gate.get_audit_log()
        assert len(log) == 1
        assert log[0]["action"] == "rejected"

    def test_reject_removes_from_pending(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        gate.reject(req.request_id, rejected_by="alice@example.com")
        pending = gate.get_pending()
        assert not any(r.request_id == req.request_id for r in pending)


# ---------------------------------------------------------------------------
# TOSAcceptanceGate — skip
# ---------------------------------------------------------------------------

class TestSkip:
    def test_skip_transitions_to_skipped(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        result = gate.skip(req.request_id)
        assert result is True
        assert req.status == TOSAcceptanceStatus.SKIPPED

    def test_skip_unknown_request_id_returns_false(self):
        gate = TOSAcceptanceGate()
        result = gate.skip("nonexistent-id")
        assert result is False

    def test_skip_removes_from_pending(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        gate.skip(req.request_id)
        pending = gate.get_pending()
        assert not any(r.request_id == req.request_id for r in pending)


# ---------------------------------------------------------------------------
# TOSAcceptanceGate — get_pending
# ---------------------------------------------------------------------------

class TestGetPending:
    def test_get_pending_only_returns_pending(self):
        gate = TOSAcceptanceGate()
        req1 = gate.request_approval("deepinfra")
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
        for provider in ["deepinfra", "openai", "anthropic"]:
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
        for provider in ["deepinfra", "openai"]:
            req = gate.request_approval(provider)
            gate.approve(req.request_id, approved_by="alice@example.com")
        log = gate.get_audit_log()
        assert len(log) == 2

    def test_audit_log_grows_with_rejection(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        gate.reject(req.request_id, rejected_by="alice@example.com")
        assert len(gate.get_audit_log()) == 1

    def test_get_audit_log_returns_copy(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
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
        req = gate.request_approval("deepinfra")
        msg = gate.format_approval_message(req)
        assert isinstance(msg, str)
        assert len(msg) > 50

    def test_message_contains_provider_name(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        msg = gate.format_approval_message(req)
        assert "DeepInfra" in msg

    def test_message_contains_tos_url(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        msg = gate.format_approval_message(req)
        assert req.tos_url in msg

    def test_message_contains_privacy_url(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        msg = gate.format_approval_message(req)
        assert req.privacy_url in msg

    def test_message_contains_request_id(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("openai")
        msg = gate.format_approval_message(req)
        assert req.request_id in msg

    def test_message_contains_liability_note_excerpt(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        msg = gate.format_approval_message(req)
        # The liability note is long; check a distinctive fragment
        assert "legal" in msg.lower() or "liability" in msg.lower()

    def test_message_contains_screenshot_path_when_set(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra", screenshot_path="/tmp/test.png")
        msg = gate.format_approval_message(req)
        assert "/tmp/test.png" in msg

    def test_message_no_screenshot_path_when_none(self):
        gate = TOSAcceptanceGate()
        req = gate.request_approval("deepinfra")
        msg = gate.format_approval_message(req)
        # Should not crash and should still mention key info
        assert "DeepInfra" in msg


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
                req = gate.request_approval("deepinfra")
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


# ---------------------------------------------------------------------------
# UserCredentialGate tests
# ---------------------------------------------------------------------------

class TestUserCredentialGateRequestCredentials:
    def test_creates_pending_request(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test harvest")
        assert req.status == CredentialRequestStatus.PENDING

    def test_request_has_purpose(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="key acquisition")
        assert req.purpose == "key acquisition"

    def test_request_stores_suggested_email(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test", suggested_email="a@b.com")
        assert req.suggested_email == "a@b.com"

    def test_request_has_unique_id(self):
        gate = UserCredentialGate()
        r1 = gate.request_credentials(purpose="t1")
        r2 = gate.request_credentials(purpose="t2")
        assert r1.request_id != r2.request_id

    def test_request_appears_in_pending(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="harvest")
        assert any(r.request_id == req.request_id for r in gate.get_pending())


class TestUserCredentialGateProvide:
    def test_provide_transitions_to_provided(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test")
        ok = gate.provide(req.request_id, email="u@example.com", password="secret123")
        assert ok is True
        with gate._lock:
            assert gate._requests[req.request_id].status == CredentialRequestStatus.PROVIDED

    def test_provide_sets_email(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test")
        gate.provide(req.request_id, email="u@example.com", password="abc")
        with gate._lock:
            assert gate._requests[req.request_id].email == "u@example.com"

    def test_provide_does_not_store_password_on_request(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test")
        gate.provide(req.request_id, email="u@example.com", password="s3cr3t")
        cred_req = gate._requests[req.request_id]
        # Ensure password is NOT on the dataclass
        assert not hasattr(cred_req, "password")
        assert cred_req.password_set is True

    def test_provide_unknown_id_returns_false(self):
        gate = UserCredentialGate()
        assert gate.provide("bad-id", email="x@x.com", password="y") is False

    def test_provide_empty_email_returns_false(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test")
        assert gate.provide(req.request_id, email="", password="abc") is False

    def test_provide_empty_password_returns_false(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test")
        assert gate.provide(req.request_id, email="x@x.com", password="") is False


class TestUserCredentialGateGetCredentials:
    def test_get_credentials_returns_email_and_password(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test")
        gate.provide(req.request_id, email="u@example.com", password="s3cr3t")
        creds = gate.get_credentials(req.request_id)
        assert creds is not None
        email, password = creds
        assert email == "u@example.com"
        assert password == "s3cr3t"

    def test_get_credentials_clears_password_from_memory(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test")
        gate.provide(req.request_id, email="u@example.com", password="s3cr3t")
        gate.get_credentials(req.request_id)
        # Password dict should be cleared after retrieval
        with gate._lock:
            assert req.request_id not in gate._passwords

    def test_get_credentials_pending_request_returns_none(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test")
        assert gate.get_credentials(req.request_id) is None

    def test_get_credentials_unknown_id_returns_none(self):
        gate = UserCredentialGate()
        assert gate.get_credentials("nonexistent-id") is None


class TestUserCredentialGateDecline:
    def test_decline_transitions_to_declined(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test")
        ok = gate.decline(req.request_id)
        assert ok is True
        with gate._lock:
            assert gate._requests[req.request_id].status == CredentialRequestStatus.DECLINED

    def test_decline_unknown_id_returns_false(self):
        gate = UserCredentialGate()
        assert gate.decline("bad-id") is False

    def test_decline_removes_from_pending(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test")
        gate.decline(req.request_id)
        assert not any(r.request_id == req.request_id for r in gate.get_pending())


class TestUserCredentialGateFormatMessage:
    def test_format_message_returns_nonempty_string(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="API key harvest")
        msg = gate.format_request_message(req)
        assert isinstance(msg, str) and len(msg) > 50

    def test_format_message_contains_purpose(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="harvest 15 providers")
        msg = gate.format_request_message(req)
        assert "harvest 15 providers" in msg

    def test_format_message_contains_request_id(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test")
        msg = gate.format_request_message(req)
        assert req.request_id in msg

    def test_format_message_contains_suggested_email(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test", suggested_email="me@example.com")
        msg = gate.format_request_message(req)
        assert "me@example.com" in msg

    def test_format_message_mentions_password_security(self):
        gate = UserCredentialGate()
        req = gate.request_credentials(purpose="test")
        msg = gate.format_request_message(req)
        assert "password" in msg.lower()
        # Must warn the user the password won't be stored on disk
        assert "disk" in msg.lower() or "permanent" in msg.lower()


class TestUserCredentialGateThreadSafety:
    def test_concurrent_provide_calls(self):
        """Multiple concurrent provide() calls must not corrupt internal state."""
        gate = UserCredentialGate()
        requests = [gate.request_credentials(purpose=f"t{i}") for i in range(20)]
        errors = []

        def do_provide(req):
            try:
                gate.provide(req.request_id, email=f"u{req.request_id[-4:]}@example.com", password="pwd123")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=do_provide, args=(r,)) for r in requests]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # All should now be PROVIDED
        with gate._lock:
            for req in requests:
                assert gate._requests[req.request_id].status == CredentialRequestStatus.PROVIDED
