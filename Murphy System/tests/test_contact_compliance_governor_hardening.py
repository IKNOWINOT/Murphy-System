"""
Test Suite: ContactComplianceGovernor Hardening

Verifies all security hardening controls applied to the ContactComplianceGovernor:

  1. contact_id validation — allowlist regex (CWE-20)
  2. contact_email validation — format + length cap (CWE-20)
  3. channel validation — closed allowlist (CWE-20)
  4. outreach_type validation — closed allowlist (CWE-20)
  5. contact_region validation — closed allowlist (CWE-20)
  6. reply_text length cap before regex (CWE-400 / ReDoS)
  7. message_metadata key count + key/value length caps (CWE-400)
  8. DNC hard cap enforcement (CWE-400)
  9. Tracked contacts hard cap + eviction (CWE-400)
 10. add_to_dnc reason / added_by field length caps (CWE-400)
 11. remove_from_dnc consent_proof length cap (CWE-400)
 12. load_state caps loaded collections to hard limits (CWE-400)
 13. Raw email never logged (PII protection)

Design Label: TEST-COMPL-001-HARDENING
Owner: Security Team / QA Team
"""

from __future__ import annotations

import logging
import os
from unittest.mock import patch

import pytest

os.environ.setdefault("MURPHY_ENV", "test")

from contact_compliance_governor import (
    ContactComplianceGovernor,
    DecisionType,
    Regulation,
    _MAX_ADDED_BY_LEN,
    _MAX_CONSENT_PROOF_LEN,
    _MAX_DNC_ENTRIES,
    _MAX_EMAIL_LEN,
    _MAX_META_KEY_LEN,
    _MAX_META_KEYS,
    _MAX_META_VALUE_LEN,
    _MAX_REASON_LEN,
    _MAX_REPLY_TEXT_LEN,
    _MAX_TRACKED_CONTACTS,
)
from persistence_manager import PersistenceManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gov():
    return ContactComplianceGovernor()


@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path))


_GOOD_META = {"has_unsubscribe_link": True, "has_physical_address": True}


def _validate(gov, contact_id="valid1", contact_email="u@example.com",
              channel="email", outreach_type="marketing",
              contact_region="US", **kwargs):
    return gov.validate_outreach(
        contact_id=contact_id,
        contact_email=contact_email,
        channel=channel,
        outreach_type=outreach_type,
        contact_region=contact_region,
        message_metadata=_GOOD_META,
        **kwargs,
    )


# ===========================================================================
# 1. contact_id validation  [CWE-20]
# ===========================================================================

class TestContactIdValidation:
    r"""contact_id must match ^[a-zA-Z0-9_@.\-]{1,200}$ (CWE-20)."""

    @pytest.mark.parametrize("bad_id", [
        "",                                   # empty
        "a" * 201,                            # too long
        "user'; DROP TABLE contacts;--",      # SQL injection
        "../../etc/passwd",                   # path traversal
        "<script>alert(1)</script>",          # XSS
        "user\x00null",                       # null byte
        "user name",                          # space
        "user|pipe",                          # pipe char
        "user&amp",                           # ampersand
    ])
    def test_invalid_contact_id_raises(self, gov, bad_id):
        with pytest.raises(ValueError):
            _validate(gov, contact_id=bad_id)

    @pytest.mark.parametrize("good_id", [
        "user123",
        "User_ID-42",
        "contact@domain",
        "user.name",
        "a" * 200,           # exactly at the 200-char limit
    ])
    def test_valid_contact_id_accepted(self, gov, good_id):
        # Should not raise; may BLOCK for regulatory reasons but won't ValueError
        try:
            _validate(gov, contact_id=good_id)
        except ValueError:
            pytest.fail(f"Valid contact_id '{good_id[:20]}' raised ValueError")


# ===========================================================================
# 2. contact_email validation  [CWE-20]
# ===========================================================================

class TestEmailValidation:
    """contact_email must be valid RFC-5321 format, max 254 chars (CWE-20)."""

    @pytest.mark.parametrize("bad_email", [
        "",                                 # empty
        "notanemail",                       # no @
        "a@",                               # no domain
        "@domain.com",                      # no local part
        "a" * 255 + "@b.com",              # exceeds 254 chars total
        "user @domain.com",                 # space in local
    ])
    def test_invalid_email_raises(self, gov, bad_email):
        with pytest.raises(ValueError):
            _validate(gov, contact_email=bad_email)

    def test_email_at_max_length_accepted(self, gov):
        # exactly 254 chars: local(248) + @b.com(6) = 254
        local = "a" * 248
        email = f"{local}@b.com"
        assert len(email) == 254
        try:
            _validate(gov, contact_email=email)
        except ValueError:
            pytest.fail("Email at exactly 254 chars should be accepted")

    def test_email_over_max_length_rejected(self, gov):
        local = "a" * 249
        email = f"{local}@b.com"  # 255 chars
        assert len(email) == 255
        with pytest.raises(ValueError):
            _validate(gov, contact_email=email)

    def test_valid_email_formats_accepted(self, gov):
        valid_emails = [
            "user@example.com",
            "user.name+tag@sub.domain.org",
            "u@b.io",
        ]
        for email in valid_emails:
            try:
                _validate(gov, contact_email=email)
            except ValueError:
                pytest.fail(f"Valid email '{email}' raised ValueError")


# ===========================================================================
# 3. channel validation  [CWE-20]
# ===========================================================================

class TestChannelValidation:
    """channel must be one of {email, sms, linkedin, phone} (CWE-20)."""

    @pytest.mark.parametrize("bad_channel", [
        "",
        "fax",
        "slack",
        "twitter",
        "'; DROP TABLE;",
        "email\x00sms",   # null byte injection
    ])
    def test_invalid_channel_raises(self, gov, bad_channel):
        with pytest.raises(ValueError):
            _validate(gov, channel=bad_channel)

    def test_channel_normalizes_uppercase(self, gov):
        """Uppercase channel values are normalized, not rejected."""
        # The validator normalizes to lowercase — "EMAIL" becomes "email"
        try:
            _validate(gov, channel="EMAIL")
        except ValueError:
            pytest.fail("Uppercase channel should be normalized, not rejected")

    @pytest.mark.parametrize("good_channel", ["email", "sms", "linkedin", "phone"])
    def test_valid_channels_accepted(self, gov, good_channel):
        kwargs = {}
        if good_channel in ("sms", "phone"):
            kwargs["has_explicit_consent"] = True
        try:
            gov.validate_outreach(
                contact_id="ch-test",
                contact_email="t@example.com",
                channel=good_channel,
                outreach_type="marketing",
                contact_region="US",
                has_explicit_consent=kwargs.get("has_explicit_consent", False),
                message_metadata=_GOOD_META,
            )
        except ValueError:
            pytest.fail(f"Valid channel '{good_channel}' raised ValueError")


# ===========================================================================
# 4. outreach_type validation  [CWE-20]
# ===========================================================================

class TestOutreachTypeValidation:
    """outreach_type must be in closed allowlist (CWE-20)."""

    @pytest.mark.parametrize("bad_type", [
        "",
        "spam",
        "bulk_mail",
        "cold outreach",    # space variant
        "'; DELETE FROM;",
        "marketing\x00",
    ])
    def test_invalid_outreach_type_raises(self, gov, bad_type):
        with pytest.raises(ValueError):
            _validate(gov, outreach_type=bad_type)

    @pytest.mark.parametrize("good_type", [
        "cold_outreach", "follow_up", "marketing", "service", "transactional",
    ])
    def test_valid_outreach_types_accepted(self, gov, good_type):
        try:
            _validate(gov, outreach_type=good_type, is_existing_customer=True)
        except ValueError:
            pytest.fail(f"Valid outreach_type '{good_type}' raised ValueError")


# ===========================================================================
# 5. contact_region validation  [CWE-20]
# ===========================================================================

class TestRegionValidation:
    """contact_region must be in {"", "US", "EU", "CA_US", "CA"} (CWE-20)."""

    @pytest.mark.parametrize("bad_region", [
        "UK",
        "GB",
        "AUSTRALIA",
        "'; DROP;",
    ])
    def test_invalid_region_raises(self, gov, bad_region):
        with pytest.raises(ValueError):
            _validate(gov, contact_region=bad_region)

    def test_region_normalizes_lowercase(self, gov):
        """Lowercase region values are normalized to uppercase, not rejected."""
        # "us".upper() == "US" which is valid
        try:
            _validate(gov, contact_region="us")
        except ValueError:
            pytest.fail("Lowercase region should be normalized, not rejected")

    @pytest.mark.parametrize("good_region", ["", "US", "EU", "CA_US", "CA"])
    def test_valid_regions_accepted(self, gov, good_region):
        kwargs = {}
        if good_region in ("EU", "CA"):
            kwargs["has_explicit_consent"] = True
        try:
            _validate(gov, contact_region=good_region, **kwargs)
        except ValueError:
            pytest.fail(f"Valid region '{good_region}' raised ValueError")


# ===========================================================================
# 6. reply_text length cap (CWE-400 / ReDoS)
# ===========================================================================

class TestReplyTextCap:
    """reply_text must be capped at _MAX_REPLY_TEXT_LEN before regex (CWE-400)."""

    def test_giant_reply_text_does_not_crash(self, gov):
        """50 MB of text must not cause OOM or ReDoS."""
        huge_text = "A" * 5_000_000  # 5 MB — well over the 50K cap
        # Should not raise, should not hang
        result = gov.detect_optout_intent(huge_text)
        assert result is False  # no opt-out signals

    def test_giant_text_with_optout_at_start_detected(self, gov):
        """Opt-out at position 0 of huge text is still detected after capping."""
        huge_text = "please unsubscribe me" + ("X" * 1_000_000)
        assert gov.detect_optout_intent(huge_text) is True

    def test_optout_beyond_cap_not_detected(self, gov):
        """Opt-out signal placed beyond the cap boundary is not detected."""
        # Place opt-out signal exactly after the cap boundary
        padding = "A" * (_MAX_REPLY_TEXT_LEN + 1)
        text = padding + " please unsubscribe me"
        assert gov.detect_optout_intent(text) is False

    def test_non_string_reply_text_returns_false(self, gov):
        assert gov.detect_optout_intent(None) is False  # type: ignore[arg-type]
        assert gov.detect_optout_intent(42) is False    # type: ignore[arg-type]

    def test_process_reply_caps_text(self, gov):
        """process_reply_for_optout should not raise on huge text."""
        huge = "A" * 10_000_000
        result = gov.process_reply_for_optout("user1", "u@example.com", huge)
        assert result is False


# ===========================================================================
# 7. message_metadata caps  [CWE-400]
# ===========================================================================

class TestMetadataCaps:
    """metadata key count and key/value lengths are bounded (CWE-400)."""

    def test_metadata_with_too_many_keys_does_not_crash(self, gov):
        """100 keys in metadata silently truncated to _MAX_META_KEYS."""
        meta = {f"key_{i}": f"val_{i}" for i in range(100)}
        meta["has_unsubscribe_link"] = True
        meta["has_physical_address"] = True
        sanitized = ContactComplianceGovernor._sanitize_metadata(meta)
        assert len(sanitized) <= _MAX_META_KEYS

    def test_metadata_long_key_truncated(self, gov):
        long_key = "k" * 500
        meta = {long_key: "value"}
        sanitized = ContactComplianceGovernor._sanitize_metadata(meta)
        for k in sanitized:
            assert len(k) <= _MAX_META_KEY_LEN

    def test_metadata_long_string_value_truncated(self, gov):
        meta = {"key": "v" * 5000}
        sanitized = ContactComplianceGovernor._sanitize_metadata(meta)
        for v in sanitized.values():
            if isinstance(v, str):
                assert len(v) <= _MAX_META_VALUE_LEN

    def test_metadata_non_dict_returns_empty(self, gov):
        assert ContactComplianceGovernor._sanitize_metadata(None) == {}
        assert ContactComplianceGovernor._sanitize_metadata("string") == {}  # type: ignore[arg-type]
        assert ContactComplianceGovernor._sanitize_metadata([1, 2]) == {}  # type: ignore[arg-type]

    def test_metadata_non_string_keys_skipped(self, gov):
        meta = {1: "value", "good_key": "val"}  # type: ignore[dict-item]
        sanitized = ContactComplianceGovernor._sanitize_metadata(meta)
        assert "good_key" in sanitized
        assert 1 not in sanitized


# ===========================================================================
# 8. DNC hard cap  [CWE-400]
# ===========================================================================

class TestDNCHardCap:
    """DNC list must not grow beyond _MAX_DNC_ENTRIES (CWE-400)."""

    def test_dnc_cap_raises_when_full(self, gov):
        """Exceeding the DNC cap must raise ValueError."""
        gov._MAX_DNC_ENTRIES_test = _MAX_DNC_ENTRIES  # reference check only
        # Override instance cap to something small for speed
        import contact_compliance_governor as mod
        original = mod._MAX_DNC_ENTRIES
        mod._MAX_DNC_ENTRIES = 5
        try:
            for i in range(5):
                gov.add_to_dnc(f"dnc{i}", f"dnc{i}@x.com", reason="test")
            with pytest.raises(ValueError, match="capacity"):
                gov.add_to_dnc("dnc99", "dnc99@x.com", reason="overflow test")
        finally:
            mod._MAX_DNC_ENTRIES = original

    def test_dnc_accepts_up_to_cap(self, gov):
        """Exactly at the cap should succeed."""
        import contact_compliance_governor as mod
        original = mod._MAX_DNC_ENTRIES
        mod._MAX_DNC_ENTRIES = 3
        try:
            for i in range(3):
                gov.add_to_dnc(f"cap{i}", f"cap{i}@x.com", reason="test")
            assert len(gov._dnc) == 3
        finally:
            mod._MAX_DNC_ENTRIES = original


# ===========================================================================
# 9. Tracked contacts hard cap + eviction  [CWE-400]
# ===========================================================================

class TestContactsHardCap:
    """Tracked contacts must not grow beyond _MAX_TRACKED_CONTACTS (CWE-400)."""

    def test_contacts_cap_evicts_oldest(self, gov):
        """When the contacts dict hits the cap, 10% are evicted."""
        import contact_compliance_governor as mod
        original = mod._MAX_TRACKED_CONTACTS
        mod._MAX_TRACKED_CONTACTS = 10
        try:
            for i in range(12):
                gov.validate_outreach(
                    contact_id=f"ct{i:03d}",
                    contact_email="u@example.com",
                    channel="email",
                    outreach_type="marketing",
                    contact_region="US",
                    message_metadata=_GOOD_META,
                )
            # After eviction, count should be at or below cap + 1 (one cycle)
            assert len(gov._contacts) <= 11
        finally:
            mod._MAX_TRACKED_CONTACTS = original


# ===========================================================================
# 10. add_to_dnc field length caps  [CWE-400]
# ===========================================================================

class TestDNCFieldCaps:
    """reason and added_by are capped before storage (CWE-400)."""

    def test_long_reason_is_truncated(self, gov):
        long_reason = "R" * 10_000
        entry = gov.add_to_dnc("trunc1", "t@x.com", reason=long_reason)
        assert len(entry.reason) <= _MAX_REASON_LEN

    def test_long_added_by_is_truncated(self, gov):
        long_added_by = "A" * 10_000
        entry = gov.add_to_dnc("trunc2", "t@x.com", reason="test", added_by=long_added_by)
        assert len(entry.added_by) <= _MAX_ADDED_BY_LEN

    def test_empty_reason_stored_as_empty_string(self, gov):
        entry = gov.add_to_dnc("trunc3", "t@x.com", reason="")
        assert entry.reason == ""


# ===========================================================================
# 11. remove_from_dnc consent_proof length cap  [CWE-400]
# ===========================================================================

class TestConsentProofCap:
    """consent_proof is capped before use (CWE-400)."""

    def test_very_long_consent_proof_accepted_and_capped(self, gov):
        gov.add_to_dnc("cp1", "cp@x.com", reason="test")
        long_proof = "P" * 10_000
        result = gov.remove_from_dnc_with_consent("cp1", consent_proof=long_proof)
        # Should succeed (long proof is valid, just capped internally)
        assert result is True
        assert gov.is_on_dnc("cp1") is False


# ===========================================================================
# 12. load_state caps loaded collections  [CWE-400]
# ===========================================================================

class TestLoadStateCaps:
    """load_state must not load more than the hard cap from persisted state."""

    def test_load_state_caps_dnc_entries(self, pm):
        """Persisted state with too many DNC entries is capped on load."""
        import contact_compliance_governor as mod
        original = mod._MAX_DNC_ENTRIES
        mod._MAX_DNC_ENTRIES = 5
        try:
            # Save a state manually with 10 DNC entries
            big_state = {
                "dnc": {
                    f"u{i}": {
                        "contact_id": f"u{i}",
                        "contact_email": f"u{i}@x.com",
                        "added_at": "2026-01-01T00:00:00+00:00",
                        "reason": "test",
                        "added_by": "system",
                        "consent_proof": None,
                    }
                    for i in range(10)
                },
                "contacts": {},
                "audit_log": [],
            }
            pm.save_document("contact_compliance_governor_state", big_state)
            gov = ContactComplianceGovernor(persistence_manager=pm)
            gov.load_state()
            assert len(gov._dnc) <= 5
        finally:
            mod._MAX_DNC_ENTRIES = original

    def test_load_state_caps_audit_log(self, pm):
        """Persisted audit log larger than MAX_AUDIT_ENTRIES is capped."""
        gov = ContactComplianceGovernor(persistence_manager=pm)
        gov._MAX_AUDIT_ENTRIES = 5
        big_state = {
            "dnc": {},
            "contacts": {},
            "audit_log": [{"x": i} for i in range(20)],
        }
        pm.save_document("contact_compliance_governor_state", big_state)
        gov.load_state()
        assert len(gov._audit_log) <= 5


# ===========================================================================
# 13. Email never written to log output  [PII protection]
# ===========================================================================

class TestEmailNotLogged:
    """Raw email addresses must not appear in any log records."""

    def test_add_to_dnc_does_not_log_email(self, gov, caplog):
        email = "secret-pii@private.example.com"
        with caplog.at_level(logging.DEBUG, logger="contact_compliance_governor"):
            gov.add_to_dnc("logtest1", email, reason="test")
        for record in caplog.records:
            assert email not in record.getMessage(), (
                f"PII (email) appeared in log: {record.getMessage()!r}"
            )

    def test_validate_outreach_does_not_log_email(self, gov, caplog):
        email = "pii-check@private.example.com"
        with caplog.at_level(logging.DEBUG, logger="contact_compliance_governor"):
            gov.validate_outreach(
                contact_id="logtest2",
                contact_email=email,
                channel="email",
                outreach_type="marketing",
                contact_region="US",
                message_metadata=_GOOD_META,
            )
        for record in caplog.records:
            assert email not in record.getMessage(), (
                f"PII (email) appeared in log: {record.getMessage()!r}"
            )

    def test_process_reply_does_not_log_email(self, gov, caplog):
        email = "reply-pii@private.example.com"
        with caplog.at_level(logging.DEBUG, logger="contact_compliance_governor"):
            gov.process_reply_for_optout("logtest3", email, "please unsubscribe")
        for record in caplog.records:
            assert email not in record.getMessage(), (
                f"PII (email) appeared in log: {record.getMessage()!r}"
            )
