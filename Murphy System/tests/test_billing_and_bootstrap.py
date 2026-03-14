"""
Tests for Billing API, Currency Conversion, Deployment Readiness,
and Self-Automation Bootstrap — Murphy System.

Covers:
  - Multi-currency conversion with static rate table
  - Japan 10% discount (by JPY currency and ja locale)
  - Billing API endpoints (plans, checkout, crypto, webhooks, CRUD, usage)
  - Currencies endpoint
  - Deployment readiness checker
  - Self-automation bootstrap stages

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("MURPHY_ENV", "test")

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# Currency Conversion
# ═══════════════════════════════════════════════════════════════════════════

from billing.currency import CurrencyConverter, get_converter


class TestCurrencyConversion:
    def test_usd_is_identity(self):
        cc = CurrencyConverter()
        assert cc.convert(29.00, "USD") == 29.00

    def test_eur_conversion(self):
        cc = CurrencyConverter()
        result = cc.convert(29.00, "EUR")
        assert result > 0
        assert result != 29.00  # 29 USD ≈ 26.68 EUR (rate 0.92)

    def test_jpy_rounded_to_integer(self):
        cc = CurrencyConverter()
        result = cc.convert(29.00, "JPY")
        assert isinstance(result, float)
        assert result == round(result)  # no decimals

    def test_krw_rounded_to_integer(self):
        cc = CurrencyConverter()
        result = cc.convert(29.00, "KRW")
        assert result == round(result)

    def test_unsupported_currency_raises(self):
        cc = CurrencyConverter()
        with pytest.raises(ValueError, match="Unsupported currency"):
            cc.convert(29.00, "XYZ")

    def test_case_insensitive_currency(self):
        cc = CurrencyConverter()
        assert cc.convert(29.00, "eur") == cc.convert(29.00, "EUR")

    def test_custom_rates(self):
        cc = CurrencyConverter(rates={"USD": 1.0, "XTS": 2.5})
        assert cc.convert(10.0, "XTS") == 25.0


class TestJapanDiscount:
    def test_jpy_currency_triggers_discount(self):
        cc = CurrencyConverter()
        result = cc.localize(100.0, "JPY")
        assert result["discount_applied"] is True
        assert result["discount_percent"] == 10.0
        # 100 USD * 0.90 * JPY rate
        expected = cc.convert(90.0, "JPY")
        assert result["amount"] == expected

    def test_ja_locale_triggers_discount(self):
        cc = CurrencyConverter()
        result = cc.localize(100.0, "USD", locale="ja")
        assert result["discount_applied"] is True
        assert result["discount_percent"] == 10.0
        assert result["amount"] == 90.0  # 100 * 0.9 * 1.0 (USD)

    def test_ja_jp_locale_triggers_discount(self):
        cc = CurrencyConverter()
        result = cc.localize(100.0, "USD", locale="ja-JP")
        assert result["discount_applied"] is True
        assert result["discount_percent"] == 10.0

    def test_no_discount_for_usd(self):
        cc = CurrencyConverter()
        result = cc.localize(100.0, "USD", locale="en")
        assert result["discount_applied"] is False
        assert result["discount_percent"] == 0.0
        assert result["amount"] == 100.0

    def test_no_discount_for_eur(self):
        cc = CurrencyConverter()
        result = cc.localize(100.0, "EUR", locale="de")
        assert result["discount_applied"] is False

    def test_localize_returns_original_usd(self):
        cc = CurrencyConverter()
        result = cc.localize(29.00, "GBP")
        assert result["original_usd"] == 29.00

    def test_discount_reason_is_japan_regional(self):
        cc = CurrencyConverter()
        result = cc.localize(29.00, "JPY")
        assert result["discount_reason"] == "japan_regional"

    def test_no_discount_reason_is_none(self):
        cc = CurrencyConverter()
        result = cc.localize(29.00, "USD")
        assert result["discount_reason"] is None


class TestCurrencyConverterMethods:
    def test_list_currencies(self):
        cc = CurrencyConverter()
        currencies = cc.list_currencies()
        assert "USD" in currencies
        assert "JPY" in currencies
        assert "EUR" in currencies
        assert currencies == sorted(currencies)

    def test_get_rate_known(self):
        cc = CurrencyConverter()
        assert cc.get_rate("USD") == 1.0
        assert cc.get_rate("jpy") is not None

    def test_get_rate_unknown(self):
        cc = CurrencyConverter()
        assert cc.get_rate("XYZ") is None

    def test_refresh_rates(self):
        cc = CurrencyConverter()
        cc.refresh_rates({"USD": 1.0, "XTS": 42.0})
        assert cc.get_rate("XTS") == 42.0

    def test_get_status(self):
        cc = CurrencyConverter()
        status = cc.get_status()
        assert "supported_currencies" in status
        assert "japan_discount" in status
        assert status["japan_discount"] == "10%"

    def test_singleton(self):
        c1 = get_converter()
        c2 = get_converter()
        assert c1 is c2


# ═══════════════════════════════════════════════════════════════════════════
# Billing API (routes)
# ═══════════════════════════════════════════════════════════════════════════

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from billing.api import create_billing_router
from subscription_manager import (
    SubscriptionManager,
    SubscriptionTier,
    SubscriptionStatus,
    BillingInterval,
    PaymentProvider,
)
from unittest.mock import patch, MagicMock


def _make_test_app() -> FastAPI:
    """Build a minimal FastAPI app with the billing router."""
    app = FastAPI()
    mgr = SubscriptionManager()
    router = create_billing_router(subscription_manager=mgr)
    app.include_router(router)
    app._test_mgr = mgr  # expose for test manipulation
    return app


def _mock_paypal_response():
    """Return a mock requests.post response for PayPal subscription creation."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "id": "I-MOCK123",
        "links": [
            {"rel": "approve", "href": "https://www.sandbox.paypal.com/webapps/billing/subscriptions?ba_token=MOCK"},
            {"rel": "self", "href": "https://api-m.sandbox.paypal.com/v1/billing/subscriptions/I-MOCK123"},
        ],
    }
    return mock_resp


def _mock_paypal_token_response():
    """Return a mock response for PayPal OAuth token exchange."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"access_token": "mock_token_123"}
    return mock_resp


def _mock_coinbase_response():
    """Return a mock response for Coinbase Commerce charge creation."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "data": {"hosted_url": "https://commerce.coinbase.com/charges/MOCK123"}
    }
    return mock_resp


@pytest.fixture
async def billing_client():
    app = _make_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app._test_mgr


class TestBillingPlansEndpoint:
    @pytest.mark.asyncio
    async def test_list_plans_default_usd(self, billing_client):
        client, _ = billing_client
        r = await client.get("/api/billing/plans")
        assert r.status_code == 200
        data = r.json()
        assert "plans" in data
        assert len(data["plans"]) >= 4
        assert data["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_list_plans_jpy_has_discount(self, billing_client):
        client, _ = billing_client
        r = await client.get("/api/billing/plans?currency=JPY&locale=ja")
        assert r.status_code == 200
        data = r.json()
        solo = next(p for p in data["plans"] if p["tier"] == "solo")
        assert solo["local_monthly"]["discount_applied"] is True
        assert solo["local_monthly"]["discount_percent"] == 10.0

    @pytest.mark.asyncio
    async def test_list_plans_eur_no_discount(self, billing_client):
        client, _ = billing_client
        r = await client.get("/api/billing/plans?currency=EUR")
        assert r.status_code == 200
        data = r.json()
        solo = next(p for p in data["plans"] if p["tier"] == "solo")
        assert solo["local_monthly"]["discount_applied"] is False


class TestCurrenciesEndpoint:
    @pytest.mark.asyncio
    async def test_list_currencies(self, billing_client):
        client, _ = billing_client
        r = await client.get("/api/billing/currencies")
        assert r.status_code == 200
        data = r.json()
        assert "currencies" in data
        assert "JPY" in data["currencies"]
        assert "USD" in data["currencies"]
        assert data["default"] == "USD"

    @pytest.mark.asyncio
    async def test_regional_discounts_listed(self, billing_client):
        client, _ = billing_client
        r = await client.get("/api/billing/currencies")
        data = r.json()
        discounts = data["regional_discounts"]
        assert any(d["locale"] == "ja" for d in discounts)
        japan = next(d for d in discounts if d["locale"] == "ja")
        assert japan["discount_percent"] == 10


class TestBillingCheckout:
    @pytest.mark.asyncio
    async def test_paypal_checkout(self, billing_client):
        client, _ = billing_client
        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_paypal_token_response(),  # token call
                _mock_paypal_response(),         # subscription call
            ]
            r = await client.post("/api/billing/checkout", json={
                "account_id": "test_acc",
                "tier": "solo",
                "interval": "monthly",
            })
        assert r.status_code == 200
        data = r.json()
        assert data["provider"] == "paypal"
        assert "approval_url" in data
        assert data["tier"] == "solo"
        assert "price" in data

    @pytest.mark.asyncio
    async def test_paypal_checkout_with_jpy(self, billing_client):
        client, _ = billing_client
        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                _mock_paypal_token_response(),
                _mock_paypal_response(),
            ]
            r = await client.post("/api/billing/checkout", json={
                "account_id": "jp_acc",
                "tier": "business",
                "interval": "monthly",
                "currency": "JPY",
                "locale": "ja",
            })
        assert r.status_code == 200
        data = r.json()
        assert data["price"]["discount_applied"] is True
        assert data["price"]["currency"] == "JPY"

    @pytest.mark.asyncio
    async def test_crypto_checkout(self, billing_client):
        client, _ = billing_client
        with patch("requests.post") as mock_post:
            mock_post.return_value = _mock_coinbase_response()
            r = await client.post("/api/billing/checkout/crypto", json={
                "account_id": "crypto_acc",
                "tier": "professional",
                "interval": "annual",
            })
        assert r.status_code == 200
        data = r.json()
        assert data["provider"] == "crypto"
        assert "hosted_url" in data
        assert "price" in data

    @pytest.mark.asyncio
    async def test_enterprise_tier_rejected(self, billing_client):
        client, _ = billing_client
        # Enterprise not allowed for self-serve checkout
        r = await client.post("/api/billing/checkout", json={
            "account_id": "ent_acc",
            "tier": "enterprise",  # not in pattern
            "interval": "monthly",
        })
        assert r.status_code == 422  # pydantic validation error


class TestBillingWebhook:
    @pytest.mark.asyncio
    async def test_paypal_webhook_activates(self, billing_client):
        client, mgr = billing_client
        # Pre-create subscription
        mgr._upsert_subscription("wh_acc", SubscriptionTier.SOLO, SubscriptionStatus.TRIAL, PaymentProvider.PAYPAL)
        payload = {
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {"custom_id": "wh_acc"},
        }
        r = await client.post("/api/billing/webhooks/paypal", json=payload)
        assert r.status_code == 200
        assert r.json()["received"] is True
        sub = mgr.get_subscription("wh_acc")
        assert sub.status == SubscriptionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_coinbase_webhook_confirmed(self, billing_client):
        client, mgr = billing_client
        payload = {
            "type": "charge:confirmed",
            "data": {
                "code": "CB_CHARGE_1",
                "metadata": {"murphy_account_id": "cb_wh_acc", "tier": "business"},
            },
        }
        r = await client.post("/api/billing/webhooks/coinbase", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["received"] is True
        assert data["event_type"] == "charge:confirmed"
        sub = mgr.get_subscription("cb_wh_acc")
        assert sub is not None
        assert sub.tier == SubscriptionTier.BUSINESS
        assert sub.status == SubscriptionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_coinbase_webhook_failed(self, billing_client):
        client, mgr = billing_client
        mgr._upsert_subscription("cb_fail_acc", SubscriptionTier.SOLO, SubscriptionStatus.ACTIVE, PaymentProvider.CRYPTO)
        payload = {
            "type": "charge:failed",
            "data": {"metadata": {"murphy_account_id": "cb_fail_acc"}},
        }
        r = await client.post("/api/billing/webhooks/coinbase", json=payload)
        assert r.status_code == 200
        sub = mgr.get_subscription("cb_fail_acc")
        assert sub.status == SubscriptionStatus.PAST_DUE

    @pytest.mark.asyncio
    async def test_coinbase_webhook_invalid_json(self, billing_client):
        client, _ = billing_client
        r = await client.post(
            "/api/billing/webhooks/coinbase",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 400


class TestBillingSubscriptionCrud:
    @pytest.mark.asyncio
    async def test_get_subscription(self, billing_client):
        client, mgr = billing_client
        mgr._upsert_subscription("crud_acc", SubscriptionTier.BUSINESS, SubscriptionStatus.ACTIVE, PaymentProvider.PAYPAL)
        r = await client.get("/api/billing/subscription/crud_acc")
        assert r.status_code == 200
        data = r.json()
        assert data["account_id"] == "crud_acc"
        assert data["tier"] == "business"

    @pytest.mark.asyncio
    async def test_get_subscription_not_found(self, billing_client):
        client, _ = billing_client
        r = await client.get("/api/billing/subscription/nobody")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_subscription(self, billing_client):
        client, mgr = billing_client
        mgr._upsert_subscription("cancel_acc", SubscriptionTier.SOLO, SubscriptionStatus.ACTIVE, PaymentProvider.PAYPAL)
        r = await client.post("/api/billing/subscription/cancel_acc/cancel")
        assert r.status_code == 200
        data = r.json()
        assert data["cancel_at_period_end"] is True

    @pytest.mark.asyncio
    async def test_upgrade_subscription(self, billing_client):
        client, mgr = billing_client
        mgr._upsert_subscription("up_acc", SubscriptionTier.SOLO, SubscriptionStatus.ACTIVE, PaymentProvider.PAYPAL)
        r = await client.post("/api/billing/subscription/up_acc/upgrade", json={
            "new_tier": "professional",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["tier"] == "professional"


class TestBillingUsage:
    @pytest.mark.asyncio
    async def test_usage_endpoint(self, billing_client):
        client, mgr = billing_client
        mgr._upsert_subscription("usage_acc", SubscriptionTier.BUSINESS, SubscriptionStatus.ACTIVE, PaymentProvider.PAYPAL)
        r = await client.get("/api/billing/usage/usage_acc")
        assert r.status_code == 200
        data = r.json()
        assert data["account_id"] == "usage_acc"
        assert data["max_users"] == 10


# ═══════════════════════════════════════════════════════════════════════════
# Deployment Readiness
# ═══════════════════════════════════════════════════════════════════════════

from deployment_readiness import DeploymentReadinessChecker


class TestDeploymentReadiness:
    def test_run_all_returns_report(self):
        checker = DeploymentReadinessChecker()
        report = checker.run_all()
        assert "ready" in report
        assert "total_checks" in report
        assert "failures" in report
        assert "by_category" in report
        assert "checked_at" in report

    def test_get_status_summary(self):
        checker = DeploymentReadinessChecker()
        status = checker.get_status()
        assert "ready" in status
        assert "checks_total" in status
        assert "failures" in status
        assert isinstance(status["failures"], list)

    def test_add_custom_check(self):
        checker = DeploymentReadinessChecker()
        checker.add_check("custom_ok", "test", lambda: (True, "all good"))
        report = checker.run_all()
        names = [r["name"] for cat in report["by_category"].values() for r in cat]
        assert "custom_ok" in names

    def test_failing_check_shows_in_failures(self):
        checker = DeploymentReadinessChecker()
        checker.add_check("always_fail", "test", lambda: (False, "broken"))
        report = checker.run_all()
        fail_names = [f["name"] for f in report["failures"]]
        assert "always_fail" in fail_names

    def test_exception_in_check_caught(self):
        def _raise():
            raise RuntimeError("boom")
        checker = DeploymentReadinessChecker()
        checker.add_check("explode", "test", _raise)
        report = checker.run_all()
        fail_names = [f["name"] for f in report["failures"]]
        assert "explode" in fail_names

    def test_module_import_check(self):
        checker = DeploymentReadinessChecker()
        report = checker.run_all()
        module_checks = report["by_category"].get("module", [])
        names = [c["name"] for c in module_checks]
        assert "subscription_manager" in names


# ═══════════════════════════════════════════════════════════════════════════
# Self-Automation Bootstrap
# ═══════════════════════════════════════════════════════════════════════════

from self_automation_bootstrap import SelfAutomationBootstrap


class TestSelfAutomationBootstrap:
    def test_run_returns_report(self):
        boot = SelfAutomationBootstrap()
        report = boot.run()
        assert "all_ready" in report
        assert "stages" in report
        assert "deployment" in report["stages"]
        assert "revenue" in report["stages"]
        assert "self_automation" in report["stages"]
        assert "next_steps" in report
        assert "checked_at" in report

    def test_each_stage_has_issues_and_components(self):
        boot = SelfAutomationBootstrap()
        report = boot.run()
        for stage_name, stage in report["stages"].items():
            assert "ready" in stage, f"{stage_name} missing 'ready'"
            assert "issues" in stage, f"{stage_name} missing 'issues'"
            assert "components" in stage, f"{stage_name} missing 'components'"

    def test_get_status_returns_summary(self):
        boot = SelfAutomationBootstrap()
        status = boot.get_status()
        assert "all_ready" in status
        assert "stages" in status
        for stage in status["stages"].values():
            assert "ready" in stage
            assert "issues" in stage

    def test_revenue_stage_detects_subscription_manager(self):
        boot = SelfAutomationBootstrap()
        report = boot.run()
        rev = report["stages"]["revenue"]
        assert rev["components"].get("subscription_manager") is True

    def test_automation_stage_detects_orchestrator(self):
        boot = SelfAutomationBootstrap()
        report = boot.run()
        auto = report["stages"]["self_automation"]
        assert auto["components"].get("orchestrator") is True

    def test_next_steps_is_nonempty(self):
        boot = SelfAutomationBootstrap()
        report = boot.run()
        assert len(report["next_steps"]) > 0
