"""
Billing API — PayPal + Crypto subscription endpoints for Murphy System.

Exposes the SubscriptionManager as FastAPI routes so the frontend can
create checkout sessions, receive webhooks, query subscription state,
and view usage.

Payment providers (Stripe deliberately excluded — too painful to set up):
  • **PayPal** — primary fiat provider
  • **Coinbase Commerce** — crypto (BTC, ETH, USDC, etc.)

Multi-currency & regional pricing:
  • Any request can include ``currency`` (ISO 4217) to get local pricing.
  • Requests from Japan (``locale=ja`` or ``currency=JPY``) receive an
    automatic **10 % discount**.

Endpoints:
  GET  /api/billing/plans           — list available pricing plans (with optional ?currency=&locale=)
  GET  /api/billing/currencies      — list supported currencies
  POST /api/billing/checkout        — create PayPal checkout (redirect URL)
  POST /api/billing/checkout/crypto — create Coinbase Commerce charge
  POST /api/billing/webhooks/paypal   — PayPal webhook receiver
  POST /api/billing/webhooks/coinbase — Coinbase Commerce webhook receiver
  GET  /api/billing/subscription/{account_id} — get subscription state
  POST /api/billing/subscription/{account_id}/cancel  — cancel
  POST /api/billing/subscription/{account_id}/upgrade — upgrade/downgrade
  GET  /api/billing/usage/{account_id}                — usage summary

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import re
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.billing.currency import CurrencyConverter, get_converter
from src.subscription_manager import (
    PRICING_PLANS,
    BillingInterval,
    PaymentProvider,
    SubscriptionManager,
    SubscriptionTier,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Security constants
# ---------------------------------------------------------------------------

# account_id must be alphanumeric + hyphens/underscores, 1–200 chars (CWE-20)
_ACCOUNT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,200}$")

# ISO 4217 currency codes are always 3 uppercase letters
_CURRENCY_CODE_RE = re.compile(r"^[A-Za-z]{3}$")

# Locale hint — relaxed to allow 'ja', 'en-US', 'ja_JP', etc.
_LOCALE_RE = re.compile(r"^[a-zA-Z]{0,10}([_\-][a-zA-Z]{0,10})?$")

# Maximum webhook body size — 256 KB (generous for payment webhooks)
_MAX_WEBHOOK_BODY_BYTES = 256 * 1024


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

def _validate_account_id(account_id: str) -> str:
    """Validate and return account_id, or raise HTTPException (CWE-20)."""
    if not account_id or not _ACCOUNT_ID_RE.match(account_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid account_id format",
        )
    return account_id


def _validate_currency_code(code: str) -> str:
    """Validate ISO 4217 currency code format (CWE-20)."""
    if code and not _CURRENCY_CODE_RE.match(code):
        raise HTTPException(status_code=400, detail="Invalid currency code format")
    return code.upper() if code else "USD"


def _validate_locale(locale: str) -> str:
    """Validate locale hint format (CWE-20)."""
    if locale and not _LOCALE_RE.match(locale):
        raise HTTPException(status_code=400, detail="Invalid locale format")
    return locale


def _safe_billing_error(exc: Exception, status_code: int = 500) -> JSONResponse:
    """Return a sanitized error response — never leak provider internals.

    In production/staging, the client only sees a generic message.
    In development/test, the original error string is included.
    """
    env = os.environ.get("MURPHY_ENV", "development").lower()
    if env in ("production", "staging"):
        body = {"error": "A billing error occurred."}
    else:
        body = {"error": str(exc)}
    return JSONResponse(body, status_code=status_code)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    """Request body for creating a checkout session."""
    account_id: str = Field(..., min_length=1, max_length=200)
    tier: str = Field(..., pattern="^(solo|business|professional)$")
    interval: str = Field("monthly", pattern="^(monthly|annual)$")
    currency: str = Field("USD", max_length=3, description="ISO 4217 currency code")
    locale: str = Field("", max_length=10, description="Locale hint (e.g. 'ja', 'en-US')")


class UpgradeRequest(BaseModel):
    """Request body for upgrading a subscription."""
    new_tier: str = Field(..., pattern="^(solo|business|professional|enterprise)$")


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_billing_router(
    subscription_manager: Optional[SubscriptionManager] = None,
    currency_converter: Optional[CurrencyConverter] = None,
) -> APIRouter:
    """Create and return the billing APIRouter.

    If *subscription_manager* is not supplied a default instance is created
    using environment variables for PayPal / Coinbase credentials.
    """
    mgr = subscription_manager or SubscriptionManager(
        paypal_client_id=os.environ.get("PAYPAL_CLIENT_ID", ""),
        paypal_client_secret=os.environ.get("PAYPAL_CLIENT_SECRET", ""),
        coinbase_api_key=os.environ.get("COINBASE_COMMERCE_API_KEY", ""),
    )
    cc = currency_converter or get_converter()

    # Lazy-import the orchestrator inside the factory so that billing routes
    # can be mounted without requiring all infra dependencies to be present.
    def _get_orchestrator() -> Any:
        try:
            from src.customer_infra_orchestrator import CustomerInfraOrchestrator
        except ImportError:
            try:
                from customer_infra_orchestrator import CustomerInfraOrchestrator  # type: ignore[no-reattr]
            except ImportError:
                return None
        return CustomerInfraOrchestrator(_subscription_manager=mgr)

    _orchestrator_cache: Dict[str, Any] = {}

    def _orchestrator() -> Any:
        if "instance" not in _orchestrator_cache:
            _orchestrator_cache["instance"] = _get_orchestrator()
        return _orchestrator_cache["instance"]

    def _trigger_provision(account_id: str, tier: str) -> None:
        """Fire provisioning in a background thread so the webhook returns fast."""
        orch = _orchestrator()
        if orch is None:
            logger.warning(
                "CustomerInfraOrchestrator unavailable — skipping provisioning "
                "for account=%s tier=%s",
                account_id, tier,
            )
            return
        t = threading.Thread(
            target=orch.provision_customer,
            args=(account_id, tier),
            daemon=True,
            name=f"provision-{account_id[:20]}",
        )
        t.start()
        logger.info(
            "Provisioning triggered in background: account=%s tier=%s", account_id, tier
        )

    def _trigger_deprovision(account_id: str) -> None:
        """Fire deprovisioning in a background thread."""
        orch = _orchestrator()
        if orch is None:
            return
        t = threading.Thread(
            target=orch.deprovision_customer,
            args=(account_id,),
            daemon=True,
            name=f"deprovision-{account_id[:20]}",
        )
        t.start()
        logger.info("Deprovisioning triggered in background: account=%s", account_id)

    router = APIRouter(prefix="/api/billing", tags=["billing"])

    # ── Currencies ───────────────────────────────────────────────────

    @router.get("/currencies")
    async def list_currencies() -> JSONResponse:
        """Return all supported currency codes."""
        return JSONResponse({
            "currencies": cc.list_currencies(),
            "default": "USD",
            "regional_discounts": [
                {"locale": "ja", "currency": "JPY", "discount_percent": 10,
                 "reason": "Japan regional discount"},
            ],
        })

    # ── Plans (with optional local currency + Japan discount) ────────

    @router.get("/plans")
    async def list_plans(
        currency: str = Query("USD", max_length=3, description="ISO 4217 currency code"),
        locale: str = Query("", max_length=10, description="Locale hint (e.g. 'ja')"),
    ) -> JSONResponse:
        """Return all pricing plans, optionally localised to *currency*.

        When ``currency=JPY`` or ``locale=ja`` the 10 % Japan discount is
        applied automatically.
        """
        currency = _validate_currency_code(currency)
        locale = _validate_locale(locale)
        plans: List[Dict[str, Any]] = []
        for plan in PRICING_PLANS.values():
            d = plan.to_dict()
            monthly_loc = cc.localize(plan.monthly_price, currency, locale)
            annual_loc = cc.localize(plan.annual_price, currency, locale)
            d["local_monthly"] = monthly_loc
            d["local_annual"] = annual_loc
            plans.append(d)
        return JSONResponse({"plans": plans, "currency": currency.upper(), "locale": locale})

    # ── PayPal Checkout ──────────────────────────────────────────────

    @router.post("/checkout")
    async def create_checkout(body: CheckoutRequest) -> JSONResponse:
        """Create a PayPal subscription checkout and return the approval URL.

        Prices are in USD on the PayPal side (PayPal handles local
        currency display).  The response includes the localised price
        for front-end display.
        """
        _validate_account_id(body.account_id)
        _validate_currency_code(body.currency)
        _validate_locale(body.locale)

        try:
            tier = SubscriptionTier(body.tier)
            interval = BillingInterval(body.interval)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            approval_url = mgr.create_paypal_order(
                account_id=body.account_id,
                tier=tier,
                interval=interval,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("PayPal checkout failed: %s", exc)
            raise HTTPException(status_code=502, detail="Payment provider unavailable") from exc

        # Compute localised display price
        plan = PRICING_PLANS.get(tier)
        base_usd = plan.monthly_price if interval == BillingInterval.MONTHLY else plan.annual_price
        local_price = cc.localize(base_usd, body.currency, body.locale)

        return JSONResponse({
            "provider": "paypal",
            "approval_url": approval_url,
            "tier": tier.value,
            "interval": interval.value,
            "price": local_price,
        })

    # ── Crypto Checkout ──────────────────────────────────────────────

    @router.post("/checkout/crypto")
    async def create_crypto_checkout(body: CheckoutRequest) -> JSONResponse:
        """Create a Coinbase Commerce charge and return the hosted URL.

        Coinbase Commerce natively accepts BTC, ETH, USDC, DAI, and more.
        The charge is denominated in USD; crypto conversion is automatic.
        Response includes the localised display price.
        """
        _validate_account_id(body.account_id)
        _validate_currency_code(body.currency)
        _validate_locale(body.locale)

        try:
            tier = SubscriptionTier(body.tier)
            interval = BillingInterval(body.interval)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            hosted_url = mgr.create_crypto_charge(
                account_id=body.account_id,
                tier=tier,
                interval=interval,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Crypto checkout failed: %s", exc)
            raise HTTPException(status_code=502, detail="Payment provider unavailable") from exc

        plan = PRICING_PLANS.get(tier)
        base_usd = plan.monthly_price if interval == BillingInterval.MONTHLY else plan.annual_price
        local_price = cc.localize(base_usd, body.currency, body.locale)

        return JSONResponse({
            "provider": "crypto",
            "hosted_url": hosted_url,
            "tier": tier.value,
            "interval": interval.value,
            "price": local_price,
        })

    # ── PayPal Webhook ───────────────────────────────────────────────

    @router.post("/webhooks/paypal")
    async def paypal_webhook(request: Request) -> JSONResponse:
        """Receive and process PayPal subscription lifecycle webhooks."""
        # Body size guard (CWE-400)
        raw_body = await request.body()
        if len(raw_body) > _MAX_WEBHOOK_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Payload too large")

        try:
            payload: Dict[str, Any] = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON") from exc

        signature = request.headers.get("paypal-transmission-sig", "")

        try:
            result = mgr.handle_paypal_webhook(
                payload=payload,
                signature=signature,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Trigger infra provisioning / deprovisioning in background
        event_type = payload.get("event_type", "")
        account_id = payload.get("resource", {}).get("custom_id", "")
        if account_id:
            if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
                sub = mgr.get_subscription(account_id)
                tier = sub.tier.value if sub else "solo"
                _trigger_provision(account_id, tier)
            elif event_type in (
                "BILLING.SUBSCRIPTION.CANCELLED",
                "BILLING.SUBSCRIPTION.EXPIRED",
                "BILLING.SUBSCRIPTION.SUSPENDED",
            ):
                _trigger_deprovision(account_id)

        return JSONResponse(result)

    # ── Coinbase Commerce Webhook ────────────────────────────────────

    @router.post("/webhooks/coinbase")
    async def coinbase_webhook(request: Request) -> JSONResponse:
        """Receive and process Coinbase Commerce charge lifecycle webhooks.

        Coinbase Commerce sends ``charge:confirmed``, ``charge:failed``,
        ``charge:delayed``, ``charge:pending``, and ``charge:resolved``
        events.  The ``X-CC-Webhook-Signature`` header is verified when
        ``COINBASE_WEBHOOK_SECRET`` is configured.
        """
        raw_body = await request.body()
        # Body size guard (CWE-400)
        if len(raw_body) > _MAX_WEBHOOK_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Payload too large")

        try:
            payload: Dict[str, Any] = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON") from exc

        signature = request.headers.get("x-cc-webhook-signature", "")

        try:
            result = mgr.handle_coinbase_webhook(
                payload=payload,
                signature=signature,
                raw_body=raw_body,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Trigger infra provisioning on confirmed payment
        event_type = payload.get("type", "")
        metadata = payload.get("data", {}).get("metadata", {})
        account_id = metadata.get("murphy_account_id", "")
        if account_id and event_type == "charge:confirmed":
            sub = mgr.get_subscription(account_id)
            tier = sub.tier.value if sub else metadata.get("tier", "solo")
            _trigger_provision(account_id, tier)

        return JSONResponse(result)

    # ── Subscription CRUD ────────────────────────────────────────────

    @router.get("/subscription/{account_id}")
    async def get_subscription(account_id: str) -> JSONResponse:
        """Get the current subscription for an account."""
        _validate_account_id(account_id)
        sub = mgr.get_subscription(account_id)
        if sub is None:
            raise HTTPException(status_code=404, detail="No subscription found")
        return JSONResponse(sub.to_dict())

    @router.post("/subscription/{account_id}/cancel")
    async def cancel_subscription(account_id: str) -> JSONResponse:
        """Cancel a subscription at the end of the billing period."""
        _validate_account_id(account_id)
        try:
            sub = mgr.cancel_subscription(account_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return JSONResponse(sub.to_dict())

    @router.post("/subscription/{account_id}/upgrade")
    async def upgrade_subscription(
        account_id: str,
        body: UpgradeRequest,
    ) -> JSONResponse:
        """Upgrade (or downgrade) a subscription tier."""
        _validate_account_id(account_id)
        try:
            new_tier = SubscriptionTier(body.new_tier)
            sub = mgr.upgrade_subscription(account_id, new_tier)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse(sub.to_dict())

    # ── Usage ────────────────────────────────────────────────────────

    @router.get("/usage/{account_id}")
    async def get_usage(account_id: str) -> JSONResponse:
        """Return current usage metrics for the account."""
        _validate_account_id(account_id)
        summary = mgr.get_usage_summary(account_id)
        return JSONResponse(summary)


    # ── PATCH-049c: flip account tier in murphy_users.db ─────────────────

    def _flip_account_tier(account_id: str, tier: str) -> None:
        """Update tier + role in murphy_users.db (user_accounts table) after payment.

        The DB stores account data as a JSON blob in the `data` column.
        account_id matches either the `account_id` field OR the `email` field.
        Falls back silently on any error — billing webhook must always return 200.
        PATCH-049c
        """
        try:
            import os, sqlite3, json as _json
            db_path = os.environ.get("MURPHY_USER_DB", "/var/lib/murphy-production/murphy_users.db")
            role_map = {
                "free": "user",
                "solo": "user",
                "business": "admin",
                "professional": "admin",
                "enterprise": "owner",
            }
            role = role_map.get(tier, "user")
            conn = sqlite3.connect(db_path)
            try:
                cur = conn.cursor()
                # Fetch matching row — account_id may be email or internal ID
                cur.execute(
                    "SELECT account_id, data FROM user_accounts "
                    "WHERE account_id=? OR email=? LIMIT 1",
                    (account_id, account_id),
                )
                row = cur.fetchone()
                if not row:
                    logger.warning("PATCH-049c: no user found for account_id=%s", account_id)
                    return
                db_account_id, raw_data = row
                data = _json.loads(raw_data) if raw_data else {}
                data["tier"] = tier
                data["role"] = role
                now = __import__("datetime").datetime.utcnow().isoformat() + "+00:00"
                cur.execute(
                    "UPDATE user_accounts SET data=?, updated_at=? WHERE account_id=?",
                    (_json.dumps(data), now, db_account_id),
                )
                conn.commit()
                logger.info(
                    "PATCH-049c: account_id=%s email=%s tier=%s role=%s updated",
                    db_account_id, data.get("email", "?"), tier, role,
                )
            finally:
                conn.close()
        except Exception as exc:
            logger.error("PATCH-049c: _flip_account_tier failed for %s: %s", account_id, exc)


    # ── PATCH-049b: Stripe checkout + webhook ─────────────────────────────

    @router.post("/checkout/stripe")
    async def stripe_checkout(request: Request) -> JSONResponse:
        """Create a Stripe Checkout Session and return the hosted URL.

        Body: { account_id, tier, interval ("monthly"|"annual") }
        Returns: { checkout_url: str }
        Stripe handles all card data — Murphy never touches raw card numbers.
        """
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        account_id = _validate_account_id(body.get("account_id", ""))
        tier_str = body.get("tier", "solo")
        interval_str = body.get("interval", "monthly")

        try:
            from src.subscription_manager import SubscriptionTier, BillingInterval
            tier = SubscriptionTier(tier_str)
            interval = BillingInterval(interval_str)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        import os
        success_url = os.environ.get("STRIPE_SUCCESS_URL", "https://murphy.systems/billing/success")
        cancel_url = os.environ.get("STRIPE_CANCEL_URL", "https://murphy.systems/billing/cancel")

        try:
            checkout_url = mgr.create_stripe_checkout_session(
                account_id=account_id,
                tier=tier,
                interval=interval,
                success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=cancel_url,
            )
            return JSONResponse({"ok": True, "checkout_url": checkout_url, "provider": "stripe"})
        except Exception as exc:
            logger.error("Stripe checkout failed for account=%s: %s", account_id, exc)
            return _safe_billing_error(exc, 502)

    @router.post("/webhooks/stripe")
    async def stripe_webhook(request: Request) -> JSONResponse:
        """Receive Stripe subscription lifecycle webhooks.

        Stripe posts signed events here on:
          - checkout.session.completed  → activate account
          - customer.subscription.updated → tier change
          - customer.subscription.deleted → cancel / downgrade to free
          - invoice.payment_failed        → grace period / suspend

        Signature verified via STRIPE_WEBHOOK_SECRET env var.
        Account tier is updated in murphy_users.db on activation.
        PATCH-049b, PATCH-049c
        """
        raw_body = await request.body()
        if len(raw_body) > _MAX_WEBHOOK_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Webhook payload too large")

        sig = request.headers.get("stripe-signature", "")
        import os
        webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

        try:
            result = mgr.handle_stripe_webhook(
                payload=raw_body.decode("utf-8", errors="replace"),
                signature=sig,
                webhook_secret=webhook_secret,
            )
        except ValueError as exc:
            logger.warning("Stripe webhook validation failed: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
        except Exception as exc:
            logger.error("Stripe webhook processing error: %s", exc)
            return _safe_billing_error(exc, 500)

        # PATCH-049c: if payment succeeded, flip the account tier in the user DB
        event_type = result.get("event_type", "")
        account_id = result.get("account_id", "")
        new_tier = result.get("tier", "")

        if event_type == "checkout.session.completed" and account_id and new_tier:
            _flip_account_tier(account_id, new_tier)
            _trigger_provision(account_id, new_tier)

        elif event_type == "customer.subscription.updated" and account_id and new_tier:
            _flip_account_tier(account_id, new_tier)

        elif event_type == "customer.subscription.deleted" and account_id:
            _flip_account_tier(account_id, "free")

        return JSONResponse({"received": True, **result})

    return router
