"""
Tests for the SubscriptionManager — Murphy System.

Covers:
  - Tier definitions and pricing
  - Checkout session creation (mocked Stripe/PayPal/Coinbase)
  - Webhook handling for subscription lifecycle events
  - Subscription CRUD operations
  - Usage metering
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
import pytest
from unittest.mock import patch, MagicMock

from subscription_manager import (
    SubscriptionManager,
    SubscriptionTier,
    SubscriptionStatus,
    BillingInterval,
    PaymentProvider,
    PricingPlan,
    SubscriptionRecord,
    PRICING_PLANS,
    _TRIAL_DAYS,
)


# ---------------------------------------------------------------------------
# Pricing plan definitions
# ---------------------------------------------------------------------------

class TestPricingPlans:
    def test_all_tiers_defined(self):
        for tier in SubscriptionTier:
            if tier != SubscriptionTier.ENTERPRISE:
                assert tier in PRICING_PLANS

    def test_solo_pricing(self):
        plan = PRICING_PLANS[SubscriptionTier.SOLO]
        assert plan.monthly_price == 99.00
        assert plan.annual_price == 79.00
        assert plan.max_users == 1
        assert plan.max_automations == 3

    def test_business_pricing(self):
        plan = PRICING_PLANS[SubscriptionTier.BUSINESS]
        assert plan.monthly_price == 299.00
        assert plan.annual_price == 249.00
        assert plan.max_users == 10
        assert plan.max_automations == -1  # unlimited

    def test_professional_pricing(self):
        plan = PRICING_PLANS[SubscriptionTier.PROFESSIONAL]
        assert plan.monthly_price == 599.00
        assert plan.annual_price == 479.00
        assert plan.max_users == -1  # unlimited
        assert plan.max_automations == -1

    def test_enterprise_pricing_is_custom(self):
        plan = PRICING_PLANS[SubscriptionTier.ENTERPRISE]
        assert plan.monthly_price == 0.00  # custom pricing
        assert plan.max_users == -1
        assert plan.max_automations == -1

    def test_annual_cheaper_than_monthly(self):
        for tier in [SubscriptionTier.SOLO, SubscriptionTier.BUSINESS, SubscriptionTier.PROFESSIONAL]:
            plan = PRICING_PLANS[tier]
            assert plan.annual_price < plan.monthly_price, f"{tier} annual should be cheaper than monthly"

    def test_plans_have_features_list(self):
        for tier, plan in PRICING_PLANS.items():
            assert isinstance(plan.features, list)
            assert len(plan.features) > 0

    def test_plan_to_dict(self):
        plan = PRICING_PLANS[SubscriptionTier.SOLO]
        d = plan.to_dict()
        assert d["tier"] == "solo"
        assert d["monthly_price"] == 99.00
        assert "features" in d


# ---------------------------------------------------------------------------
# SubscriptionRecord
# ---------------------------------------------------------------------------

class TestSubscriptionRecord:
    def test_default_status_is_trial(self):
        sub = SubscriptionRecord(account_id="acc1")
        assert sub.status == SubscriptionStatus.TRIAL

    def test_is_active_for_trial_and_active(self):
        sub = SubscriptionRecord(account_id="acc1", status=SubscriptionStatus.TRIAL)
        assert sub.is_active() is True
        sub.status = SubscriptionStatus.ACTIVE
        assert sub.is_active() is True

    def test_not_active_for_canceled(self):
        sub = SubscriptionRecord(account_id="acc1", status=SubscriptionStatus.CANCELED)
        assert sub.is_active() is False

    def test_not_active_for_past_due(self):
        sub = SubscriptionRecord(account_id="acc1", status=SubscriptionStatus.PAST_DUE)
        assert sub.is_active() is False

    def test_to_dict(self):
        sub = SubscriptionRecord(account_id="acc1", tier=SubscriptionTier.BUSINESS)
        d = sub.to_dict()
        assert d["account_id"] == "acc1"
        assert d["tier"] == "business"
        assert d["status"] == "trial"


# ---------------------------------------------------------------------------
# Stripe checkout (stub path — no SDK required)
# ---------------------------------------------------------------------------

class TestStripeCheckout:
    def test_creates_stub_url_without_sdk(self):
        mgr = SubscriptionManager(stripe_api_key="sk_test_fake")
        url = mgr.create_stripe_checkout_session(
            account_id="acct1",
            tier=SubscriptionTier.SOLO,
            interval=BillingInterval.MONTHLY,
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )
        assert "acct1" in url
        assert "solo" in url

    def test_annual_billing_interval(self):
        mgr = SubscriptionManager(stripe_api_key="sk_test_fake")
        url = mgr.create_stripe_checkout_session(
            account_id="acct2",
            tier=SubscriptionTier.BUSINESS,
            interval=BillingInterval.ANNUAL,
            success_url="https://example.com/ok",
            cancel_url="https://example.com/no",
        )
        assert isinstance(url, str)
        assert len(url) > 0

    def test_enterprise_raises(self):
        mgr = SubscriptionManager()
        with pytest.raises(ValueError, match="Enterprise"):
            mgr.create_stripe_checkout_session(
                account_id="acct3",
                tier=SubscriptionTier.ENTERPRISE,
                interval=BillingInterval.MONTHLY,
                success_url="https://example.com/ok",
                cancel_url="https://example.com/no",
            )

    def test_audit_log_entry_created(self):
        mgr = SubscriptionManager(stripe_api_key="sk_test_fake")
        mgr.create_stripe_checkout_session(
            account_id="acct_audit",
            tier=SubscriptionTier.SOLO,
            interval=BillingInterval.MONTHLY,
            success_url="https://ok",
            cancel_url="https://no",
        )
        log = mgr.get_audit_log()
        assert any(e["action"] == "stripe_checkout_created" for e in log)


# ---------------------------------------------------------------------------
# Stripe webhook handling
# ---------------------------------------------------------------------------

class TestStripeWebhook:
    def _make_event(self, event_type: str, account_id: str = "acct_wh", sub_id: str = "sub_123") -> str:
        payload = {
            "type": event_type,
            "data": {
                "object": {
                    "metadata": {"murphy_account_id": account_id, "tier": "business"},
                    "subscription": sub_id,
                    "status": "active",
                }
            }
        }
        return json.dumps(payload)

    def test_checkout_completed_creates_subscription(self):
        mgr = SubscriptionManager()
        payload = self._make_event("checkout.session.completed")
        result = mgr.handle_stripe_webhook(payload, signature="", webhook_secret="")
        assert result["received"] is True
        sub = mgr.get_subscription("acct_wh")
        assert sub is not None
        assert sub.tier == SubscriptionTier.BUSINESS

    def test_subscription_updated_to_active(self):
        mgr = SubscriptionManager()
        # First create subscription
        mgr.handle_stripe_webhook(self._make_event("checkout.session.completed"), "", "")
        # Then update status
        payload = json.dumps({
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "metadata": {"murphy_account_id": "acct_wh"},
                    "status": "active",
                }
            }
        })
        result = mgr.handle_stripe_webhook(payload, "", "")
        assert result["received"] is True
        sub = mgr.get_subscription("acct_wh")
        assert sub.status == SubscriptionStatus.ACTIVE

    def test_subscription_deleted_cancels(self):
        mgr = SubscriptionManager()
        mgr.handle_stripe_webhook(self._make_event("checkout.session.completed"), "", "")
        payload = json.dumps({
            "type": "customer.subscription.deleted",
            "data": {"object": {"metadata": {"murphy_account_id": "acct_wh"}}}
        })
        mgr.handle_stripe_webhook(payload, "", "")
        sub = mgr.get_subscription("acct_wh")
        assert sub.status == SubscriptionStatus.CANCELED

    def test_payment_failed_sets_past_due(self):
        mgr = SubscriptionManager()
        mgr.handle_stripe_webhook(self._make_event("checkout.session.completed"), "", "")
        payload = json.dumps({
            "type": "invoice.payment_failed",
            "data": {"object": {"metadata": {"murphy_account_id": "acct_wh"}}}
        })
        mgr.handle_stripe_webhook(payload, "", "")
        sub = mgr.get_subscription("acct_wh")
        assert sub.status == SubscriptionStatus.PAST_DUE


# ---------------------------------------------------------------------------
# PayPal webhook handling
# ---------------------------------------------------------------------------

class TestPaypalWebhook:
    def test_subscription_activated(self):
        mgr = SubscriptionManager()
        # Pre-create subscription
        mgr._upsert_subscription("pp_acc", SubscriptionTier.SOLO, SubscriptionStatus.TRIAL, PaymentProvider.PAYPAL)
        payload = {
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {"custom_id": "pp_acc"}
        }
        result = mgr.handle_paypal_webhook(payload)
        assert result["received"] is True
        sub = mgr.get_subscription("pp_acc")
        assert sub.status == SubscriptionStatus.ACTIVE

    def test_subscription_cancelled(self):
        mgr = SubscriptionManager()
        mgr._upsert_subscription("pp_acc2", SubscriptionTier.BUSINESS, SubscriptionStatus.ACTIVE, PaymentProvider.PAYPAL)
        payload = {
            "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
            "resource": {"custom_id": "pp_acc2"}
        }
        mgr.handle_paypal_webhook(payload)
        assert mgr.get_subscription("pp_acc2").status == SubscriptionStatus.CANCELED

    def test_payment_failed_sets_past_due(self):
        mgr = SubscriptionManager()
        mgr._upsert_subscription("pp_acc3", SubscriptionTier.SOLO, SubscriptionStatus.ACTIVE, PaymentProvider.PAYPAL)
        payload = {
            "event_type": "BILLING.SUBSCRIPTION.PAYMENT.FAILED",
            "resource": {"custom_id": "pp_acc3"}
        }
        mgr.handle_paypal_webhook(payload)
        assert mgr.get_subscription("pp_acc3").status == SubscriptionStatus.PAST_DUE


# ---------------------------------------------------------------------------
# Coinbase Commerce webhook handling
# ---------------------------------------------------------------------------

class TestCoinbaseWebhook:
    def test_charge_confirmed_creates_subscription(self):
        mgr = SubscriptionManager()
        payload = {
            "type": "charge:confirmed",
            "data": {
                "code": "CHARGE123",
                "metadata": {"murphy_account_id": "cb_acc", "tier": "business"},
            }
        }
        result = mgr.handle_coinbase_webhook(payload)
        assert result["received"] is True
        assert result["event_type"] == "charge:confirmed"
        sub = mgr.get_subscription("cb_acc")
        assert sub is not None
        assert sub.tier == SubscriptionTier.BUSINESS
        assert sub.status == SubscriptionStatus.ACTIVE

    def test_charge_failed_sets_past_due(self):
        mgr = SubscriptionManager()
        mgr._upsert_subscription("cb_acc2", SubscriptionTier.SOLO, SubscriptionStatus.ACTIVE, PaymentProvider.CRYPTO)
        payload = {
            "type": "charge:failed",
            "data": {"metadata": {"murphy_account_id": "cb_acc2"}},
        }
        mgr.handle_coinbase_webhook(payload)
        assert mgr.get_subscription("cb_acc2").status == SubscriptionStatus.PAST_DUE

    def test_charge_resolved_reactivates(self):
        mgr = SubscriptionManager()
        mgr._upsert_subscription("cb_acc3", SubscriptionTier.PROFESSIONAL, SubscriptionStatus.PAST_DUE, PaymentProvider.CRYPTO)
        payload = {
            "type": "charge:resolved",
            "data": {"metadata": {"murphy_account_id": "cb_acc3"}},
        }
        mgr.handle_coinbase_webhook(payload)
        assert mgr.get_subscription("cb_acc3").status == SubscriptionStatus.ACTIVE

    def test_duplicate_event_skipped(self):
        mgr = SubscriptionManager()
        payload = {
            "id": "unique_event_1",
            "type": "charge:confirmed",
            "data": {
                "code": "CHARGE456",
                "metadata": {"murphy_account_id": "cb_dedup", "tier": "solo"},
            }
        }
        r1 = mgr.handle_coinbase_webhook(payload)
        r2 = mgr.handle_coinbase_webhook(payload)
        assert r1["received"] is True
        assert r2.get("duplicate") is True

    def test_unknown_event_type_accepted(self):
        mgr = SubscriptionManager()
        payload = {
            "type": "charge:pending",
            "data": {"metadata": {"murphy_account_id": "cb_pend"}},
        }
        result = mgr.handle_coinbase_webhook(payload)
        assert result["received"] is True
        assert result["event_type"] == "charge:pending"


# ---------------------------------------------------------------------------
# Subscription CRUD
# ---------------------------------------------------------------------------

class TestSubscriptionCrud:
    def test_get_subscription_none_for_unknown_account(self):
        mgr = SubscriptionManager()
        assert mgr.get_subscription("unknown") is None

    def test_cancel_subscription(self):
        mgr = SubscriptionManager()
        mgr._upsert_subscription("acct_cancel", SubscriptionTier.BUSINESS, SubscriptionStatus.ACTIVE, PaymentProvider.STRIPE)
        sub = mgr.cancel_subscription("acct_cancel")
        assert sub.cancel_at_period_end is True

    def test_cancel_nonexistent_raises(self):
        mgr = SubscriptionManager()
        with pytest.raises(ValueError):
            mgr.cancel_subscription("nobody")

    def test_upgrade_subscription(self):
        mgr = SubscriptionManager()
        mgr._upsert_subscription("acct_up", SubscriptionTier.SOLO, SubscriptionStatus.ACTIVE, PaymentProvider.STRIPE)
        sub = mgr.upgrade_subscription("acct_up", SubscriptionTier.BUSINESS)
        assert sub.tier == SubscriptionTier.BUSINESS

    def test_upgrade_nonexistent_raises(self):
        mgr = SubscriptionManager()
        with pytest.raises(ValueError):
            mgr.upgrade_subscription("nobody", SubscriptionTier.PROFESSIONAL)


# ---------------------------------------------------------------------------
# Usage metering
# ---------------------------------------------------------------------------

class TestUsageSummary:
    def test_returns_account_id(self):
        mgr = SubscriptionManager()
        mgr._upsert_subscription("meter_acc", SubscriptionTier.BUSINESS, SubscriptionStatus.ACTIVE, PaymentProvider.STRIPE)
        summary = mgr.get_usage_summary("meter_acc")
        assert summary["account_id"] == "meter_acc"

    def test_returns_correct_limits(self):
        mgr = SubscriptionManager()
        mgr._upsert_subscription("meter_acc2", SubscriptionTier.BUSINESS, SubscriptionStatus.ACTIVE, PaymentProvider.STRIPE)
        summary = mgr.get_usage_summary("meter_acc2")
        assert summary["max_users"] == 10
        assert summary["max_automations"] == -1  # unlimited

    def test_unknown_account_returns_zeros(self):
        mgr = SubscriptionManager()
        summary = mgr.get_usage_summary("unknown_acc")
        assert summary["max_users"] == 0
        assert summary["max_automations"] == 0

    def test_generated_at_is_set(self):
        mgr = SubscriptionManager()
        summary = mgr.get_usage_summary("any")
        assert "generated_at" in summary
        assert len(summary["generated_at"]) > 0


# ---------------------------------------------------------------------------
# start_trial
# ---------------------------------------------------------------------------

class TestStartTrial:
    def test_start_trial_returns_subscription(self):
        mgr = SubscriptionManager()
        sub = mgr.start_trial("trial_acc_1", SubscriptionTier.SOLO)
        assert sub is not None
        assert sub.account_id == "trial_acc_1"

    def test_start_trial_status_is_trial(self):
        mgr = SubscriptionManager()
        sub = mgr.start_trial("trial_acc_2", SubscriptionTier.SOLO)
        assert sub.status == SubscriptionStatus.TRIAL

    def test_start_trial_tier_is_correct(self):
        mgr = SubscriptionManager()
        sub = mgr.start_trial("trial_acc_3", SubscriptionTier.BUSINESS)
        assert sub.tier == SubscriptionTier.BUSINESS

    def test_start_trial_sets_trial_end(self):
        mgr = SubscriptionManager()
        sub = mgr.start_trial("trial_acc_4", SubscriptionTier.SOLO)
        assert sub.trial_end != ""

    def test_start_trial_professional_allowed(self):
        mgr = SubscriptionManager()
        sub = mgr.start_trial("trial_acc_5", SubscriptionTier.PROFESSIONAL)
        assert sub.tier == SubscriptionTier.PROFESSIONAL

    def test_start_trial_enterprise_raises(self):
        mgr = SubscriptionManager()
        with pytest.raises(ValueError, match="Enterprise"):
            mgr.start_trial("trial_acc_6", SubscriptionTier.ENTERPRISE)

    def test_start_trial_subscription_is_active(self):
        mgr = SubscriptionManager()
        sub = mgr.start_trial("trial_acc_7", SubscriptionTier.BUSINESS)
        assert sub.is_active() is True


# ---------------------------------------------------------------------------
# can_create_org feature flag
# ---------------------------------------------------------------------------

class TestCanCreateOrg:
    def _make_active(self, mgr, account_id, tier):
        mgr._upsert_subscription(account_id, tier, SubscriptionStatus.ACTIVE, PaymentProvider.STRIPE)

    def test_free_cannot_create_org(self):
        mgr = SubscriptionManager()
        self._make_active(mgr, "org_free", SubscriptionTier.FREE)
        result = mgr.check_feature_access("org_free", "can_create_org")
        assert result["allowed"] is False

    def test_solo_cannot_create_org(self):
        mgr = SubscriptionManager()
        self._make_active(mgr, "org_solo", SubscriptionTier.SOLO)
        result = mgr.check_feature_access("org_solo", "can_create_org")
        assert result["allowed"] is False

    def test_business_cannot_create_org(self):
        mgr = SubscriptionManager()
        self._make_active(mgr, "org_biz", SubscriptionTier.BUSINESS)
        result = mgr.check_feature_access("org_biz", "can_create_org")
        assert result["allowed"] is False

    def test_professional_can_create_org(self):
        mgr = SubscriptionManager()
        self._make_active(mgr, "org_pro", SubscriptionTier.PROFESSIONAL)
        result = mgr.check_feature_access("org_pro", "can_create_org")
        assert result["allowed"] is True

    def test_enterprise_can_create_org(self):
        mgr = SubscriptionManager()
        self._make_active(mgr, "org_ent", SubscriptionTier.ENTERPRISE)
        result = mgr.check_feature_access("org_ent", "can_create_org")
        assert result["allowed"] is True

    def test_no_subscription_cannot_create_org(self):
        mgr = SubscriptionManager()
        result = mgr.check_feature_access("org_unknown", "can_create_org")
        assert result["allowed"] is False
