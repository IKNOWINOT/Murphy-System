# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
NOWPayments Crypto Billing — Murphy System
==========================================
Design Label: BILLING-CRYPTO-001
Owner: Platform / Billing

Replaces Stripe in the Murphy payment pipeline.
Accepts BTC, ETH, SOL, USDC, USDT, and 290+ coins via NOWPayments.
All prices quoted in USD — NOWPayments converts at current market rate.

Supports:
  - One-time invoices (manual/enterprise)
  - Recurring subscription plans (monthly, annual)
  - IPN webhook verification + tier upgrade on payment
  - Per-tenant billing records in SQLite

Environment:
  NOWPAYMENTS_API_KEY    — your NOWPayments API key (required)
  NOWPAYMENTS_IPN_SECRET — IPN HMAC secret (from dashboard → IPN settings)
  NOWPAYMENTS_API_BASE   — override base URL (default: https://api.nowpayments.io/v1)

API docs: https://documenter.getpostman.com/view/7907941/2s93JusNJt

Copyright © 2020 Inoni LLC — Creator: Corey Post — License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("murphy.billing.crypto")

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

NOWPAYMENTS_BASE = os.environ.get(
    "NOWPAYMENTS_API_BASE", "https://api.nowpayments.io/v1"
)

DB_PATH = "/var/lib/murphy-production/billing.db"
REQUEST_TIMEOUT = 20  # seconds

# USD prices per tier per month
TIER_PRICES_USD: Dict[str, float] = {
    "free":       0.00,
    "solo":      99.00,
    "team":     399.00,
    "business": 799.00,
    # enterprise is manual invoice — not automated
}

# Annual prices (20% discount)
TIER_PRICES_ANNUAL_USD: Dict[str, float] = {
    tier: round(price * 12 * 0.80, 2)
    for tier, price in TIER_PRICES_USD.items()
}

# ── Add-on features (billed on top of any base tier) ──────────────────────────
ADDON_PRICES_USD: Dict[str, float] = {
    "system_influence": 50.00,   # User commands affect platform-wide config
                                  # Founder (cpost@murphy.systems) gets this free
}

ADDON_DESCRIPTIONS: Dict[str, str] = {
    "system_influence": (
        "System Influence — your commands can modify platform-wide settings, "
        "global agent config, and shared Murphy capabilities. "
        "Founder has this included free at no charge."
    ),
}


# Human-readable plan descriptions
TIER_DESCRIPTIONS: Dict[str, str] = {
    "solo":     "Murphy Solo — 1 seat, full dispatch, file pipeline, morning brief",
    "team":     "Murphy Team — 5 seats, CRM, outreach, compliance, voice",
    "business": "Murphy Business — 15 seats, all frameworks, API, PiCar-X",
}


# ─────────────────────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NowPaymentsPlan:
    """A NOWPayments subscription plan (server-side object)."""
    tier:       str
    interval:   str          # "monthly" | "annual"
    plan_id:    str = ""     # assigned by NOWPayments
    amount_usd: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class BillingRecord:
    """One subscription record per tenant."""
    id:              str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id:       str = ""
    email:           str = ""
    tier:            str = "free"
    interval:        str = "monthly"
    plan_id:         str = ""     # NOWPayments plan_id
    subscription_id: str = ""     # NOWPayments subscription id
    payment_id:      str = ""     # latest payment id
    status:          str = "pending"  # pending | active | cancelled | expired
    amount_usd:      float = 0.0
    amount_crypto:   str = ""     # e.g. "0.00123 BTC"
    pay_currency:    str = ""     # coin user chose
    created_at:      str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    activated_at:    str = ""
    expires_at:      str = ""
    ipn_raw:         str = ""     # last IPN payload (JSON)


# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_schema() -> None:
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS billing_records (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                email TEXT NOT NULL,
                tier TEXT NOT NULL DEFAULT 'free',
                interval TEXT NOT NULL DEFAULT 'monthly',
                plan_id TEXT,
                subscription_id TEXT,
                payment_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                amount_usd REAL DEFAULT 0.0,
                amount_crypto TEXT,
                pay_currency TEXT,
                created_at TEXT NOT NULL,
                activated_at TEXT,
                expires_at TEXT,
                ipn_raw TEXT
            );

            CREATE TABLE IF NOT EXISTS nowpayments_plans (
                tier TEXT NOT NULL,
                interval TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                amount_usd REAL NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (tier, interval)
            );

            CREATE TABLE IF NOT EXISTS ipn_events (
                id TEXT PRIMARY KEY,
                payment_id TEXT,
                payment_status TEXT,
                order_id TEXT,
                tenant_id TEXT,
                raw TEXT,
                processed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_billing_tenant
                ON billing_records(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_billing_email
                ON billing_records(email);
        """)


# ─────────────────────────────────────────────────────────────────────────────
# Core billing class
# ─────────────────────────────────────────────────────────────────────────────



# ── Vault read (PATCH-407 + PATCH-408): vault-first with tenant scoping ─────
class CrossTenantReadRefused(Exception):
    """Raised when a tenant op tries to read another tenant's identity secret."""
    pass


def _vault_or_env(name: str, tenant_id: str = None,
                  caller_tenant: str = None,
                  require_tenant_override: bool = False) -> str:
    """Read a secret by name. PATCH-408 canonical accessor.

    Scoping rules (per .agents/rules/vault_and_accounting_canon.md):
      - tenant_id=None        → reads class='platform' only (Murphy's engine)
      - tenant_id='acmecorp'  → tries class='tenant_identity' tenant=acmecorp
                                 first, falls back to class='platform' default
                                 (unless require_tenant_override=True)
      - caller_tenant cross-check: if caller_tenant is set AND differs from
        tenant_id, raises CrossTenantReadRefused. Inoni/admin code that
        legitimately serves multiple tenants must NOT pass caller_tenant.

    Vault is canonical. Env is a boot-ordering fallback for platform reads
    only; tenant_identity reads never fall back to env.
    """
    # Cross-tenant guard
    if caller_tenant and tenant_id and caller_tenant != tenant_id:
        raise CrossTenantReadRefused(
            f"tenant '{caller_tenant}' cannot read identity secret of '{tenant_id}'"
        )

    try:
        from src.patch405_secrets_vault import _db, _decrypt, _CRYPTO_OK, init_db
        if _CRYPTO_OK:
            init_db()
            conn = _db()
            # 1) If tenant_id given, try tenant_identity first
            if tenant_id:
                row = conn.execute(
                    "SELECT encrypted_value, nonce FROM vault_secrets "
                    "WHERE name=? AND class='tenant_identity' "
                    "AND tenant_id=? AND revoked_at IS NULL",
                    (name, tenant_id)
                ).fetchone()
                if row:
                    conn.close()
                    try:
                        return _decrypt(row[0], row[1])
                    except (TypeError, ValueError):
                        # Storage-type drift on legacy rows; treat as missing
                        pass
                if require_tenant_override:
                    conn.close()
                    return ""

            # 2) Platform fallback (default behavior, or tenant_id=None)
            row = conn.execute(
                "SELECT encrypted_value, nonce FROM vault_secrets "
                "WHERE name=? AND class='platform' AND revoked_at IS NULL",
                (name,)
            ).fetchone()
            conn.close()
            if row:
                try:
                    return _decrypt(row[0], row[1])
                except (TypeError, ValueError):
                    pass
    except Exception:
        pass

    # 3) Env fallback (platform reads only)
    if not tenant_id or not require_tenant_override:
        return os.environ.get(name, "")
    return ""


class NowPaymentsBilling:
    """
    Murphy crypto billing via NOWPayments.

    Usage::
        billing = NowPaymentsBilling()
        # On first boot — register plans once
        billing.ensure_plans_registered()
        # When user subscribes
        result = billing.create_subscription(
            tenant_id="abc123",
            email="user@example.com",
            tier="solo",
            interval="monthly",
        )
        # result["payment_url"] → send user here
        # IPN fires at /api/billing/nowpayments/ipn → call billing.handle_ipn(payload, sig)
    """

    def __init__(self, api_key: str = "", ipn_secret: str = "") -> None:
        # 2026-06-07: prefer Murphy vault → fall back to env (for boot ordering)
        # Both NOWPAYMENTS_API_KEY (write-class) and NOWPAYMENTS_IPN_SECRET
        # (destructive-class) live in /var/lib/murphy-production/murphy_vault.db.
        # See patch405_secrets_vault.py.
        self._api_key    = api_key    or _vault_or_env("NOWPAYMENTS_API_KEY")
        self._ipn_secret = ipn_secret or _vault_or_env("NOWPAYMENTS_IPN_SECRET")
        self._lock = threading.Lock()
        _ensure_schema()

        if not self._api_key:
            logger.warning(
                "BILLING-CRYPTO-001: NOWPAYMENTS_API_KEY not set — "
                "billing will return stub URLs until key is configured"
            )

    # ── Internal HTTP ─────────────────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: Dict = None) -> Dict:
        url = f"{NOWPAYMENTS_BASE}{path}"
        r = requests.get(url, headers=self._headers(), params=params or {},
                         timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: Dict) -> Dict:
        url = f"{NOWPAYMENTS_BASE}{path}"
        r = requests.post(url, headers=self._headers(),
                          json=body, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()

    # ── Plan management ────────────────────────────────────────────────────────

    def ensure_plans_registered(self) -> Dict[str, str]:
        """
        Create NOWPayments subscription plans for all tiers if not yet registered.
        Call once at boot. Returns {tier_interval: plan_id}.
        """
        if not self._api_key:
            return {}

        results = {}
        with _db() as conn:
            existing = {
                f"{row['tier']}_{row['interval']}": row['plan_id']
                for row in conn.execute(
                    "SELECT tier, interval, plan_id FROM nowpayments_plans"
                ).fetchall()
            }

        base_url = os.environ.get("MURPHY_BASE_URL", "https://murphy.systems")

        for tier, price_usd in TIER_PRICES_USD.items():
            if tier == "free" or price_usd == 0:
                continue

            for interval in ["monthly"]:
                key = f"{tier}_{interval}"
                if key in existing:
                    results[key] = existing[key]
                    logger.info("BILLING: plan %s already registered: %s", key, existing[key])
                    continue

                amount = price_usd
                try:
                    resp = self._post("/subscriptions/plans", {
                        "title":            f"Murphy {tier.title()} — {interval}",
                        "interval_day":     30,
                        "amount":           amount,
                        "currency":         "usd",
                        "description":      TIER_DESCRIPTIONS.get(tier, f"Murphy {tier}"),
                        "ipn_callback_url": f"{base_url}/api/billing/nowpayments/ipn",
                        "success_url":      f"{base_url}/billing/success?tier={tier}",
                        "cancel_url":       f"{base_url}/billing/cancel",
                        "partially_paid_url": f"{base_url}/billing/partial",
                    })
                    plan_id = str(resp.get("id", ""))
                    if plan_id:
                        with _db() as conn:
                            conn.execute(
                                """INSERT OR REPLACE INTO nowpayments_plans
                                   (tier, interval, plan_id, amount_usd, created_at)
                                   VALUES (?,?,?,?,?)""",
                                (tier, interval, plan_id, amount,
                                 datetime.now(timezone.utc).isoformat())
                            )
                        results[key] = plan_id
                        logger.info("BILLING: registered plan %s → %s", key, plan_id)
                    else:
                        logger.warning("BILLING: no plan_id in response for %s: %s", key, resp)

                except Exception as exc:
                    logger.error("BILLING: failed to register plan %s: %s", key, exc)

        return results

    def get_plan_id(self, tier: str, interval: str = "monthly") -> Optional[str]:
        """Look up registered NOWPayments plan_id for a tier."""
        with _db() as conn:
            row = conn.execute(
                "SELECT plan_id FROM nowpayments_plans WHERE tier=? AND interval=?",
                (tier, interval)
            ).fetchone()
            return row["plan_id"] if row else None

    # ── Subscription creation ─────────────────────────────────────────────────

    def create_subscription(
        self,
        tenant_id: str,
        email: str,
        tier: str,
        interval: str = "monthly",
    ) -> Dict[str, Any]:
        """
        Create a NOWPayments subscription for a tenant.
        Sends a payment link to the user's email automatically.
        Returns {"success": bool, "payment_url": str, "record_id": str, "message": str}
        """
        if tier not in TIER_PRICES_USD or tier == "free":
            return {"success": False, "message": f"Invalid tier: {tier}"}

        plan_id = self.get_plan_id(tier, interval)
        if not plan_id:
            # Try to register plans on the fly
            self.ensure_plans_registered()
            plan_id = self.get_plan_id(tier, interval)

        record = BillingRecord(
            tenant_id=tenant_id,
            email=email,
            tier=tier,
            interval=interval,
            plan_id=plan_id or "",
            amount_usd=TIER_PRICES_USD[tier],
        )

        # If no API key — save record as pending, return stub
        if not self._api_key or not plan_id:
            record.status = "pending_key_config"
            self._save_record(record)
            return {
                "success":     False,
                "message":     "NOWPAYMENTS_API_KEY not configured — billing pending setup",
                "record_id":   record.id,
                "payment_url": "",
            }

        try:
            resp = self._post("/subscriptions", {
                "subscription_plan_id": int(plan_id),
                "email": email,
            })
            subscription_id = str(resp.get("id", ""))
            payment_url = resp.get("payment_url", "") or resp.get("checkout_url", "")

            record.subscription_id = subscription_id
            record.status = "payment_pending"
            self._save_record(record)

            logger.info(
                "BILLING: subscription created for %s tier=%s sub_id=%s",
                email, tier, subscription_id
            )
            return {
                "success":         True,
                "payment_url":     payment_url,
                "subscription_id": subscription_id,
                "record_id":       record.id,
                "message": (
                    f"Payment link sent to {email}. "
                    f"Pay in any crypto at current USD rate. "
                    f"Monthly: ${TIER_PRICES_USD[tier]:.0f} USD equivalent."
                ),
            }

        except requests.HTTPError as exc:
            logger.error("BILLING: NOWPayments API error for %s: %s", email, exc)
            record.status = "error"
            self._save_record(record)
            return {
                "success": False,
                "message": f"Payment provider error: {exc}",
                "record_id": record.id,
            }
        except Exception as exc:
            logger.error("BILLING: unexpected error for %s: %s", email, exc)
            record.status = "error"
            self._save_record(record)
            return {
                "success": False,
                "message": f"Billing error: {exc}",
                "record_id": record.id,
            }

    # ── IPN webhook handling ──────────────────────────────────────────────────

    def verify_ipn_signature(self, payload: str, signature: str) -> bool:
        """
        Verify the HMAC-SHA512 signature from NOWPayments IPN.
        Header: x-nowpayments-sig
        """
        if not self._ipn_secret:
            logger.warning("BILLING: IPN_SECRET not set — skipping signature verification")
            return True  # allow in dev; enforce in prod

        try:
            # NOWPayments signs the sorted JSON payload
            sorted_payload = json.dumps(
                json.loads(payload), sort_keys=True, separators=(",", ":")
            )
            expected = hmac.new(
                self._ipn_secret.encode(),
                sorted_payload.encode(),
                hashlib.sha512,
            ).hexdigest()
            return hmac.compare_digest(expected.lower(), signature.lower())
        except Exception as exc:
            logger.error("BILLING: IPN signature verification error: %s", exc)
            return False

    def handle_ipn(self, payload: Dict[str, Any], raw_body: str = "", signature: str = "") -> Dict[str, Any]:
        """
        Process a NOWPayments IPN (Instant Payment Notification) webhook.
        Called by POST /api/billing/nowpayments/ipn

        On confirmed payment → upgrades tenant tier in user_accounts DB.
        """
        if signature and not self.verify_ipn_signature(raw_body, signature):
            return {"success": False, "message": "invalid signature"}

        payment_id  = str(payload.get("payment_id", ""))
        status      = payload.get("payment_status", "")
        order_id    = str(payload.get("order_id", ""))  # we store tenant_id here
        pay_amount  = payload.get("pay_amount", "")
        pay_currency= payload.get("pay_currency", "")

        # Dedup
        event_id = f"ipn_{payment_id}_{status}"
        with _db() as conn:
            if conn.execute(
                "SELECT id FROM ipn_events WHERE id=?", (event_id,)
            ).fetchone():
                return {"success": True, "message": "duplicate IPN — already processed"}

            conn.execute(
                """INSERT INTO ipn_events
                   (id, payment_id, payment_status, order_id, tenant_id, raw, processed_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (event_id, payment_id, status, order_id, order_id,
                 json.dumps(payload), datetime.now(timezone.utc).isoformat())
            )

        logger.info("BILLING: IPN received payment_id=%s status=%s tenant=%s",
                    payment_id, status, order_id)

        # Update billing record
        if status in ("confirmed", "finished"):
            self._activate_subscription(
                tenant_id=order_id,
                payment_id=payment_id,
                pay_amount=str(pay_amount),
                pay_currency=pay_currency,
                raw=json.dumps(payload),
            )
            return {"success": True, "message": "subscription activated"}

        elif status in ("expired", "failed", "refunded"):
            self._deactivate_subscription(order_id, status, json.dumps(payload))
            return {"success": True, "message": f"subscription {status}"}

        return {"success": True, "message": f"IPN received — status: {status}"}

    def _activate_subscription(
        self,
        tenant_id: str,
        payment_id: str,
        pay_amount: str,
        pay_currency: str,
        raw: str,
    ) -> None:
        """Activate tenant tier on confirmed payment."""
        now = datetime.now(timezone.utc).isoformat()
        with _db() as conn:
            row = conn.execute(
                """SELECT id, tier FROM billing_records
                   WHERE tenant_id=? ORDER BY created_at DESC LIMIT 1""",
                (tenant_id,)
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE billing_records SET
                       status='active', payment_id=?, amount_crypto=?, pay_currency=?,
                       activated_at=?, ipn_raw=?
                       WHERE id=?""",
                    (payment_id, f"{pay_amount} {pay_currency}",
                     pay_currency, now, raw, row["id"])
                )
                tier = row["tier"]
            else:
                logger.warning("BILLING: no billing record for tenant %s", tenant_id)
                tier = "solo"  # default safe tier

        # Upgrade the user account tier
        self._upgrade_user_tier(tenant_id, tier)
        logger.info("BILLING: tenant %s activated on tier=%s", tenant_id, tier)

    def _deactivate_subscription(self, tenant_id: str, status: str, raw: str) -> None:
        """Downgrade tenant on payment failure/expiry."""
        with _db() as conn:
            conn.execute(
                "UPDATE billing_records SET status=?, ipn_raw=? WHERE tenant_id=?",
                (status, raw, tenant_id)
            )
        self._upgrade_user_tier(tenant_id, "free")
        logger.info("BILLING: tenant %s downgraded to free — reason: %s", tenant_id, status)

    def _upgrade_user_tier(self, tenant_id: str, tier: str) -> None:
        """Write tier upgrade to murphy_users.db user_accounts."""
        try:
            import json as _json
            USERS_DB = "/var/lib/murphy-production/murphy_users.db"
            with sqlite3.connect(USERS_DB, timeout=8) as conn:
                row = conn.execute(
                    "SELECT account_id, data FROM user_accounts WHERE account_id=? OR email=?",
                    (tenant_id, tenant_id)
                ).fetchone()
                if row:
                    try:
                        data = _json.loads(row[1]) if row[1] else {}
                    except Exception:
                        data = {}
                    data["tier"] = tier
                    data["tier_updated_at"] = datetime.now(timezone.utc).isoformat()
                    conn.execute(
                        "UPDATE user_accounts SET data=? WHERE account_id=?",
                        (_json.dumps(data), row[0])
                    )
                    logger.info("BILLING: user %s tier → %s", row[0], tier)
                else:
                    logger.warning("BILLING: no user account found for tenant %s", tenant_id)
        except Exception as exc:
            logger.error("BILLING: tier upgrade DB error: %s", exc)

    # ── Record management ─────────────────────────────────────────────────────

    def _save_record(self, rec: BillingRecord) -> None:
        with _db() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO billing_records
                   (id, tenant_id, email, tier, interval, plan_id, subscription_id,
                    payment_id, status, amount_usd, amount_crypto, pay_currency,
                    created_at, activated_at, expires_at, ipn_raw)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rec.id, rec.tenant_id, rec.email, rec.tier, rec.interval,
                 rec.plan_id, rec.subscription_id, rec.payment_id, rec.status,
                 rec.amount_usd, rec.amount_crypto, rec.pay_currency,
                 rec.created_at, rec.activated_at, rec.expires_at, rec.ipn_raw)
            )

    # ── Status + admin ────────────────────────────────────────────────────────

    def get_tenant_status(self, tenant_id: str) -> Dict[str, Any]:
        """Get billing status for a tenant."""
        with _db() as conn:
            row = conn.execute(
                """SELECT * FROM billing_records
                   WHERE tenant_id=? ORDER BY created_at DESC LIMIT 1""",
                (tenant_id,)
            ).fetchone()
            if not row:
                return {"tier": "free", "status": "no_subscription", "tenant_id": tenant_id}
            return dict(row)

    def list_active_subscriptions(self, limit: int = 100) -> List[Dict]:
        """List all active subscriptions."""
        with _db() as conn:
            rows = conn.execute(
                "SELECT * FROM billing_records WHERE status='active' LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_revenue_summary(self) -> Dict[str, Any]:
        """MRR and subscriber count by tier."""
        with _db() as conn:
            rows = conn.execute(
                """SELECT tier, COUNT(*) as count, SUM(amount_usd) as mrr
                   FROM billing_records WHERE status='active'
                   GROUP BY tier"""
            ).fetchall()
            tiers = [dict(r) for r in rows]
            total_mrr = sum(t["mrr"] or 0 for t in tiers)
            total_subs = sum(t["count"] for t in tiers)
            return {
                "mrr_usd": total_mrr,
                "total_subscribers": total_subs,
                "arr_usd": total_mrr * 12,
                "by_tier": tiers,
            }

    def get_pricing_table(self) -> List[Dict[str, Any]]:
        """Return the full pricing table for the UI."""
        return [
            {
                "tier": "free",
                "name": "Free",
                "price_monthly": 0,
                "seats": 1,
                "features": [
                    "Chat console",
                    "5 dispatches/day",
                    "No swarm access",
                    "No CRM",
                ],
            },
            {
                "tier": "solo",
                "name": "Solo",
                "price_monthly": 99,
                "seats": 1,
                "features": [
                    "Full swarm dispatch",
                    "File upload → artifacts",
                    "Daily morning brief",
                    "10 automations",
                    "Bring your own LLM",
                    "Voice control",
                ],
            },
            {
                "tier": "team",
                "name": "Team",
                "price_monthly": 399,
                "seats": 5,
                "seat_extra_usd": 79,
                "features": [
                    "Everything in Solo",
                    "CRM + outreach",
                    "1 compliance framework",
                    "Shared artifact folders",
                    "50 automations",
                    "Team voice profiles",
                ],
            },
            {
                "tier": "business",
                "name": "Business",
                "price_monthly": 799,
                "seats": 15,
                "seat_extra_usd": 79,
                "features": [
                    "Everything in Team",
                    "All compliance frameworks",
                    "Multi-integration",
                    "Full API access",
                    "PiCar-X / robotics",
                    "Priority support",
                ],
            },
            {
                "tier": "enterprise",
                "name": "Enterprise",
                "price_monthly": None,
                "seats": None,
                "features": [
                    "Dedicated server",
                    "Custom CEO soul document",
                    "White-label",
                    "Full source visibility",
                    "SLA",
                    "Custom compliance build",
                ],
                "cta": "Contact us",
            },
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

_billing: Optional[NowPaymentsBilling] = None
_billing_lock = threading.Lock()


def get_billing() -> NowPaymentsBilling:
    global _billing
    if _billing is None:
        with _billing_lock:
            if _billing is None:
                _billing = NowPaymentsBilling()
    return _billing
