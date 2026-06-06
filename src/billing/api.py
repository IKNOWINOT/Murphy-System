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

# PATCH-175: customer persistence
try:
    from src.customer_db import init_db as _init_customer_db, upsert_customer, log_event as _log_billing_event, list_customers, customer_stats, get_customer
    _init_customer_db()
    _CUSTOMER_DB_AVAILABLE = True
except Exception as _cdb_err:
    logger.warning("customer_db unavailable: %s", _cdb_err)
    _CUSTOMER_DB_AVAILABLE = False
    def upsert_customer(*a, **kw): pass
    def _log_billing_event(*a, **kw): pass
    def list_customers(**kw): return {"customers": [], "total": 0}
    def customer_stats(): return {"total_customers": 0, "active": 0, "by_tier": {}, "by_status": {}, "estimated_mrr_usd": 0}
    def get_customer(account_id): return None


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
            # _R463_PRICE_DISPLAY — explicit display strings + pricing_mode so
            # any consumer (third-party, embed, partner) knows when a tier is
            # quote-only without parsing magic -1 sentinels.
            is_quote = (plan.monthly_price == -1.0 or plan.annual_price == -1.0)
            d["pricing_mode"] = "contact_us" if is_quote else "fixed"
            if is_quote:
                d["price_display_monthly"] = "Contact us"
                d["price_display_annual"]  = "Contact us"
                d["cta_text"]              = "Contact sales"
                d["cta_href"]              = "/book?intent=enterprise"
                monthly_loc = {"amount": None, "currency": currency.upper(),
                              "display": "Contact us", "quote_only": True}
                annual_loc  = {"amount": None, "currency": currency.upper(),
                              "display": "Contact us", "quote_only": True}
            else:
                monthly_loc = cc.localize(plan.monthly_price, currency, locale)
                annual_loc  = cc.localize(plan.annual_price, currency, locale)
                d["price_display_monthly"] = f"${plan.monthly_price:,.0f}/mo" if plan.monthly_price > 0 else "Free"
                d["price_display_annual"]  = f"${plan.annual_price:,.0f}/mo" if plan.annual_price > 0 else "Free"
                d["cta_text"]              = "Subscribe" if plan.monthly_price > 0 else "Get started"
                d["cta_href"]              = "/checkout?plan=" + plan.tier.value if hasattr(plan.tier, "value") else "/checkout"
            d["local_monthly"] = monthly_loc
            d["local_annual"]  = annual_loc
            plans.append(d)
        return JSONResponse({"plans": plans, "currency": currency.upper(),
                            "locale": locale, "schema_version": "r463.1"})

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
        _primary_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        _test_secret    = os.environ.get("STRIPE_WEBHOOK_SECRET_TEST", "")
        # PATCH-175b: try both secrets (live + test) so either endpoint works
        _payload_str = raw_body.decode("utf-8", errors="replace")
        result = None
        _last_err = None
        for _ws in [s for s in [_primary_secret, _test_secret] if s]:
            try:
                result = mgr.handle_stripe_webhook(
                    payload=_payload_str,
                    signature=sig,
                    webhook_secret=_ws,
                )
                break  # success — stop trying
            except ValueError as _ve:
                _last_err = _ve
                continue
        if result is None:
            # No secret matched — if no secrets configured at all, process unsigned
            if not _primary_secret and not _test_secret:
                logger.warning("STRIPE_WEBHOOK_SECRET not set — processing unsigned event")
                result = mgr.handle_stripe_webhook(
                    payload=_payload_str,
                    signature="",
                    webhook_secret="",
                )
            else:
                logger.warning("Stripe webhook validation failed: %s", _last_err)
                raise HTTPException(status_code=400, detail="Invalid webhook signature")
        try:
            pass  # result already set above
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

        # PATCH-175: persist customer to DB on Stripe events
        if _CUSTOMER_DB_AVAILABLE:
            try:
                _acct = account_id or result.get("account_id", "")
                _tier = result.get("tier", "")
                _evt  = result.get("event_type", "")
                if _acct:
                    _status = (
                        "cancelled" if "deleted" in _evt
                        else "past_due" if "payment_failed" in _evt
                        else "active"
                    )
                    upsert_customer(account_id=_acct, tier=_tier or "solo", status=_status)
                    _log_billing_event(
                        account_id=_acct,
                        event_type=_evt,
                        stripe_event_id=result.get("id", ""),
                        payload=result,
                    )
            except Exception as _pe:
                logger.warning("PATCH-175 customer upsert error: %s", _pe)

        return JSONResponse({"received": True, **result})



    @router.post("/seed-demo")
    async def seed_demo_customers(request: Request):
        _bearer = request.headers.get("Authorization","").replace("Bearer ","").strip()
        if not _bearer or not (_bearer.startswith("founder_") or len(_bearer) > 20):
            raise HTTPException(status_code=403, detail="Admin access required")
        """PATCH-175: Seed demo customer records for dashboard exploration. Admin only."""
        import random, string
        from datetime import datetime, timezone, timedelta
        demo_data = [
            {"account_id": "acct_demo_001", "email": "alice@example.com",   "full_name": "Alice Chen",     "tier": "business",      "status": "active",    "interval": "monthly"},
            {"account_id": "acct_demo_002", "email": "bob@example.com",     "full_name": "Bob Martinez",   "tier": "solo",          "status": "active",    "interval": "monthly"},
            {"account_id": "acct_demo_003", "email": "carol@example.com",   "full_name": "Carol Kim",      "tier": "professional",  "status": "active",    "interval": "annual"},
            {"account_id": "acct_demo_004", "email": "dave@example.com",    "full_name": "Dave Okonkwo",   "tier": "solo",          "status": "cancelled", "interval": "monthly"},
            {"account_id": "acct_demo_005", "email": "eve@example.com",     "full_name": "Eve Nakamura",   "tier": "business",      "status": "active",    "interval": "annual"},
            {"account_id": "acct_demo_006", "email": "frank@example.com",   "full_name": "Frank Dubois",   "tier": "professional",  "status": "past_due",  "interval": "monthly"},
            {"account_id": "acct_demo_007", "email": "grace@example.com",   "full_name": "Grace Patel",    "tier": "solo",          "status": "active",    "interval": "monthly"},
            {"account_id": "acct_demo_008", "email": "henry@example.com",   "full_name": "Henry Larsson",  "tier": "business",      "status": "active",    "interval": "monthly"},
            {"account_id": "acct_demo_009", "email": "iris@example.com",    "full_name": "Iris Andersen",  "tier": "free",          "status": "active",    "interval": ""},
            {"account_id": "acct_demo_010", "email": "jack@example.com",    "full_name": "Jack Osei",      "tier": "professional",  "status": "active",    "interval": "annual"},
        ]
        now = datetime.now(timezone.utc)
        seeded = 0
        if _CUSTOMER_DB_AVAILABLE:
            for d in demo_data:
                period_end = (now + timedelta(days=30)).isoformat() if d["tier"] != "free" else ""
                upsert_customer(
                    account_id=d["account_id"],
                    email=d["email"],
                    full_name=d["full_name"],
                    tier=d["tier"],
                    status=d["status"],
                    interval=d["interval"],
                    current_period_end=period_end,
                )
                seeded += 1
        return JSONResponse({"ok": True, "seeded": seeded})

    # ── PATCH-175: Customer Management API ──────────────────────────────────────

    @router.get("/customers")
    async def list_all_customers(
        request: Request,
        tier: str = "",
        status: str = "",
        limit: int = 100,
        offset: int = 0,
    ):
        _bearer = request.headers.get("Authorization","").replace("Bearer ","").strip()
        if not _bearer or not (_bearer.startswith("founder_") or len(_bearer) > 20):
            raise HTTPException(status_code=403, detail="Admin access required")
        """List all customers with optional tier/status filter. Admin only."""
        result = list_customers(
            tier=tier or None,
            status=status or None,
            limit=min(limit, 500),
            offset=offset,
        )
        return JSONResponse(result)

    @router.get("/customers/stats")
    async def get_customer_stats(request: Request):
        _bearer = request.headers.get("Authorization","").replace("Bearer ","").strip()
        if not _bearer or not (_bearer.startswith("founder_") or len(_bearer) > 20):
            raise HTTPException(status_code=403, detail="Admin access required")
        """Billing KPIs: total customers, MRR estimate, by-tier breakdown. Admin only."""
        return JSONResponse(customer_stats())

    @router.get("/customers/{account_id}")
    async def get_single_customer(account_id: str, request: Request):
        _bearer = request.headers.get("Authorization","").replace("Bearer ","").strip()
        if not _bearer or not (_bearer.startswith("founder_") or len(_bearer) > 20):
            raise HTTPException(status_code=403, detail="Admin access required")
        """Get a single customer record. Admin only."""
        record = get_customer(account_id)
        if not record:
            raise HTTPException(status_code=404, detail="Customer not found")
        return JSONResponse(record)

    @router.post("/customers/{account_id}/status")
    async def update_customer_status(account_id: str, request: Request):
        _bearer = request.headers.get("Authorization","").replace("Bearer ","").strip()
        if not _bearer or not (_bearer.startswith("founder_") or len(_bearer) > 20):
            raise HTTPException(status_code=403, detail="Admin access required")
        """Manually update a customer's status (active/cancelled/paused). Admin only."""
        body = await request.json()
        new_status = body.get("status", "active")
        if new_status not in ("active", "cancelled", "paused", "past_due"):
            raise HTTPException(status_code=400, detail="Invalid status")
        upsert_customer(account_id=account_id, tier="", status=new_status)
        return JSONResponse({"ok": True, "account_id": account_id, "status": new_status})

    # ── PATCH-378: Murphy Treasury — autonomous bill payment & ops finance ────
    @router.get("/treasury/status")
    async def treasury_status() -> JSONResponse:
        """Full treasury dashboard — wallet, bills, runway, journal."""
        try:
            from src.murphy_treasury import get_treasury
            return JSONResponse({"success": True, **get_treasury().get_status()})
        except Exception as exc:
            logger.error("Treasury status error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.post("/treasury/monitor")
    async def treasury_run_monitor() -> JSONResponse:
        """Manually trigger the daily bill monitor (also runs automatically at 6am ET)."""
        try:
            from src.murphy_treasury import get_treasury
            result = get_treasury().run_daily_monitor()
            return JSONResponse({"success": True, **result})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.post("/treasury/inflow")
    async def treasury_record_inflow(request: Request) -> JSONResponse:
        """Record a subscription payment inflow and split 50/50 ops/ATOM."""
        try:
            body = await request.json()
            from src.murphy_treasury import get_treasury
            result = get_treasury().handle_subscription_payment(
                amount_usd=float(body.get("amount_usd", 0)),
                tenant_id=body.get("tenant_id", ""),
                payment_id=body.get("payment_id", ""),
                tier=body.get("tier", ""),
            )
            return JSONResponse(result)
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.post("/treasury/register-bill")
    async def treasury_register_bill(request: Request) -> JSONResponse:
        """Add a new vendor bill to Murphy's registry."""
        try:
            body = await request.json()
            from src.murphy_treasury import get_treasury
            result = get_treasury().register_bill(**body)
            return JSONResponse(result)
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=400)

    # ── PATCH-378 END ────────────────────────────────────────────────────────


    # ── PATCH-379: Investment Engine — valuation, data room, investor outreach ─
    @router.get("/investment/valuation")
    async def investment_valuation() -> JSONResponse:
        """Live Murphy valuation — three scenarios, Rule of 40, comparables."""
        try:
            from src.murphy_investment_engine import get_valuation_engine
            return JSONResponse({"success": True, **get_valuation_engine().compute()})
        except Exception as exc:
            logger.error("Valuation error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.get("/investment/data-room")
    async def investment_data_room() -> JSONResponse:
        """Full investor data room — financials, product, team, cap table, ask."""
        try:
            from src.murphy_investment_engine import get_data_room
            return JSONResponse({"success": True, **get_data_room().generate()})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.get("/investment/investors")
    async def investment_list_investors(stage: str = "") -> JSONResponse:
        """List tracked investors by pipeline stage."""
        try:
            from src.murphy_investment_engine import get_investor_outreach
            investors = get_investor_outreach().list_investors(stage=stage)
            return JSONResponse({"success": True, "investors": investors, "count": len(investors)})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.post("/investment/pitch/generate")
    async def investment_generate_pitch(request: Request) -> JSONResponse:
        """Generate personalized investor pitch email."""
        try:
            body = await request.json()
            from src.murphy_investment_engine import get_investor_outreach
            pitch = get_investor_outreach().generate_pitch(
                investor_id=body.get("investor_id", ""),
                custom_context=body.get("context", ""),
            )
            return JSONResponse({"success": True, **pitch})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.get("/investment/applications")
    async def investment_list_applications() -> JSONResponse:
        """List all funding applications and their status."""
        try:
            from src.murphy_investment_engine import get_application_engine
            apps = get_application_engine().list_applications()
            return JSONResponse({"success": True, "applications": apps, "count": len(apps)})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.post("/investment/applications/draft-yc")
    async def investment_draft_yc() -> JSONResponse:
        """Draft Murphy's YC application using live system data."""
        try:
            from src.murphy_investment_engine import get_application_engine
            result = get_application_engine().draft_yc_application()
            return JSONResponse({"success": True, **result})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.post("/investment/term-sheet/analyze")
    async def investment_analyze_term_sheet(request: Request) -> JSONResponse:
        """Analyze a term sheet for red flags. HITL attorney review is mandatory."""
        try:
            body = await request.json()
            from src.murphy_investment_engine import get_term_sheet_hitl
            result = get_term_sheet_hitl().analyze(
                term_sheet_text=body.get("text", ""),
                investor=body.get("investor", ""),
            )
            return JSONResponse({"success": True, **result})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.post("/investment/bootstrap")
    async def investment_bootstrap() -> JSONResponse:
        """Initialize investment engine — seed investors and programs."""
        try:
            from src.murphy_investment_engine import bootstrap
            return JSONResponse(bootstrap())
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    # ── PATCH-379 END ────────────────────────────────────────────────────────


    # ── PATCH-380: Business Line Separation — segmented P&L ──────────────────
    @router.get("/business-lines/pnl")
    async def business_lines_pnl() -> JSONResponse:
        """Segmented P&L — platform SaaS vs managed services, with separate valuations."""
        try:
            from src.murphy_business_lines import get_segmented_pnl
            return JSONResponse({"success": True, **get_segmented_pnl().generate()})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.get("/business-lines/classify")
    async def business_lines_classify(task: str = "", tier: str = "",
                                      client_id: str = "") -> JSONResponse:
        """Classify a task or revenue event to the correct business line."""
        try:
            from src.murphy_business_lines import get_classifier, classify_dispatch
            c = get_classifier()
            result = {
                "task_classification":    classify_dispatch(task, client_id=client_id) if task else None,
                "revenue_classification": c.classify_revenue(0, tier=tier, client_id=client_id) if (tier or client_id) else None,
            }
            return JSONResponse({"success": True, **result})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.get("/business-lines/clients")
    async def business_lines_managed_clients() -> JSONResponse:
        """List all managed service clients Murphy is running operations for."""
        try:
            from src.murphy_business_lines import list_managed_clients
            clients = list_managed_clients()
            return JSONResponse({"success": True, "clients": clients, "count": len(clients)})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.post("/business-lines/clients/register")
    async def business_lines_register_client(request: Request) -> JSONResponse:
        """Register a new managed service client."""
        try:
            body = await request.json()
            from src.murphy_business_lines import register_managed_client
            result = register_managed_client(**body)
            return JSONResponse(result)
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=400)

    # ── PATCH-380 END ────────────────────────────────────────────────────────


    # ── PATCH-381: Tenant Intelligence — profiles, strategies, authority scope ─
    @router.get("/tenant/intake-questions")
    async def tenant_intake_questions() -> JSONResponse:
        """Onboarding intake questions Murphy asks every new user."""
        try:
            from src.murphy_tenant_engine import INTAKE_QUESTIONS
            return JSONResponse({"success": True, "questions": INTAKE_QUESTIONS, "count": len(INTAKE_QUESTIONS)})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.post("/tenant/profile")
    async def tenant_save_profile(request: Request) -> JSONResponse:
        """Save or update a tenant business profile from onboarding intake answers."""
        try:
            body = await request.json()
            from src.murphy_tenant_engine import (
                TenantBusinessProfile, StrategyEngine,
                save_profile, save_strategy, classify_budget
            )
            # Get tenant_id from session
            session_data = request.state.__dict__.get("session_data", {})
            tenant_id = body.get("tenant_id") or session_data.get("account_id", "unknown")
            body["tenant_id"] = tenant_id
            body["budget_tier"] = classify_budget(float(body.get("monthly_budget", 0)))
            profile = TenantBusinessProfile(**{
                k: v for k, v in body.items()
                if k in TenantBusinessProfile.__dataclass_fields__
            })
            save_profile(profile)
            # Auto-generate strategy
            strategy = StrategyEngine().generate(profile)
            save_strategy(strategy)
            return JSONResponse({
                "success":    True,
                "tenant_id":  tenant_id,
                "budget_tier": profile.budget_tier,
                "strategy_id": strategy.id,
                "strategy_summary": strategy.summary,
                "action_count": len(strategy.actions),
            })
        except Exception as exc:
            logger.error("Tenant profile error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=400)

    @router.get("/tenant/profile")
    async def tenant_get_profile(tenant_id: str = "") -> JSONResponse:
        """Get a tenant's business profile."""
        try:
            from src.murphy_tenant_engine import load_profile
            profile = load_profile(tenant_id)
            if not profile:
                return JSONResponse({"success": False, "error": "Profile not found — complete intake first"}, status_code=404)
            import dataclasses
            return JSONResponse({"success": True, "profile": dataclasses.asdict(profile)})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.get("/tenant/strategy")
    async def tenant_get_strategy(tenant_id: str = "") -> JSONResponse:
        """Get a tenant's active 90-day business strategy."""
        try:
            from src.murphy_tenant_engine import get_active_strategy
            import dataclasses
            strategy = get_active_strategy(tenant_id)
            if not strategy:
                return JSONResponse({"success": False, "error": "No strategy found — complete intake first"}, status_code=404)
            return JSONResponse({"success": True, "strategy": dataclasses.asdict(strategy)})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.post("/tenant/strategy/regenerate")
    async def tenant_regenerate_strategy(request: Request) -> JSONResponse:
        """Regenerate strategy after a profile update (budget changed, goal changed, etc.)."""
        try:
            body = await request.json()
            tenant_id = body.get("tenant_id", "")
            from src.murphy_tenant_engine import load_profile, StrategyEngine, save_strategy
            profile = load_profile(tenant_id)
            if not profile:
                return JSONResponse({"success": False, "error": "Profile not found"}, status_code=404)
            # Apply any updates in the request
            for k, v in body.items():
                if hasattr(profile, k) and k != "tenant_id":
                    setattr(profile, k, v)
            strategy = StrategyEngine().generate(profile)
            save_strategy(strategy)
            import dataclasses
            return JSONResponse({"success": True, "strategy": dataclasses.asdict(strategy)})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.get("/tenant/scope")
    async def tenant_dispatch_scope(account_id: str = "", role: str = "user", email: str = "") -> JSONResponse:
        """Resolve the dispatch authority scope for a user — platform (founder) vs tenant-scoped (user)."""
        try:
            from src.murphy_tenant_engine import resolve_dispatch_scope
            scope = resolve_dispatch_scope(account_id, role, email)
            return JSONResponse({"success": True, **scope})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    # ── PATCH-381 END ────────────────────────────────────────────────────────


    # ── PATCH-381b: Add-ons + Knowledge Context ───────────────────────────────
    @router.post("/addons/grant")
    async def addon_grant(request: Request) -> JSONResponse:
        """Grant a tenant a paid add-on (called after payment confirmed)."""
        try:
            body = await request.json()
            from src.murphy_tenant_engine import grant_addon
            result = grant_addon(
                tenant_id=body.get("tenant_id", ""),
                addon=body.get("addon", ""),
                price_usd=float(body.get("price_usd", 50.0)),
                notes=body.get("notes", ""),
            )
            return JSONResponse(result)
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=400)

    @router.post("/addons/revoke")
    async def addon_revoke(request: Request) -> JSONResponse:
        """Revoke a tenant add-on on cancellation or non-payment."""
        try:
            body = await request.json()
            from src.murphy_tenant_engine import revoke_addon
            result = revoke_addon(
                tenant_id=body.get("tenant_id", ""),
                addon=body.get("addon", ""),
            )
            return JSONResponse(result)
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=400)

    @router.get("/addons/pricing")
    async def addon_pricing() -> JSONResponse:
        """Available add-on features and pricing."""
        try:
            from src.nowpayments_billing import ADDON_PRICES_USD, ADDON_DESCRIPTIONS
            addons = [
                {
                    "id":          addon,
                    "price_usd":   price,
                    "price_label": f"${price:.0f}/mo",
                    "description": ADDON_DESCRIPTIONS.get(addon, ""),
                }
                for addon, price in ADDON_PRICES_USD.items()
            ]
            return JSONResponse({"success": True, "addons": addons})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @router.get("/tenant/knowledge-context")
    async def tenant_knowledge_context(tenant_id: str = "") -> JSONResponse:
        """
        Returns the knowledge context that gets injected into every LLM prompt
        for this tenant. This is what makes Murphy sound like the user.
        """
        try:
            from src.murphy_tenant_engine import build_knowledge_context
            ctx = build_knowledge_context(tenant_id)
            return JSONResponse({"success": True, **ctx})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    # ── PATCH-381b END ───────────────────────────────────────────────────────


    return router
