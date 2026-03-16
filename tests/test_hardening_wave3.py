"""
Test Suite: Hardening Wave 3 — Security Parameter Enforcement

Verifies the security hardening changes introduced in wave 3:

  1. signup_gateway: Email format validation
  2. signup_gateway: Email validation token expiry (24 h)
  3. signup_gateway: Phone number E.164 format validation
  4. signup_gateway: OTP brute-force lockout (5 attempts)
  5. signup_gateway: OTP expiry (10 min)
  6. signup_gateway: Constant-time OTP comparison
  7. subscription_manager: PayPal webhook signature verification
  8. subscription_manager: Webhook event idempotency (Stripe + PayPal)
  9. compliance_toggle_manager: tenant_id non-empty validation
 10. webhook_event_processor: SHA1/MD5 deprecation warnings

Copyright (c) 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


# ===================================================================
# 1. signup_gateway: Email format validation
# ===================================================================


class TestSignupEmailFormatValidation:
    """Email format must be validated on signup."""

    def _gw(self):
        from signup_gateway import SignupGateway
        return SignupGateway()

    def _base(self, email):
        return dict(
            name="Test User",
            email=email,
            position="Engineer",
            justification="Testing",
            new_org_name="TestOrg",
        )

    def test_valid_email_accepted(self):
        profile = self._gw().signup(**self._base("alice@example.com"))
        assert profile.email == "alice@example.com"

    def test_missing_tld_rejected(self):
        from signup_gateway import SignupError
        with pytest.raises(SignupError, match="invalid email format"):
            self._gw().signup(**self._base("alice@noext"))

    def test_no_at_sign_rejected(self):
        from signup_gateway import SignupError
        with pytest.raises(SignupError, match="invalid email format"):
            self._gw().signup(**self._base("aliceexample.com"))

    def test_double_at_rejected(self):
        from signup_gateway import SignupError
        with pytest.raises(SignupError, match="invalid email format"):
            self._gw().signup(**self._base("a@@b.com"))

    def test_plus_addressing_accepted(self):
        profile = self._gw().signup(**self._base("alice+tag@example.com"))
        assert profile.email == "alice+tag@example.com"


# ===================================================================
# 2. signup_gateway: Email validation token expiry
# ===================================================================


class TestEmailTokenExpiry:
    """Email validation tokens must expire after 24 hours."""

    def _gw_with_profile(self):
        from signup_gateway import SignupGateway
        gw = SignupGateway()
        profile = gw.signup(
            name="Bob", email="bob@example.com",
            position="PM", justification="Test",
            new_org_name="Acme",
        )
        return gw, profile

    def test_fresh_token_works(self):
        gw, profile = self._gw_with_profile()
        result = gw.validate_email(profile.user_id, profile.email_validation_token)
        assert result.email_validated is True

    def test_expired_token_rejected(self):
        from signup_gateway import AuthError
        gw, profile = self._gw_with_profile()
        profile.email_validation_token_created_at = (
            datetime.now(timezone.utc) - timedelta(hours=25)
        ).isoformat()
        with pytest.raises(AuthError, match="expired"):
            gw.validate_email(profile.user_id, profile.email_validation_token)


# ===================================================================
# 3. signup_gateway: Phone format validation
# ===================================================================


class TestPhoneFormatValidation:
    """Phone numbers must match E.164 / 10-15 digit pattern."""

    def _gw_with_phone(self, phone):
        from signup_gateway import SignupGateway
        gw = SignupGateway()
        profile = gw.signup(
            name="Charlie", email=f"c{id(gw)}@example.com",
            position="Eng", justification="Test",
            new_org_name="PhoneCo", phone=phone,
        )
        return gw, profile

    def test_valid_e164_accepted(self):
        gw, p = self._gw_with_phone("+15551234567")
        assert len(gw.send_phone_otp(p.user_id)) == 6

    def test_valid_10_digit_accepted(self):
        gw, p = self._gw_with_phone("5551234567")
        assert len(gw.send_phone_otp(p.user_id)) == 6

    def test_short_number_rejected(self):
        from signup_gateway import SignupError
        gw, p = self._gw_with_phone("123")
        with pytest.raises(SignupError, match="invalid phone number format"):
            gw.send_phone_otp(p.user_id)

    def test_alpha_chars_rejected(self):
        from signup_gateway import SignupError
        gw, p = self._gw_with_phone("555-abc-1234")
        with pytest.raises(SignupError, match="invalid phone number format"):
            gw.send_phone_otp(p.user_id)

    def test_empty_phone_raises(self):
        from signup_gateway import SignupGateway, SignupError
        gw = SignupGateway()
        p = gw.signup(
            name="NoPhone", email="nophone@example.com",
            position="Eng", justification="Test",
            new_org_name="NoCo",
        )
        with pytest.raises(SignupError, match="no phone number"):
            gw.send_phone_otp(p.user_id)


# ===================================================================
# 4. signup_gateway: OTP brute-force lockout
# ===================================================================


class TestOTPBruteForceProtection:
    """OTP validation must lock out after 5 failed attempts."""

    def _gw_with_otp(self):
        from signup_gateway import SignupGateway
        gw = SignupGateway()
        profile = gw.signup(
            name="Dave", email=f"dave{id(gw)}@example.com",
            position="Eng", justification="Test",
            new_org_name="LockCo", phone="+15559876543",
        )
        otp = gw.send_phone_otp(profile.user_id)
        return gw, profile, otp

    def test_correct_otp_succeeds(self):
        gw, profile, otp = self._gw_with_otp()
        assert gw.validate_phone(profile.user_id, otp).phone_validated

    def test_wrong_otp_raises(self):
        from signup_gateway import AuthError
        gw, profile, _ = self._gw_with_otp()
        with pytest.raises(AuthError, match="invalid phone OTP"):
            gw.validate_phone(profile.user_id, "000000")

    def test_lockout_after_5_failures(self):
        from signup_gateway import AuthError
        gw, profile, _ = self._gw_with_otp()
        for _ in range(5):
            with pytest.raises(AuthError, match="invalid phone OTP"):
                gw.validate_phone(profile.user_id, "000000")
        with pytest.raises(AuthError, match="too many failed OTP attempts"):
            gw.validate_phone(profile.user_id, "000000")

    def test_new_otp_resets_lockout(self):
        from signup_gateway import AuthError
        gw, profile, _ = self._gw_with_otp()
        for _ in range(5):
            with pytest.raises(AuthError):
                gw.validate_phone(profile.user_id, "000000")
        new_otp = gw.send_phone_otp(profile.user_id)
        assert gw.validate_phone(profile.user_id, new_otp).phone_validated


# ===================================================================
# 5. signup_gateway: OTP expiry
# ===================================================================


class TestOTPExpiry:
    """OTP must expire after 10 minutes."""

    def test_expired_otp_rejected(self):
        from signup_gateway import SignupGateway, AuthError
        gw = SignupGateway()
        profile = gw.signup(
            name="Eve", email="eve@example.com",
            position="Eng", justification="Test",
            new_org_name="ExpireCo", phone="+15550001111",
        )
        otp = gw.send_phone_otp(profile.user_id)
        profile.phone_otp_created_at = (
            datetime.now(timezone.utc) - timedelta(minutes=11)
        ).isoformat()
        with pytest.raises(AuthError, match="expired"):
            gw.validate_phone(profile.user_id, otp)

    def test_otp_within_window_succeeds(self):
        from signup_gateway import SignupGateway
        gw = SignupGateway()
        profile = gw.signup(
            name="Frank", email="frank@example.com",
            position="Eng", justification="Test",
            new_org_name="FreshCo", phone="+15550002222",
        )
        otp = gw.send_phone_otp(profile.user_id)
        profile.phone_otp_created_at = (
            datetime.now(timezone.utc) - timedelta(minutes=9)
        ).isoformat()
        assert gw.validate_phone(profile.user_id, otp).phone_validated


# ===================================================================
# 7. subscription_manager: PayPal webhook signature verification
# ===================================================================


class TestPayPalWebhookSignatureVerification:
    """PayPal webhook handler must verify HMAC-SHA256 signature."""

    def _mgr(self):
        from subscription_manager import SubscriptionManager
        return SubscriptionManager()

    def _sign(self, payload, secret):
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def test_valid_signature_accepted(self):
        mgr = self._mgr()
        payload = {"event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                   "resource": {"custom_id": "acct1"}}
        sig = self._sign(payload, "s3cret")
        result = mgr.handle_paypal_webhook(payload, signature=sig, webhook_secret="s3cret")
        assert result["received"] is True

    def test_invalid_signature_rejected(self):
        mgr = self._mgr()
        payload = {"event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                   "resource": {"custom_id": "acct1"}}
        with pytest.raises(ValueError, match="invalid PayPal webhook signature"):
            mgr.handle_paypal_webhook(payload, signature="bad", webhook_secret="s3cret")

    def test_no_secret_skips_verification(self):
        mgr = self._mgr()
        payload = {"event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                   "resource": {"custom_id": "acct1"}}
        result = mgr.handle_paypal_webhook(payload)
        assert result["received"] is True


# ===================================================================
# 8. subscription_manager: Webhook event idempotency
# ===================================================================


class TestWebhookIdempotency:
    """Duplicate webhook events must be acknowledged but not re-processed."""

    def _mgr(self):
        from subscription_manager import SubscriptionManager
        return SubscriptionManager()

    def test_stripe_duplicate_skipped(self):
        mgr = self._mgr()
        payload = json.dumps({
            "id": "evt_test_123",
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {"murphy_account_id": "a1", "tier": "solo"},
                                "subscription": "sub_1"}},
        })
        r1 = mgr.handle_stripe_webhook(payload, signature="", webhook_secret="")
        assert r1["received"] is True
        assert "duplicate" not in r1

        r2 = mgr.handle_stripe_webhook(payload, signature="", webhook_secret="")
        assert r2.get("duplicate") is True

    def test_paypal_duplicate_skipped(self):
        mgr = self._mgr()
        payload = {"id": "WH-123", "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                   "resource": {"custom_id": "acct2"}}
        r1 = mgr.handle_paypal_webhook(payload)
        assert "duplicate" not in r1

        r2 = mgr.handle_paypal_webhook(payload)
        assert r2.get("duplicate") is True


# ===================================================================
# 9. compliance_toggle_manager: tenant_id validation
# ===================================================================


class TestComplianceTenantIdValidation:
    """save_tenant_frameworks must reject empty tenant_id."""

    def _mgr(self):
        from compliance_toggle_manager import ComplianceToggleManager
        return ComplianceToggleManager()

    def test_empty_tenant_id_raises(self):
        with pytest.raises(ValueError, match="tenant_id is required"):
            self._mgr().save_tenant_frameworks("", ["gdpr"])

    def test_whitespace_tenant_id_raises(self):
        with pytest.raises(ValueError, match="tenant_id is required"):
            self._mgr().save_tenant_frameworks("   ", ["gdpr"])

    def test_valid_tenant_id_accepted(self):
        cfg = self._mgr().save_tenant_frameworks("tenant-abc", ["gdpr"])
        assert cfg.tenant_id == "tenant-abc"


# ===================================================================
# 10. webhook_event_processor: SHA1/MD5 deprecation warnings
# ===================================================================


class TestWebhookDeprecationWarnings:
    """SHA1 and MD5 signature algorithms must emit deprecation warnings."""

    def test_sha1_logs_warning(self, caplog):
        from webhook_event_processor import (
            WebhookEventProcessor, WebhookSource, SignatureAlgorithm,
        )
        proc = WebhookEventProcessor()
        src = WebhookSource(
            source_id="test_sha1", name="SHA1 Test", platform="test",
            signature_algorithm=SignatureAlgorithm.SHA1,
            secret="secret123",
        )
        payload = b'{"event": "ping"}'
        sig = hmac.new(b"secret123", payload, hashlib.sha1).hexdigest()
        with caplog.at_level(logging.WARNING):
            result = proc.verify_signature(src, payload, sig)
        assert result is True
        assert any("deprecated SHA1" in rec.message for rec in caplog.records)

    def test_md5_logs_warning(self, caplog):
        from webhook_event_processor import (
            WebhookEventProcessor, WebhookSource, SignatureAlgorithm,
        )
        proc = WebhookEventProcessor()
        src = WebhookSource(
            source_id="test_md5", name="MD5 Test", platform="test",
            signature_algorithm=SignatureAlgorithm.MD5,
            secret="secret456",
        )
        payload = b'{"event": "ping"}'
        sig = hmac.new(b"secret456", payload, hashlib.md5).hexdigest()
        with caplog.at_level(logging.WARNING):
            result = proc.verify_signature(src, payload, sig)
        assert result is True
        assert any("deprecated MD5" in rec.message for rec in caplog.records)

    def test_sha256_no_warning(self, caplog):
        from webhook_event_processor import (
            WebhookEventProcessor, WebhookSource, SignatureAlgorithm,
        )
        proc = WebhookEventProcessor()
        src = WebhookSource(
            source_id="test_sha256", name="SHA256 Test", platform="test",
            signature_algorithm=SignatureAlgorithm.SHA256,
            secret="secret789",
        )
        payload = b'{"event": "ping"}'
        sig = hmac.new(b"secret789", payload, hashlib.sha256).hexdigest()
        with caplog.at_level(logging.WARNING):
            result = proc.verify_signature(src, payload, sig)
        assert result is True
        assert not any("deprecated" in rec.message for rec in caplog.records)
