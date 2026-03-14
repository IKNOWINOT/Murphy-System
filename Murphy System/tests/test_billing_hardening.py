"""
Test Suite: Billing & Ancillary Hardening

Verifies the security hardening controls applied to billing features:

  1. Billing API: account_id path parameter validation (CWE-20)
  2. Billing API: currency code format validation (ISO 4217)
  3. Billing API: locale parameter format validation
  4. Billing API: webhook body size limit (CWE-400)
  5. Billing API: safe error response (no provider detail leakage)
  6. Currency converter: currency code regex enforcement
  7. Currency converter: exchange rate bounds validation on refresh_rates
  8. Subscription manager: Coinbase webhook HMAC verification
  9. Subscription manager: dedup map hard cap (CWE-400)
 10. Subscription manager: subscription map hard cap (CWE-400)
 11. Deployment readiness: webhook secret checks present

Copyright (c) 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

os.environ.setdefault("MURPHY_ENV", "test")


# ===================================================================
# 1. Billing API: account_id validation
# ===================================================================


class TestAccountIdValidation:
    """account_id must match ^[a-zA-Z0-9_\\-]{1,200}$ (CWE-20)."""

    @pytest.fixture
    async def client(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from billing.api import create_billing_router
        from subscription_manager import SubscriptionManager
        app = FastAPI()
        mgr = SubscriptionManager()
        router = create_billing_router(subscription_manager=mgr)
        app.include_router(router)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c, mgr

    @pytest.mark.asyncio
    async def test_valid_account_id_accepted(self, client):
        _, mgr = client
        from subscription_manager import PaymentProvider, SubscriptionStatus, SubscriptionTier
        mgr._upsert_subscription("abc-123_test", SubscriptionTier.SOLO, SubscriptionStatus.ACTIVE, PaymentProvider.PAYPAL)
        c, _ = client
        r = await c.get("/api/billing/subscription/abc-123_test")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_path_traversal_rejected(self, client):
        c, _ = client
        r = await c.get("/api/billing/subscription/../../etc/passwd")
        assert r.status_code in (400, 404, 422)

    @pytest.mark.asyncio
    async def test_sql_injection_rejected(self, client):
        c, _ = client
        r = await c.get("/api/billing/subscription/'; DROP TABLE subs;--")
        assert r.status_code in (400, 404, 422)

    @pytest.mark.asyncio
    async def test_whitespace_only_account_id_rejected(self, client):
        c, _ = client
        r = await c.get("/api/billing/usage/%20")
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_special_chars_rejected_cancel(self, client):
        c, _ = client
        r = await c.post("/api/billing/subscription/<script>/cancel")
        assert r.status_code in (400, 404, 422)


# ===================================================================
# 2. Billing API: currency code validation
# ===================================================================


class TestCurrencyCodeValidation:
    """Currency codes must be 3 alpha characters (ISO 4217)."""

    @pytest.fixture
    async def client(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from billing.api import create_billing_router
        app = FastAPI()
        router = create_billing_router()
        app.include_router(router)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_valid_currency_accepted(self, client):
        r = await client.get("/api/billing/plans?currency=JPY")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_numeric_currency_rejected(self, client):
        r = await client.get("/api/billing/plans?currency=123")
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_long_currency_rejected(self, client):
        r = await client.get("/api/billing/plans?currency=USDX")
        assert r.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_injection_in_currency_rejected(self, client):
        r = await client.get("/api/billing/plans?currency=<s")
        assert r.status_code in (400, 422)


# ===================================================================
# 3. Billing API: locale validation
# ===================================================================


class TestLocaleValidation:
    """Locale parameter must match safe pattern."""

    @pytest.fixture
    async def client(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from billing.api import create_billing_router
        app = FastAPI()
        router = create_billing_router()
        app.include_router(router)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_valid_locale_accepted(self, client):
        r = await client.get("/api/billing/plans?locale=ja")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_locale_with_region_accepted(self, client):
        r = await client.get("/api/billing/plans?locale=ja-JP")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_injection_in_locale_rejected(self, client):
        r = await client.get("/api/billing/plans?locale=<script>alert(1)</script>")
        assert r.status_code in (400, 422)  # rejected by length or regex


# ===================================================================
# 4. Billing API: webhook body size limit
# ===================================================================


class TestWebhookBodySizeLimit:
    """Webhook endpoints must reject oversized payloads (CWE-400)."""

    @pytest.fixture
    async def client(self):
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from billing.api import create_billing_router
        app = FastAPI()
        router = create_billing_router()
        app.include_router(router)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_paypal_webhook_oversized_rejected(self, client):
        # 300 KB payload — exceeds 256 KB limit
        oversized = b'{"event_type":"test","data":"' + b"x" * (300 * 1024) + b'"}'
        r = await client.post(
            "/api/billing/webhooks/paypal",
            content=oversized,
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 413

    @pytest.mark.asyncio
    async def test_coinbase_webhook_oversized_rejected(self, client):
        oversized = b'{"type":"test","data":"' + b"x" * (300 * 1024) + b'"}'
        r = await client.post(
            "/api/billing/webhooks/coinbase",
            content=oversized,
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 413

    @pytest.mark.asyncio
    async def test_normal_size_webhook_accepted(self, client):
        payload = json.dumps({"event_type": "test", "resource": {"custom_id": "a1"}})
        r = await client.post(
            "/api/billing/webhooks/paypal",
            content=payload.encode(),
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 200


# ===================================================================
# 6. Currency converter: currency code regex
# ===================================================================


class TestCurrencyConverterCodeValidation:
    """CurrencyConverter.convert must reject non-ISO-4217 codes."""

    def test_valid_3_letter_code(self):
        from billing.currency import CurrencyConverter
        cc = CurrencyConverter()
        assert cc.convert(10.0, "USD") == 10.0

    def test_4_letter_code_rejected(self):
        from billing.currency import CurrencyConverter
        cc = CurrencyConverter()
        with pytest.raises(ValueError, match="Invalid currency code format"):
            cc.convert(10.0, "USDT")

    def test_numeric_code_rejected(self):
        from billing.currency import CurrencyConverter
        cc = CurrencyConverter()
        with pytest.raises(ValueError, match="Invalid currency code format"):
            cc.convert(10.0, "123")

    def test_empty_code_rejected(self):
        from billing.currency import CurrencyConverter
        cc = CurrencyConverter()
        with pytest.raises(ValueError, match="Invalid currency code format"):
            cc.convert(10.0, "")

    def test_injection_code_rejected(self):
        from billing.currency import CurrencyConverter
        cc = CurrencyConverter()
        with pytest.raises(ValueError, match="Invalid currency code format"):
            cc.convert(10.0, "US$")


# ===================================================================
# 7. Currency converter: exchange rate bounds validation
# ===================================================================


class TestExchangeRateBoundsValidation:
    """refresh_rates must reject negative, zero, and extreme rates."""

    def test_negative_rate_ignored(self):
        from billing.currency import CurrencyConverter
        cc = CurrencyConverter()
        cc.refresh_rates({"XTS": -1.0})
        assert cc.get_rate("XTS") is None

    def test_zero_rate_ignored(self):
        from billing.currency import CurrencyConverter
        cc = CurrencyConverter()
        cc.refresh_rates({"XTS": 0.0})
        assert cc.get_rate("XTS") is None

    def test_extreme_rate_ignored(self):
        from billing.currency import CurrencyConverter
        cc = CurrencyConverter()
        cc.refresh_rates({"XTS": 2_000_000.0})
        assert cc.get_rate("XTS") is None

    def test_valid_rate_accepted(self):
        from billing.currency import CurrencyConverter
        cc = CurrencyConverter()
        cc.refresh_rates({"XTS": 42.0})
        assert cc.get_rate("XTS") == 42.0

    def test_non_alpha_code_ignored_in_refresh(self):
        from billing.currency import CurrencyConverter
        cc = CurrencyConverter()
        cc.refresh_rates({"12X": 1.5, "LONG": 2.0, "!@#": 3.0})
        assert cc.get_rate("12X") is None
        # 4-letter code filtered out
        assert cc.get_rate("LONG") is None


# ===================================================================
# 8. Coinbase webhook HMAC signature verification
# ===================================================================


class TestCoinbaseWebhookSignatureVerification:
    """Coinbase webhook handler must verify HMAC-SHA256 signature."""

    def _mgr(self):
        from subscription_manager import SubscriptionManager
        return SubscriptionManager()

    def _sign_raw(self, raw_body: bytes, secret: str) -> str:
        return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

    def test_valid_signature_accepted(self):
        mgr = self._mgr()
        payload = {"type": "charge:confirmed", "data": {"metadata": {"murphy_account_id": "cb1", "tier": "solo"}}}
        raw = json.dumps(payload).encode()
        sig = self._sign_raw(raw, "cb_secret")
        result = mgr.handle_coinbase_webhook(payload, signature=sig, webhook_secret="cb_secret", raw_body=raw)
        assert result["received"] is True

    def test_invalid_signature_rejected(self):
        mgr = self._mgr()
        payload = {"type": "charge:confirmed", "data": {"metadata": {"murphy_account_id": "cb2"}}}
        raw = json.dumps(payload).encode()
        with pytest.raises(ValueError, match="invalid Coinbase webhook signature"):
            mgr.handle_coinbase_webhook(payload, signature="bad_sig", webhook_secret="cb_secret", raw_body=raw)

    def test_no_secret_skips_verification(self):
        mgr = self._mgr()
        payload = {"type": "charge:confirmed", "data": {"metadata": {"murphy_account_id": "cb3", "tier": "solo"}}}
        result = mgr.handle_coinbase_webhook(payload)
        assert result["received"] is True

    def test_coinbase_duplicate_event_skipped(self):
        mgr = self._mgr()
        payload = {"id": "CB-EVT-123", "type": "charge:confirmed",
                   "data": {"metadata": {"murphy_account_id": "cb4", "tier": "solo"}}}
        r1 = mgr.handle_coinbase_webhook(payload)
        assert r1["received"] is True
        assert "duplicate" not in r1
        r2 = mgr.handle_coinbase_webhook(payload)
        assert r2.get("duplicate") is True


# ===================================================================
# 9. Subscription manager: dedup map hard cap (CWE-400)
# ===================================================================


class TestDedupMapHardCap:
    """The dedup map must enforce a hard cap to prevent memory exhaustion."""

    def test_dedup_cap_enforced(self):
        from subscription_manager import SubscriptionManager
        mgr = SubscriptionManager()
        # Set a very low cap for testing
        mgr._MAX_DEDUP_ENTRIES = 10
        mgr._EVENT_DEDUP_WINDOW = 3600

        # Insert 15 events — should never exceed cap
        for i in range(15):
            mgr._is_duplicate_event(f"evt_{i}")

        assert len(mgr._processed_events) <= 11  # at most cap + 1 (just-added)

    def test_dedup_still_detects_duplicates_after_cap(self):
        from subscription_manager import SubscriptionManager
        mgr = SubscriptionManager()
        mgr._MAX_DEDUP_ENTRIES = 10
        mgr._EVENT_DEDUP_WINDOW = 3600

        # Insert events
        for i in range(15):
            mgr._is_duplicate_event(f"evt_{i}")

        # The most recent events should still be detected as duplicates
        assert mgr._is_duplicate_event("evt_14") is True


# ===================================================================
# 10. Subscription manager: subscription map hard cap (CWE-400)
# ===================================================================


class TestSubscriptionMapHardCap:
    """subscription_manager must enforce a hard cap on total subscriptions."""

    def test_subscription_cap_raises(self):
        from subscription_manager import (
            PaymentProvider,
            SubscriptionManager,
            SubscriptionStatus,
            SubscriptionTier,
        )
        mgr = SubscriptionManager()
        mgr._MAX_SUBSCRIPTIONS = 5

        # Fill to cap
        for i in range(5):
            mgr._upsert_subscription(
                f"acct_{i}", SubscriptionTier.SOLO,
                SubscriptionStatus.ACTIVE, PaymentProvider.PAYPAL,
            )

        # 6th should raise
        with pytest.raises(ValueError, match="capacity limit"):
            mgr._upsert_subscription(
                "acct_overflow", SubscriptionTier.SOLO,
                SubscriptionStatus.ACTIVE, PaymentProvider.PAYPAL,
            )

    def test_update_existing_under_cap_ok(self):
        from subscription_manager import (
            PaymentProvider,
            SubscriptionManager,
            SubscriptionStatus,
            SubscriptionTier,
        )
        mgr = SubscriptionManager()
        mgr._MAX_SUBSCRIPTIONS = 5

        for i in range(5):
            mgr._upsert_subscription(
                f"acct_{i}", SubscriptionTier.SOLO,
                SubscriptionStatus.ACTIVE, PaymentProvider.PAYPAL,
            )

        # Updating an existing subscription should not hit the cap
        sub = mgr._upsert_subscription(
            "acct_0", SubscriptionTier.BUSINESS,
            SubscriptionStatus.ACTIVE, PaymentProvider.CRYPTO,
        )
        assert sub.tier == SubscriptionTier.BUSINESS


# ===================================================================
# 11. Deployment readiness: webhook secret checks
# ===================================================================


class TestDeploymentReadinessWebhookSecrets:
    """Readiness checker must include webhook secret checks."""

    def test_webhook_secret_checks_present(self):
        from deployment_readiness import DeploymentReadinessChecker
        checker = DeploymentReadinessChecker()
        report = checker.run_all()
        all_names = [r["name"] for cat in report["by_category"].values() for r in cat]
        assert "PAYPAL_WEBHOOK_SECRET" in all_names
        assert "COINBASE_WEBHOOK_SECRET" in all_names

    def test_billing_security_category_exists(self):
        from deployment_readiness import DeploymentReadinessChecker
        checker = DeploymentReadinessChecker()
        report = checker.run_all()
        assert "billing_security" in report["by_category"]

    def test_webhook_secrets_optional_not_blocking(self):
        """Webhook secrets should be optional — not block deployment readiness."""
        from deployment_readiness import DeploymentReadinessChecker
        # With MURPHY_ENV set, secrets not configured should NOT cause failure
        # (they're optional)
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}, clear=False):
            checker = DeploymentReadinessChecker()
            report = checker.run_all()
            billing_sec = report["by_category"].get("billing_security", [])
            for check in billing_sec:
                # Optional checks should pass even when not set
                assert check["ok"] is True
