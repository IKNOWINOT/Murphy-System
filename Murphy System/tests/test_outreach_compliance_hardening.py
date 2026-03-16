"""Hardening tests for outreach_compliance_integration.py (COMPL-002).

Validates all input-validation, sanitisation, and security invariants added
in the security hardening pass:
  - CWE-20  — improper input validation
  - CWE-158 — null-byte injection
  - CWE-770 — unbounded resource allocation (memory, string length)
  - PII-LOG  — raw email addresses must not appear in error log output
"""

from __future__ import annotations

import os
import logging
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------


from outreach_compliance_integration import (
    _ALLOWED_CHANNELS,
    _MAX_CONTACT_ID_LEN,
    _MAX_EMAIL_LEN,
    _MAX_OUTREACH_TYPE_LEN,
    _MAX_REGION_LEN,
    _MAX_REPLY_TEXT_LEN,
    _MAX_METADATA_KEYS,
    _MAX_METADATA_KEY_LEN,
    _MAX_METADATA_VALUE_LEN,
    _MAX_REGULATION_LEN,
    _MAX_MESSAGE_LEN,
    OutreachComplianceGate,
    _validate_contact_id,
    _validate_email,
    _validate_channel,
    _sanitize_str,
    _sanitize_metadata,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_governor(**overrides) -> MagicMock:
    gov = MagicMock()
    gov.is_dnc.return_value = overrides.get("is_dnc", False)
    gov.is_in_cooldown.return_value = overrides.get("is_in_cooldown", False)
    gov.cooldown_remaining_seconds.return_value = overrides.get("cooldown_remaining_seconds", 0)
    gov.check_regulatory.return_value = overrides.get(
        "check_regulatory", {"allowed": True, "regulation": "", "reason": ""}
    )
    gov.record_contact.return_value = None
    gov.add_to_dnc.return_value = None
    gov.last_contacted_at.return_value = None
    gov.consent_status.return_value = "unknown"
    return gov


def _make_gate(governor: Any = None) -> OutreachComplianceGate:
    gov = governor if governor is not None else _make_governor()
    return OutreachComplianceGate(governor=gov)


# ---------------------------------------------------------------------------
# Tests: _validate_contact_id (CWE-20, CWE-158)
# ---------------------------------------------------------------------------

class TestValidateContactId(unittest.TestCase):

    def test_valid_simple_id(self):
        self.assertEqual(_validate_contact_id("c-001"), "c-001")

    def test_valid_uuid_style(self):
        uid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        self.assertEqual(_validate_contact_id(uid), uid)

    def test_valid_email_as_id(self):
        self.assertEqual(_validate_contact_id("user@example.com"), "user@example.com")

    def test_null_bytes_stripped_then_validated(self):
        # "\x00" stripped; remaining "c1" is valid
        self.assertEqual(_validate_contact_id("c\x001"), "c1")

    def test_all_null_bytes_raises(self):
        with self.assertRaises(ValueError):
            _validate_contact_id("\x00\x00")

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError):
            _validate_contact_id("")

    def test_too_long_raises(self):
        with self.assertRaises(ValueError):
            _validate_contact_id("a" * (_MAX_CONTACT_ID_LEN + 1))

    def test_max_length_accepted(self):
        self.assertEqual(len(_validate_contact_id("a" * _MAX_CONTACT_ID_LEN)), _MAX_CONTACT_ID_LEN)

    def test_angle_bracket_raises(self):
        with self.assertRaises(ValueError):
            _validate_contact_id("<script>")

    def test_semicolon_raises(self):
        with self.assertRaises(ValueError):
            _validate_contact_id("c1;DROP TABLE contacts")

    def test_pipe_raises(self):
        with self.assertRaises(ValueError):
            _validate_contact_id("c1|id")

    def test_backtick_raises(self):
        with self.assertRaises(ValueError):
            _validate_contact_id("c1`ls`")

    def test_non_string_raises(self):
        with self.assertRaises(ValueError):
            _validate_contact_id(12345)  # type: ignore[arg-type]

    def test_space_raises(self):
        with self.assertRaises(ValueError):
            _validate_contact_id("c 1")


# ---------------------------------------------------------------------------
# Tests: _validate_email (CWE-20, CWE-158, RFC 5321)
# ---------------------------------------------------------------------------

class TestValidateEmail(unittest.TestCase):

    def test_valid_email_lowercased(self):
        self.assertEqual(_validate_email("User@Example.COM"), "user@example.com")

    def test_valid_email_with_plus(self):
        self.assertEqual(_validate_email("user+tag@example.com"), "user+tag@example.com")

    def test_null_bytes_stripped(self):
        self.assertEqual(_validate_email("user\x00@example.com"), "user@example.com")

    def test_leading_trailing_whitespace_stripped(self):
        self.assertEqual(_validate_email("  user@example.com  "), "user@example.com")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            _validate_email("")

    def test_whitespace_only_raises(self):
        with self.assertRaises(ValueError):
            _validate_email("   ")

    def test_too_long_raises(self):
        # localpart@domain where total length exceeds RFC 5321 limit
        long_local = "a" * 250
        with self.assertRaises(ValueError):
            _validate_email(f"{long_local}@x.com")

    def test_max_length_boundary(self):
        # Exactly 254 chars is valid: build a conforming address of that length
        domain = "example.com"  # 11 chars
        at = "@"                # 1 char
        local = "a" * (254 - len(domain) - len(at))  # 242 chars
        addr = f"{local}{at}{domain}"
        self.assertEqual(len(addr), 254)
        result = _validate_email(addr)
        self.assertEqual(result, addr.lower())

    def test_no_at_sign_raises(self):
        with self.assertRaises(ValueError):
            _validate_email("notanemail.com")

    def test_no_domain_raises(self):
        with self.assertRaises(ValueError):
            _validate_email("user@")

    def test_no_tld_raises(self):
        with self.assertRaises(ValueError):
            _validate_email("user@domain")

    def test_xss_in_localpart_raises(self):
        with self.assertRaises(ValueError):
            _validate_email("<script>@example.com")

    def test_sql_injection_raises(self):
        with self.assertRaises(ValueError):
            _validate_email("'; DROP TABLE users; --@example.com")

    def test_non_string_raises(self):
        with self.assertRaises(ValueError):
            _validate_email(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests: _validate_channel (allowlist enforcement)
# ---------------------------------------------------------------------------

class TestValidateChannel(unittest.TestCase):

    def test_all_allowed_channels_accepted(self):
        for ch in _ALLOWED_CHANNELS:
            with self.subTest(ch=ch):
                self.assertEqual(_validate_channel(ch), ch)

    def test_case_insensitive(self):
        self.assertEqual(_validate_channel("EMAIL"), "email")
        self.assertEqual(_validate_channel("SMS"), "sms")

    def test_unknown_channel_raises(self):
        with self.assertRaises(ValueError):
            _validate_channel("fax")

    def test_empty_channel_raises(self):
        with self.assertRaises(ValueError):
            _validate_channel("")

    def test_injection_in_channel_raises(self):
        with self.assertRaises(ValueError):
            _validate_channel("email; rm -rf /")

    def test_null_bytes_stripped_then_channel_validated(self):
        # "\x00email" → "email" after strip, then passes allowlist
        self.assertEqual(_validate_channel("\x00email"), "email")

    def test_non_string_raises(self):
        with self.assertRaises(ValueError):
            _validate_channel(42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests: _sanitize_str (CWE-158, CWE-770)
# ---------------------------------------------------------------------------

class TestSanitizeStr(unittest.TestCase):

    def test_null_bytes_stripped(self):
        self.assertEqual(_sanitize_str("hel\x00lo", 100), "hello")

    def test_truncated_to_max(self):
        result = _sanitize_str("a" * 200, 50)
        self.assertEqual(len(result), 50)

    def test_short_string_unchanged(self):
        self.assertEqual(_sanitize_str("hello", 100), "hello")

    def test_non_string_coerced(self):
        result = _sanitize_str(12345, 100)  # type: ignore[arg-type]
        self.assertEqual(result, "12345")

    def test_empty_string_ok(self):
        self.assertEqual(_sanitize_str("", 100), "")

    def test_multiple_null_bytes_all_stripped(self):
        self.assertEqual(_sanitize_str("\x00a\x00b\x00", 100), "ab")


# ---------------------------------------------------------------------------
# Tests: _sanitize_metadata (CWE-20, CWE-770)
# ---------------------------------------------------------------------------

class TestSanitizeMetadata(unittest.TestCase):

    def test_none_returns_none(self):
        self.assertIsNone(_sanitize_metadata(None))

    def test_valid_dict_passes_through(self):
        md = {"key": "value", "count": 42}
        result = _sanitize_metadata(md)
        self.assertEqual(result["key"], "value")
        self.assertEqual(result["count"], 42)

    def test_non_dict_raises(self):
        with self.assertRaises(ValueError):
            _sanitize_metadata("not a dict")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            _sanitize_metadata(["list"])  # type: ignore[arg-type]

    def test_too_many_keys_raises(self):
        big = {str(i): i for i in range(_MAX_METADATA_KEYS + 1)}
        with self.assertRaises(ValueError):
            _sanitize_metadata(big)

    def test_exactly_max_keys_accepted(self):
        md = {str(i): i for i in range(_MAX_METADATA_KEYS)}
        result = _sanitize_metadata(md)
        self.assertEqual(len(result), _MAX_METADATA_KEYS)

    def test_long_key_truncated(self):
        long_key = "k" * (_MAX_METADATA_KEY_LEN + 50)
        result = _sanitize_metadata({long_key: "v"})
        stored_key = next(iter(result))
        self.assertEqual(len(stored_key), _MAX_METADATA_KEY_LEN)

    def test_long_value_truncated(self):
        result = _sanitize_metadata({"k": "v" * (_MAX_METADATA_VALUE_LEN + 100)})
        self.assertEqual(len(result["k"]), _MAX_METADATA_VALUE_LEN)

    def test_null_bytes_stripped_from_key_and_value(self):
        result = _sanitize_metadata({"ke\x00y": "val\x00ue"})
        self.assertIn("key", result)
        self.assertEqual(result["key"], "value")

    def test_non_string_key_raises(self):
        with self.assertRaises(ValueError):
            _sanitize_metadata({1: "value"})  # type: ignore[arg-type]

    def test_non_string_value_not_mutated(self):
        """Non-string values (int, bool, etc.) pass through unchanged."""
        result = _sanitize_metadata({"count": 99, "flag": True})
        self.assertEqual(result["count"], 99)
        self.assertTrue(result["flag"])

    def test_empty_dict_accepted(self):
        self.assertEqual(_sanitize_metadata({}), {})


# ---------------------------------------------------------------------------
# Tests: check_and_record — input validation raises ValueError
# ---------------------------------------------------------------------------

class TestCheckAndRecordInputValidation(unittest.TestCase):

    def _gate(self):
        return _make_gate()

    def test_empty_contact_id_raises(self):
        with self.assertRaises(ValueError):
            self._gate().check_and_record("", "a@b.com", "email", "cold")

    def test_null_byte_contact_id_raises(self):
        with self.assertRaises(ValueError):
            self._gate().check_and_record("\x00\x00", "a@b.com", "email", "cold")

    def test_overlong_contact_id_raises(self):
        with self.assertRaises(ValueError):
            self._gate().check_and_record(
                "a" * (_MAX_CONTACT_ID_LEN + 1), "a@b.com", "email", "cold"
            )

    def test_invalid_chars_in_contact_id_raises(self):
        with self.assertRaises(ValueError):
            self._gate().check_and_record("<xss>", "a@b.com", "email", "cold")

    def test_malformed_email_raises(self):
        for bad in ("not-an-email", "@nodomain", "user@", "user@@host.com", ""):
            with self.subTest(email=bad):
                with self.assertRaises(ValueError):
                    self._gate().check_and_record("c1", bad, "email", "cold")

    def test_email_too_long_raises(self):
        long_email = "a" * 250 + "@x.com"
        with self.assertRaises(ValueError):
            self._gate().check_and_record("c1", long_email, "email", "cold")

    def test_unknown_channel_raises(self):
        with self.assertRaises(ValueError):
            self._gate().check_and_record("c1", "a@b.com", "fax", "cold")

    def test_injection_in_channel_raises(self):
        with self.assertRaises(ValueError):
            self._gate().check_and_record("c1", "a@b.com", "email;DROP TABLE", "cold")

    def test_valid_inputs_do_not_raise(self):
        """Confirm valid inputs still pass through cleanly."""
        gate = _make_gate()
        decision = gate.check_and_record("c-001", "user@example.com", "email", "cold")
        self.assertTrue(decision.allowed)

    def test_outreach_type_truncated_not_raised(self):
        """A very long outreach_type is silently truncated, not rejected."""
        gate = _make_gate()
        long_type = "x" * (_MAX_OUTREACH_TYPE_LEN + 200)
        decision = gate.check_and_record("c1", "a@b.com", "email", long_type)
        self.assertTrue(decision.allowed)

    def test_contact_region_truncated_not_raised(self):
        gate = _make_gate()
        long_region = "R" * (_MAX_REGION_LEN + 200)
        decision = gate.check_and_record(
            "c1", "a@b.com", "email", "cold", contact_region=long_region
        )
        self.assertTrue(decision.allowed)

    def test_invalid_metadata_raises(self):
        with self.assertRaises(ValueError):
            self._gate().check_and_record(
                "c1", "a@b.com", "email", "cold",
                message_metadata="not-a-dict",  # type: ignore[arg-type]
            )

    def test_metadata_too_many_keys_raises(self):
        big = {str(i): i for i in range(_MAX_METADATA_KEYS + 1)}
        with self.assertRaises(ValueError):
            self._gate().check_and_record(
                "c1", "a@b.com", "email", "cold", message_metadata=big
            )

    def test_validation_error_not_swallowed_by_fail_closed(self):
        """ValueError from input validation must NOT be caught and returned as BLOCK."""
        gate = _make_gate()
        with self.assertRaises(ValueError):
            gate.check_and_record("", "a@b.com", "email", "cold")


# ---------------------------------------------------------------------------
# Tests: process_reply — input validation
# ---------------------------------------------------------------------------

class TestProcessReplyInputValidation(unittest.TestCase):

    def test_empty_contact_id_raises(self):
        with self.assertRaises(ValueError):
            _make_gate().process_reply("", "a@b.com", "please stop")

    def test_invalid_email_raises(self):
        with self.assertRaises(ValueError):
            _make_gate().process_reply("c1", "not-an-email", "please stop")

    def test_null_bytes_stripped_from_reply(self):
        gate = _make_gate()
        # "stop\x00" with null stripped = "stop", still matches opt-out keyword
        result = gate.process_reply("c1", "a@b.com", "please stop\x00")
        self.assertTrue(result["opted_out"])

    def test_oversized_reply_truncated_not_raised(self):
        """A reply exceeding _MAX_REPLY_TEXT_LEN is truncated, not rejected."""
        gate = _make_gate()
        # Put the opt-out keyword in the first 50K, then pad with junk
        padded = "please stop " + "x" * (_MAX_REPLY_TEXT_LEN + 1000)
        result = gate.process_reply("c1", "a@b.com", padded)
        self.assertTrue(result["opted_out"])

    def test_opt_out_keyword_beyond_limit_not_detected(self):
        """Opt-out keyword hidden beyond the truncation limit is NOT detected."""
        gate = _make_gate()
        # Build a string where the opt-out keyword starts after the cap
        filler = "harmless " * (_MAX_REPLY_TEXT_LEN // len("harmless ") + 1)
        late_optout = filler[:_MAX_REPLY_TEXT_LEN] + " please stop"
        result = gate.process_reply("c1", "a@b.com", late_optout)
        # The keyword is beyond the cap, so should NOT be detected
        self.assertFalse(result["opted_out"])

    def test_non_string_reply_coerced(self):
        """Non-string reply_text is coerced to str without raising."""
        gate = _make_gate()
        result = gate.process_reply("c1", "a@b.com", 12345)  # type: ignore[arg-type]
        self.assertFalse(result["opted_out"])


# ---------------------------------------------------------------------------
# Tests: get_contact_status — input validation
# ---------------------------------------------------------------------------

class TestGetContactStatusInputValidation(unittest.TestCase):

    def test_empty_contact_id_raises(self):
        with self.assertRaises(ValueError):
            _make_gate().get_contact_status("", "a@b.com")

    def test_invalid_email_raises(self):
        with self.assertRaises(ValueError):
            _make_gate().get_contact_status("c1", "not-an-email")

    def test_valid_inputs_return_status(self):
        status = _make_gate().get_contact_status("c1", "a@b.com")
        self.assertIn("is_dnc", status)
        self.assertIn("cooldown_remaining", status)


# ---------------------------------------------------------------------------
# Tests: governor-supplied strings sanitised before storage
# ---------------------------------------------------------------------------

class TestGovernorSuppliedStringSanitization(unittest.TestCase):

    def test_long_regulation_string_truncated_in_decision(self):
        """A regulation string longer than _MAX_REGULATION_LEN is truncated."""
        gov = _make_governor(
            check_regulatory={
                "allowed": False,
                "regulation": "X" * (_MAX_REGULATION_LEN + 200),
                "reason": "test",
            }
        )
        gate = _make_gate(gov)
        decision = gate.check_and_record("c1", "a@b.com", "email", "cold")
        self.assertFalse(decision.allowed)
        self.assertLessEqual(len(decision.regulation_cited), _MAX_REGULATION_LEN)

    def test_long_reason_string_truncated_in_decision(self):
        """A reason string longer than _MAX_MESSAGE_LEN is truncated."""
        gov = _make_governor(
            check_regulatory={
                "allowed": False,
                "regulation": "GDPR",
                "reason": "Y" * (_MAX_MESSAGE_LEN + 500),
            }
        )
        gate = _make_gate(gov)
        decision = gate.check_and_record("c1", "a@b.com", "email", "cold")
        self.assertFalse(decision.allowed)
        self.assertLessEqual(len(decision.message), _MAX_MESSAGE_LEN)

    def test_null_bytes_stripped_from_regulation(self):
        gov = _make_governor(
            check_regulatory={
                "allowed": False,
                "regulation": "GD\x00PR",
                "reason": "no consent",
            }
        )
        gate = _make_gate(gov)
        decision = gate.check_and_record("c1", "a@b.com", "email", "cold")
        self.assertNotIn("\x00", decision.regulation_cited)

    def test_null_bytes_stripped_from_reason(self):
        gov = _make_governor(
            check_regulatory={
                "allowed": False,
                "regulation": "TCPA",
                "reason": "consent\x00 required",
            }
        )
        gate = _make_gate(gov)
        decision = gate.check_and_record("c1", "a@b.com", "email", "cold")
        self.assertNotIn("\x00", decision.message)


# ---------------------------------------------------------------------------
# Tests: PII — raw email must not appear in error log output
# ---------------------------------------------------------------------------

class TestPIILogSanitization(unittest.TestCase):

    def test_email_not_in_governor_error_log(self):
        """When governor.is_dnc() throws, the raw email must NOT appear in the log."""
        gov = MagicMock()
        gov.is_dnc.side_effect = RuntimeError("DB down")
        gate = _make_gate(gov)

        with self.assertLogs("outreach_compliance_integration", level=logging.ERROR) as cm:
            gate.check_and_record("c-999", "secret@private.com", "email", "cold")

        for line in cm.output:
            self.assertNotIn("secret@private.com", line,
                             "Raw email found in error log — PII exposure!")

    def test_email_not_in_dnc_failure_log(self):
        """When add_to_dnc() throws, raw email must NOT appear in the log."""
        gov = _make_governor()
        gov.add_to_dnc.side_effect = RuntimeError("write failed")
        gate = _make_gate(gov)

        with self.assertLogs("outreach_compliance_integration", level=logging.ERROR) as cm:
            gate.process_reply("c-999", "private@leak.com", "please stop")

        for line in cm.output:
            self.assertNotIn("private@leak.com", line,
                             "Raw email found in error log — PII exposure!")

    def test_email_not_in_status_failure_log(self):
        """When get_contact_status() governor call throws, raw email must not appear."""
        gov = MagicMock()
        gov.is_dnc.side_effect = RuntimeError("timeout")
        gate = _make_gate(gov)

        with self.assertLogs("outreach_compliance_integration", level=logging.ERROR) as cm:
            gate.get_contact_status("c-999", "hidden@email.com")

        for line in cm.output:
            self.assertNotIn("hidden@email.com", line,
                             "Raw email found in error log — PII exposure!")


# ---------------------------------------------------------------------------
# Tests: all channels in the allowlist still work end-to-end
# ---------------------------------------------------------------------------

class TestAllowedChannelsEndToEnd(unittest.TestCase):

    def test_all_allowed_channels_reach_governor(self):
        for ch in sorted(_ALLOWED_CHANNELS):
            with self.subTest(channel=ch):
                gov = _make_governor()
                gate = _make_gate(gov)
                decision = gate.check_and_record("c1", "a@b.com", ch, "cold")
                self.assertTrue(decision.allowed, f"Expected ALLOW for channel {ch!r}")
                gov.record_contact.assert_called_once()
                gov.record_contact.reset_mock()


if __name__ == "__main__":
    unittest.main()
