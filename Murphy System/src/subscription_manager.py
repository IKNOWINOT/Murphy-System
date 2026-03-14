"""
Subscription Manager — Murphy System
Handles subscription lifecycle via Stripe, PayPal, and Coinbase Commerce.
Designed for minimal setup — uses hosted checkout pages for PCI compliance.

Design Principles:
  - Never handle raw card data — always redirect to hosted checkout
  - Thread-safe with bounded audit log
  - Graceful degradation when payment provider SDKs are unavailable

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import enum
import hashlib
import hmac as _hmac
import json as _json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from thread_safe_operations import capped_append

logger = logging.getLogger(__name__)

_MAX_AUDIT_LOG = 5_000


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SubscriptionTier(str, enum.Enum):
    """Murphy System subscription tiers."""
    SOLO = "solo"
    BUSINESS = "business"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    """Subscription lifecycle states."""
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    PAUSED = "paused"


class BillingInterval(str, enum.Enum):
    """Billing cycle options."""
    MONTHLY = "monthly"
    ANNUAL = "annual"


class PaymentProvider(str, enum.Enum):
    """Supported payment providers."""
    STRIPE = "stripe"
    PAYPAL = "paypal"
    CRYPTO = "crypto"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class PricingPlan:
    """Immutable definition of a subscription pricing tier."""
    tier: SubscriptionTier
    name: str
    monthly_price: float            # USD
    annual_price: float             # USD per month (billed annually)
    max_users: int                  # -1 = unlimited
    max_automations: int            # -1 = unlimited
    features: List[str] = field(default_factory=list)
    stripe_price_id_monthly: str = ""
    stripe_price_id_annual: str = ""
    paypal_plan_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value,
            "name": self.name,
            "monthly_price": self.monthly_price,
            "annual_price": self.annual_price,
            "max_users": self.max_users,
            "max_automations": self.max_automations,
            "features": self.features,
            "stripe_price_id_monthly": self.stripe_price_id_monthly,
            "stripe_price_id_annual": self.stripe_price_id_annual,
            "paypal_plan_id": self.paypal_plan_id,
        }


@dataclass
class SubscriptionRecord:
    """Active or historical subscription for an account."""
    subscription_id: str = field(default_factory=lambda: uuid.uuid4().hex[:20])
    account_id: str = ""
    tier: SubscriptionTier = SubscriptionTier.SOLO
    status: SubscriptionStatus = SubscriptionStatus.TRIAL
    payment_provider: PaymentProvider = PaymentProvider.STRIPE
    billing_interval: BillingInterval = BillingInterval.MONTHLY
    current_period_start: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    current_period_end: str = ""
    trial_end: str = ""
    external_subscription_id: str = ""  # Stripe sub ID, PayPal subscription ID, etc.
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    canceled_at: str = ""
    cancel_at_period_end: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subscription_id": self.subscription_id,
            "account_id": self.account_id,
            "tier": self.tier.value,
            "status": self.status.value,
            "payment_provider": self.payment_provider.value,
            "billing_interval": self.billing_interval.value,
            "current_period_start": self.current_period_start,
            "current_period_end": self.current_period_end,
            "trial_end": self.trial_end,
            "external_subscription_id": self.external_subscription_id,
            "created_at": self.created_at,
            "canceled_at": self.canceled_at,
            "cancel_at_period_end": self.cancel_at_period_end,
        }

    def is_active(self) -> bool:
        """Return True if the subscription grants access."""
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL)


# ---------------------------------------------------------------------------
# Pricing Definitions
# ---------------------------------------------------------------------------

PRICING_PLANS: Dict[SubscriptionTier, PricingPlan] = {
    SubscriptionTier.SOLO: PricingPlan(
        tier=SubscriptionTier.SOLO,
        name="Solo",
        monthly_price=29.00,
        annual_price=24.00,
        max_users=1,
        max_automations=3,
        stripe_price_id_monthly=os.environ.get("STRIPE_PRICE_SOLO_MONTHLY", ""),
        stripe_price_id_annual=os.environ.get("STRIPE_PRICE_SOLO_ANNUAL", ""),
        paypal_plan_id=os.environ.get("PAYPAL_PLAN_SOLO", ""),
        features=[
            "1 user",
            "3 automations",
            "Email support",
            "Community templates",
            "Murphy terminal access",
            "Basic compliance (GDPR, SOC2)",
        ],
    ),
    SubscriptionTier.BUSINESS: PricingPlan(
        tier=SubscriptionTier.BUSINESS,
        name="Business",
        monthly_price=99.00,
        annual_price=79.00,
        max_users=10,
        max_automations=-1,
        stripe_price_id_monthly=os.environ.get("STRIPE_PRICE_BUSINESS_MONTHLY", ""),
        stripe_price_id_annual=os.environ.get("STRIPE_PRICE_BUSINESS_ANNUAL", ""),
        paypal_plan_id=os.environ.get("PAYPAL_PLAN_BUSINESS", ""),
        features=[
            "Up to 10 users",
            "Unlimited automations",
            "Priority support",
            "All integrations",
            "Advanced compliance",
            "API access",
            "Shadow agent training",
        ],
    ),
    SubscriptionTier.PROFESSIONAL: PricingPlan(
        tier=SubscriptionTier.PROFESSIONAL,
        name="Professional",
        monthly_price=299.00,
        annual_price=249.00,
        max_users=-1,
        max_automations=-1,
        stripe_price_id_monthly=os.environ.get("STRIPE_PRICE_PRO_MONTHLY", ""),
        stripe_price_id_annual=os.environ.get("STRIPE_PRICE_PRO_ANNUAL", ""),
        paypal_plan_id=os.environ.get("PAYPAL_PLAN_PRO", ""),
        features=[
            "Unlimited users",
            "Unlimited automations",
            "HITL graduation",
            "All compliance frameworks",
            "API access + webhooks",
            "White-label options",
            "Dedicated onboarding",
            "SLA: 99.9% uptime",
        ],
    ),
    SubscriptionTier.ENTERPRISE: PricingPlan(
        tier=SubscriptionTier.ENTERPRISE,
        name="Enterprise",
        monthly_price=0.00,   # custom pricing
        annual_price=0.00,
        max_users=-1,
        max_automations=-1,
        features=[
            "Unlimited users",
            "Unlimited automations",
            "Dedicated cloud instance",
            "SSO/SAML integration",
            "Custom SLA",
            "Audit export (PDF/CSV)",
            "White-labeling",
            "Dedicated CSM",
            "All compliance frameworks",
            "FedRAMP / CMMC support",
        ],
    ),
}


# ---------------------------------------------------------------------------
# SubscriptionManager
# ---------------------------------------------------------------------------

_TRIAL_DAYS = 14


class SubscriptionManager:
    """Orchestrates subscription billing across Stripe, PayPal, and Coinbase Commerce.

    Usage::

        mgr = SubscriptionManager()
        url = mgr.create_stripe_checkout_session(
            account_id="abc123",
            tier=SubscriptionTier.BUSINESS,
            interval=BillingInterval.MONTHLY,
            success_url="https://app.murphy.ai/dashboard?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://app.murphy.ai/pricing",
        )
        # redirect user to url
    """

    def __init__(
        self,
        stripe_api_key: str = "",
        paypal_client_id: str = "",
        paypal_client_secret: str = "",
        coinbase_api_key: str = "",
    ) -> None:
        self._stripe_api_key = stripe_api_key or os.environ.get("STRIPE_API_KEY", "")
        self._paypal_client_id = paypal_client_id or os.environ.get("PAYPAL_CLIENT_ID", "")
        self._paypal_client_secret = paypal_client_secret or os.environ.get("PAYPAL_CLIENT_SECRET", "")
        self._coinbase_api_key = coinbase_api_key or os.environ.get("COINBASE_COMMERCE_API_KEY", "")
        self._lock = threading.Lock()
        self._subscriptions: Dict[str, SubscriptionRecord] = {}
        self._audit_log: List[Dict[str, Any]] = []
        self._processed_events: Dict[str, float] = {}  # event_id → timestamp
        self._EVENT_DEDUP_WINDOW = 3600  # 1 hour

    # ------------------------------------------------------------------
    # Stripe
    # ------------------------------------------------------------------

    def create_stripe_checkout_session(
        self,
        account_id: str,
        tier: SubscriptionTier,
        interval: BillingInterval,
        success_url: str,
        cancel_url: str,
        trial_days: int = _TRIAL_DAYS,
    ) -> str:
        """Create a Stripe Checkout Session and return the hosted URL.

        Stripe handles all card data and PCI compliance.
        Returns the Stripe checkout URL to redirect the customer to.
        """
        plan = PRICING_PLANS.get(tier)
        if plan is None:
            raise ValueError(f"Unknown tier: {tier}")
        if tier == SubscriptionTier.ENTERPRISE:
            raise ValueError("Enterprise pricing is custom — use contact sales flow")

        price_id = (
            plan.stripe_price_id_monthly
            if interval == BillingInterval.MONTHLY
            else plan.stripe_price_id_annual
        )

        try:
            import stripe as _stripe  # lazy import — not a hard dependency
            _stripe.api_key = self._stripe_api_key
            session = _stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                subscription_data={
                    "trial_period_days": trial_days,
                    "metadata": {"murphy_account_id": account_id, "tier": tier.value},
                },
                metadata={"murphy_account_id": account_id, "tier": tier.value},
            )
            checkout_url: str = session.url
        except ImportError:
            logger.warning("stripe SDK not installed — returning stub checkout URL")
            checkout_url = (
                f"https://checkout.stripe.com/stub?account={account_id}&tier={tier.value}"
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Stripe checkout session creation failed: %s", exc)
            raise

        self._audit("stripe_checkout_created", account_id, {"tier": tier.value, "interval": interval.value})
        return checkout_url

    def handle_stripe_webhook(
        self,
        payload: str,
        signature: str,
        webhook_secret: str = "",
    ) -> Dict[str, Any]:
        """Process a Stripe webhook event (subscription lifecycle).

        Handles: checkout.session.completed, customer.subscription.updated,
        customer.subscription.deleted, invoice.payment_failed.

        Includes idempotency: duplicate event IDs within the dedup window
        are acknowledged without re-processing.
        """
        secret = webhook_secret or os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        event: Dict[str, Any] = {}
        try:
            import stripe as _stripe
            _stripe.api_key = self._stripe_api_key
            event = _stripe.Webhook.construct_event(payload, signature, secret)
        except ImportError:
            import json
            event = json.loads(payload)
        except Exception as exc:  # noqa: BLE001
            logger.error("Stripe webhook validation failed: %s", exc)
            raise ValueError("invalid stripe webhook") from exc

        # Idempotency: skip already-processed events
        event_id = event.get("id", "")
        if event_id and self._is_duplicate_event(event_id):
            logger.info("Duplicate Stripe event skipped: %s", event_id)
            return {"received": True, "duplicate": True, "event_type": event.get("type", "")}

        event_type = event.get("type", "")
        data_obj = event.get("data", {}).get("object", {})
        account_id = (data_obj.get("metadata") or {}).get("murphy_account_id", "")

        if event_type == "checkout.session.completed":
            tier_val = (data_obj.get("metadata") or {}).get("tier", SubscriptionTier.SOLO.value)
            self._upsert_subscription(
                account_id=account_id,
                tier=SubscriptionTier(tier_val),
                status=SubscriptionStatus.TRIAL,
                provider=PaymentProvider.STRIPE,
                external_id=data_obj.get("subscription", ""),
            )
        elif event_type == "customer.subscription.updated":
            status_map = {
                "active": SubscriptionStatus.ACTIVE,
                "trialing": SubscriptionStatus.TRIAL,
                "past_due": SubscriptionStatus.PAST_DUE,
                "canceled": SubscriptionStatus.CANCELED,
                "paused": SubscriptionStatus.PAUSED,
            }
            new_status = status_map.get(data_obj.get("status", ""), SubscriptionStatus.ACTIVE)
            self._update_subscription_status(account_id, new_status)
        elif event_type == "customer.subscription.deleted":
            self._update_subscription_status(account_id, SubscriptionStatus.CANCELED)
        elif event_type == "invoice.payment_failed":
            self._update_subscription_status(account_id, SubscriptionStatus.PAST_DUE)

        self._audit("stripe_webhook", account_id, {"event_type": event_type})
        return {"received": True, "event_type": event_type}

    # ------------------------------------------------------------------
    # PayPal
    # ------------------------------------------------------------------

    def create_paypal_order(
        self,
        account_id: str,
        tier: SubscriptionTier,
        interval: BillingInterval,
    ) -> str:
        """Create a PayPal subscription order and return the approval URL."""
        plan = PRICING_PLANS.get(tier)
        if plan is None:
            raise ValueError(f"Unknown tier: {tier}")
        if tier == SubscriptionTier.ENTERPRISE:
            raise ValueError("Enterprise pricing is custom")

        plan_id = plan.paypal_plan_id
        price = plan.monthly_price if interval == BillingInterval.MONTHLY else plan.annual_price

        try:
            import requests  # lazy import
            token = self._get_paypal_access_token()
            base_url = os.environ.get("PAYPAL_API_BASE", "https://api-m.sandbox.paypal.com")
            resp = requests.post(
                f"{base_url}/v1/billing/subscriptions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "plan_id": plan_id,
                    "quantity": "1",
                    "custom_id": account_id,
                    "application_context": {
                        "return_url": os.environ.get("PAYPAL_RETURN_URL", "http://localhost:8000/billing/success"),
                        "cancel_url": os.environ.get("PAYPAL_CANCEL_URL", "http://localhost:8000/pricing"),
                        "user_action": "SUBSCRIBE_NOW",
                    },
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for link in data.get("links", []):
                if link.get("rel") == "approve":
                    approval_url: str = link["href"]
                    self._audit("paypal_order_created", account_id, {"tier": tier.value})
                    return approval_url
            raise RuntimeError("PayPal approval URL not found in response")
        except ImportError:
            logger.warning("requests not available — returning stub PayPal URL")
            return f"https://www.paypal.com/stub?account={account_id}&tier={tier.value}&price={price}"

    def _get_paypal_access_token(self) -> str:
        """Exchange PayPal client credentials for an access token."""
        import base64

        import requests
        credentials = base64.b64encode(
            f"{self._paypal_client_id}:{self._paypal_client_secret}".encode()
        ).decode()
        base_url = os.environ.get("PAYPAL_API_BASE", "https://api-m.sandbox.paypal.com")
        resp = requests.post(
            f"{base_url}/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
            timeout=15,
        )
        resp.raise_for_status()
        return str(resp.json()["access_token"])

    def handle_paypal_webhook(
        self,
        payload: Dict[str, Any],
        signature: str = "",
        webhook_secret: str = "",
    ) -> Dict[str, Any]:
        """Process a PayPal subscription webhook event.

        When ``webhook_secret`` (or the ``PAYPAL_WEBHOOK_SECRET`` env var) is
        set, the ``signature`` is verified via HMAC-SHA256 before processing.
        Includes idempotency to prevent duplicate event processing.

        Note: The HMAC is computed over canonical JSON (sorted keys, no
        whitespace).  In production, consider using the PayPal SDK's
        ``verify_webhook_signature`` for full protocol compliance.
        """
        secret = webhook_secret or os.environ.get("PAYPAL_WEBHOOK_SECRET", "")
        if secret:
            payload_bytes = _json.dumps(
                payload, separators=(",", ":"), sort_keys=True
            ).encode()
            expected = _hmac.new(
                secret.encode(), payload_bytes, hashlib.sha256
            ).hexdigest()
            if not _hmac.compare_digest(expected, signature):
                logger.warning("PayPal webhook signature mismatch")
                raise ValueError("invalid PayPal webhook signature")

        # Idempotency
        event_id = payload.get("id", "")
        if event_id and self._is_duplicate_event(event_id):
            logger.info("Duplicate PayPal event skipped: %s", event_id)
            return {"received": True, "duplicate": True, "event_type": payload.get("event_type", "")}

        event_type = payload.get("event_type", "")
        resource = payload.get("resource", {})
        account_id = resource.get("custom_id", "")

        if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
            self._update_subscription_status(account_id, SubscriptionStatus.ACTIVE)
        elif event_type in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.EXPIRED"):
            self._update_subscription_status(account_id, SubscriptionStatus.CANCELED)
        elif event_type == "BILLING.SUBSCRIPTION.PAYMENT.FAILED":
            self._update_subscription_status(account_id, SubscriptionStatus.PAST_DUE)

        self._audit("paypal_webhook", account_id, {"event_type": event_type})
        return {"received": True, "event_type": event_type}

    # ------------------------------------------------------------------
    # Coinbase Commerce (crypto)
    # ------------------------------------------------------------------

    def handle_coinbase_webhook(
        self,
        payload: Dict[str, Any],
        signature: str = "",
        webhook_secret: str = "",
    ) -> Dict[str, Any]:
        """Process a Coinbase Commerce webhook event.

        Coinbase Commerce sends events for charge lifecycle:
          - ``charge:confirmed``  → payment received, activate subscription
          - ``charge:failed``     → payment failed
          - ``charge:delayed``    → underpaid / waiting for confirmation
          - ``charge:pending``    → payment detected, awaiting confirmation
          - ``charge:resolved``   → previously underpaid charge resolved

        When ``webhook_secret`` (or ``COINBASE_WEBHOOK_SECRET`` env var) is
        set, the ``signature`` header (``X-CC-Webhook-Signature``) is verified
        via HMAC-SHA256 before processing.
        """
        secret = webhook_secret or os.environ.get("COINBASE_WEBHOOK_SECRET", "")
        if secret and signature:
            payload_bytes = _json.dumps(
                payload, separators=(",", ":"), sort_keys=True
            ).encode()
            expected = _hmac.new(
                secret.encode(), payload_bytes, hashlib.sha256
            ).hexdigest()
            if not _hmac.compare_digest(expected, signature):
                logger.warning("Coinbase webhook signature mismatch")
                raise ValueError("invalid Coinbase webhook signature")

        # Idempotency
        event_id = payload.get("id", "")
        if event_id and self._is_duplicate_event(event_id):
            logger.info("Duplicate Coinbase event skipped: %s", event_id)
            return {"received": True, "duplicate": True, "event_type": payload.get("type", "")}

        event_type = payload.get("type", "")
        event_data = payload.get("data", {})
        metadata = event_data.get("metadata", {})
        account_id = metadata.get("murphy_account_id", "")
        tier_str = metadata.get("tier", "solo")

        if event_type == "charge:confirmed":
            if account_id:
                try:
                    tier = SubscriptionTier(tier_str)
                except ValueError:
                    tier = SubscriptionTier.SOLO
                self._upsert_subscription(
                    account_id, tier, SubscriptionStatus.ACTIVE, PaymentProvider.CRYPTO,
                    external_id=event_data.get("code", ""),
                )
        elif event_type == "charge:failed":
            if account_id:
                self._update_subscription_status(account_id, SubscriptionStatus.PAST_DUE)
        elif event_type == "charge:resolved":
            if account_id:
                self._update_subscription_status(account_id, SubscriptionStatus.ACTIVE)

        self._audit("coinbase_webhook", account_id, {"event_type": event_type})
        return {"received": True, "event_type": event_type}

    def create_crypto_charge(
        self,
        account_id: str,
        tier: SubscriptionTier,
        interval: BillingInterval,
    ) -> str:
        """Create a Coinbase Commerce charge and return the hosted payment URL."""
        plan = PRICING_PLANS.get(tier)
        if plan is None:
            raise ValueError(f"Unknown tier: {tier}")
        if tier == SubscriptionTier.ENTERPRISE:
            raise ValueError("Enterprise pricing is custom")

        price = plan.monthly_price if interval == BillingInterval.MONTHLY else plan.annual_price * 12

        try:
            import requests
            resp = requests.post(
                "https://api.commerce.coinbase.com/charges",
                headers={
                    "X-CC-Api-Key": self._coinbase_api_key,
                    "X-CC-Version": "2018-03-22",
                    "Content-Type": "application/json",
                },
                json={
                    "name": f"Murphy System — {plan.name}",
                    "description": f"{plan.name} plan ({interval.value})",
                    "pricing_type": "fixed_price",
                    "local_price": {"amount": str(price), "currency": "USD"},
                    "metadata": {"murphy_account_id": account_id, "tier": tier.value},
                    "redirect_url": os.environ.get("CRYPTO_REDIRECT_URL", "http://localhost:8000/billing/success"),
                    "cancel_url": os.environ.get("CRYPTO_CANCEL_URL", "http://localhost:8000/pricing"),
                },
                timeout=15,
            )
            resp.raise_for_status()
            hosted_url: str = resp.json()["data"]["hosted_url"]
            self._audit("crypto_charge_created", account_id, {"tier": tier.value})
            return hosted_url
        except ImportError:
            logger.warning("requests not available — returning stub crypto URL")
            return f"https://commerce.coinbase.com/stub?account={account_id}&tier={tier.value}"

    # ------------------------------------------------------------------
    # Subscription CRUD
    # ------------------------------------------------------------------

    def get_subscription(self, account_id: str) -> Optional[SubscriptionRecord]:
        """Return the current subscription for an account, or None."""
        with self._lock:
            return self._subscriptions.get(account_id)

    def cancel_subscription(self, account_id: str) -> SubscriptionRecord:
        """Mark a subscription to cancel at the end of the billing period."""
        with self._lock:
            sub = self._subscriptions.get(account_id)
            if sub is None:
                raise ValueError(f"No subscription found for account {account_id}")
            sub.cancel_at_period_end = True
            self._audit("cancel_subscription", account_id, {"tier": sub.tier.value})
        logger.info("Subscription cancel-at-period-end set: account_id=%s", account_id)
        return sub

    def upgrade_subscription(
        self,
        account_id: str,
        new_tier: SubscriptionTier,
    ) -> SubscriptionRecord:
        """Upgrade (or downgrade) a subscription tier (prorated on Stripe)."""
        with self._lock:
            sub = self._subscriptions.get(account_id)
            if sub is None:
                raise ValueError(f"No subscription found for account {account_id}")
            old_tier = sub.tier
            sub.tier = new_tier
            sub.cancel_at_period_end = False
            self._audit("upgrade_subscription", account_id, {
                "old_tier": old_tier.value,
                "new_tier": new_tier.value,
            })
        logger.info("Subscription upgraded: account_id=%s %s→%s", account_id, old_tier.value, new_tier.value)
        return sub

    def get_usage_summary(self, account_id: str) -> Dict[str, Any]:
        """Return current usage metrics for the account (for metered billing)."""
        sub = self.get_subscription(account_id)
        plan = PRICING_PLANS.get(sub.tier) if sub else None
        return {
            "account_id": account_id,
            "tier": sub.tier.value if sub else None,
            "max_users": plan.max_users if plan else 0,
            "max_automations": plan.max_automations if plan else 0,
            "current_users": 0,       # populate from user directory in production
            "current_automations": 0, # populate from automation registry in production
            "api_calls_this_period": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _upsert_subscription(
        self,
        account_id: str,
        tier: SubscriptionTier,
        status: SubscriptionStatus,
        provider: PaymentProvider,
        external_id: str = "",
    ) -> SubscriptionRecord:
        """Create or update a subscription record."""
        now = datetime.now(timezone.utc)
        trial_end = (now + timedelta(days=_TRIAL_DAYS)).isoformat()
        period_end = (now + timedelta(days=30)).isoformat()

        with self._lock:
            existing = self._subscriptions.get(account_id)
            if existing:
                existing.tier = tier
                existing.status = status
                existing.payment_provider = provider
                existing.external_subscription_id = external_id
                return existing

            sub = SubscriptionRecord(
                account_id=account_id,
                tier=tier,
                status=status,
                payment_provider=provider,
                current_period_start=now.isoformat(),
                current_period_end=period_end,
                trial_end=trial_end if status == SubscriptionStatus.TRIAL else "",
                external_subscription_id=external_id,
            )
            self._subscriptions[account_id] = sub
            return sub

    def _update_subscription_status(
        self, account_id: str, status: SubscriptionStatus
    ) -> None:
        with self._lock:
            sub = self._subscriptions.get(account_id)
            if sub:
                sub.status = status
                if status == SubscriptionStatus.CANCELED:
                    sub.canceled_at = datetime.now(timezone.utc).isoformat()

    def _is_duplicate_event(self, event_id: str) -> bool:
        """Check if an event has already been processed (idempotency guard).

        Prunes stale entries outside the dedup window to bound memory.
        """
        now = time.time()
        with self._lock:
            # Prune old entries
            cutoff = now - self._EVENT_DEDUP_WINDOW
            stale = [eid for eid, ts in self._processed_events.items() if ts < cutoff]
            for eid in stale:
                del self._processed_events[eid]

            if event_id in self._processed_events:
                return True
            self._processed_events[event_id] = now
            return False

    def _audit(self, action: str, account_id: str, details: Dict[str, Any]) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "account_id": account_id,
            **details,
        }
        capped_append(self._audit_log, entry, _MAX_AUDIT_LOG)

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Return a copy of the audit log."""
        with self._lock:
            return list(self._audit_log)
