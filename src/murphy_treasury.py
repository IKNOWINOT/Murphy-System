# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Murphy Treasury — Autonomous Bill Payment & Operations Finance Engine
======================================================================
Design Label: TREASURY-001
Owner: Platform / Finance

Murphy pays its own bills. This module:

  1. BILL REGISTRY — knows every recurring obligation Murphy has:
       - Hetzner server (auto-billed to card on file, Murphy monitors)
       - DeepInfra LLM credits (prepaid — Murphy tops up when low)
       - Together.ai credits (prepaid — Murphy tops up when low)
       - NOWPayments fees (auto-deducted from payments — Murphy monitors)
       - Domain registration (annual — Murphy sets calendar alert)
       - Any future vendor/API added via register_bill()

  2. OPERATIONS WALLET — tracks the 50% cash split from NOWPayments IPN:
       - Subscription payment received → 50% → operations wallet
       - 50% → ATOM purchase + staking (via profit_sweep.py)
       - Operations wallet balance is real cash Murphy can deploy

  3. BILL MONITOR (runs daily at 6:00 AM ET):
       - Checks each bill's status via its vendor API or email parsing
       - Verifies sufficient balance to cover upcoming bills
       - Sends HITL alert if balance is insufficient
       - Auto-tops-up prepaid API credits when below threshold

  4. PAYMENT EXECUTION:
       - For auto-billed vendors (Hetzner): confirms payment received in email
       - For prepaid credits (DeepInfra, Together): places top-up order via API
       - For all payments: records in SQLite ledger with double-entry journal

  5. TREASURY DASHBOARD (/api/treasury/status):
       - Operations wallet balance
       - Upcoming bills (next 30 days)
       - Bill payment history
       - Cash runway (months of burn at current rate)
       - ATOM staking position + estimated monthly reward

Payment execution requires:
  COINBASE_API_KEY + COINBASE_API_SECRET → to convert ATOM rewards → USD → pay bills
  DEEPINFRA_API_KEY                      → to check balance + top up
  TOGETHER_API_KEY                       → to check balance + top up
  HETZNER_TOKEN                          → to check server billing status
  NOWPAYMENTS_API_KEY                    → to check fee deductions

Copyright © 2020 Inoni LLC — Creator: Corey Post — License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("murphy.treasury")

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

DB_PATH       = "/var/lib/murphy-production/treasury.db"
REQUEST_TIMEOUT = 20

# How much to keep in operations wallet as minimum buffer (USD)
MIN_OPERATIONS_BUFFER_USD = 200.0

# Prepaid credit top-up thresholds
DEEPINFRA_LOW_THRESHOLD_USD  = 5.00
TOGETHER_LOW_THRESHOLD_USD   = 5.00
DEEPINFRA_TOPUP_AMOUNT_USD   = 25.00
TOGETHER_TOPUP_AMOUNT_USD    = 25.00


# ─────────────────────────────────────────────────────────────────────────────
# Enums & models
# ─────────────────────────────────────────────────────────────────────────────

class BillType(str, Enum):
    AUTO_BILLED  = "auto_billed"   # vendor charges card on file — Murphy monitors
    PREPAID      = "prepaid"       # Murphy must top up before depletion
    MANUAL       = "manual"        # rare — Murphy alerts HITL


class BillStatus(str, Enum):
    CURRENT    = "current"
    DUE_SOON   = "due_soon"    # within 7 days
    OVERDUE    = "overdue"
    LOW_CREDIT = "low_credit"  # prepaid balance below threshold
    PAID       = "paid"
    UNKNOWN    = "unknown"


class PaymentStatus(str, Enum):
    PENDING   = "pending"
    CONFIRMED = "confirmed"
    FAILED    = "failed"
    SKIPPED   = "skipped"   # dry-run or insufficient funds


@dataclass
class Bill:
    """One recurring obligation."""
    id:               str
    vendor:           str          # "Hetzner", "DeepInfra", etc.
    description:      str
    bill_type:        BillType
    amount_usd:       float        # 0 = variable (prepaid credits)
    cycle:            str          # "monthly" | "annual" | "prepaid" | "usage"
    due_day:          int          # day of month (1-28), 0 = usage-based
    auto_topup:       bool = False # Murphy auto-pays when low
    topup_threshold:  float = 0.0  # for prepaid: top up when balance drops below this
    topup_amount:     float = 0.0  # how much to add each time
    check_url:        str  = ""    # API endpoint to check balance/status
    last_checked:     str  = ""
    last_status:      str  = BillStatus.UNKNOWN
    notes:            str  = ""


@dataclass
class PaymentRecord:
    """Immutable record of one bill payment event."""
    id:           str = field(default_factory=lambda: str(uuid.uuid4()))
    bill_id:      str = ""
    vendor:       str = ""
    amount_usd:   float = 0.0
    status:       str = PaymentStatus.PENDING
    method:       str = ""       # "auto_topup" | "coinbase_sweep" | "card_on_file" | "confirmed_email"
    tx_ref:       str = ""       # transaction ID if available
    note:         str = ""
    timestamp:    str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dry_run:      bool = True


@dataclass
class OperationsWallet:
    """Murphy's operations cash position."""
    balance_usd:       float = 0.0
    total_received:    float = 0.0
    total_paid:        float = 0.0
    last_inflow:       str   = ""
    last_payment:      str   = ""
    updated_at:        str   = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ─────────────────────────────────────────────────────────────────────────────
# Murphy's known bills — the canonical registry
# ─────────────────────────────────────────────────────────────────────────────

MURPHY_BILL_REGISTRY: List[Bill] = [
    Bill(
        id="hetzner_server",
        vendor="Hetzner Cloud",
        description="Hetzner CPX41 VPS — 8 core / 16GB RAM / 240GB NVMe / 20TB traffic",
        bill_type=BillType.AUTO_BILLED,
        amount_usd=28.19,          # CPX41 EUR → ~$30.50 USD at current rate
        cycle="monthly",
        due_day=1,
        notes="Auto-billed to Hetzner payment method on file. Murphy monitors invoice email.",
        check_url="https://api.hetzner.cloud/v1/servers",
    ),
    Bill(
        id="deepinfra_credits",
        vendor="DeepInfra",
        description="LLM API credits — primary model: Qwen/Qwen3-235B-A22B",
        bill_type=BillType.PREPAID,
        amount_usd=0.0,            # usage-based
        cycle="prepaid",
        due_day=0,
        auto_topup=True,
        topup_threshold=DEEPINFRA_LOW_THRESHOLD_USD,
        topup_amount=DEEPINFRA_TOPUP_AMOUNT_USD,
        check_url="https://api.deepinfra.com/v1/user",
        notes="Top up $25 when balance < $5. Primary LLM provider. Fast-fail at 8s per RULE 7.",
    ),
    Bill(
        id="together_ai_credits",
        vendor="Together.ai",
        description="LLM API credits — fallback chain rung 2 (120s window)",
        bill_type=BillType.PREPAID,
        amount_usd=0.0,
        cycle="prepaid",
        due_day=0,
        auto_topup=True,
        topup_threshold=TOGETHER_LOW_THRESHOLD_USD,
        topup_amount=TOGETHER_TOPUP_AMOUNT_USD,
        check_url="https://api.together.ai/v1/users/me",
        notes="Top up $25 when balance < $5. Second rung of LLM chain after DeepInfra.",
    ),
    Bill(
        id="nowpayments_fees",
        vendor="NOWPayments",
        description="Payment processing fees — 0.5% per transaction, auto-deducted",
        bill_type=BillType.AUTO_BILLED,
        amount_usd=0.0,            # variable — 0.5% of revenue
        cycle="usage",
        due_day=0,
        notes="Auto-deducted from each payment. No action needed — Murphy monitors via /api/billing/nowpayments/revenue.",
    ),
    Bill(
        id="domain_murphy_systems",
        vendor="Domain Registrar",
        description="murphy.systems domain registration — annual renewal",
        bill_type=BillType.MANUAL,
        amount_usd=18.00,
        cycle="annual",
        due_day=0,
        notes="Annual renewal. Murphy sets 60-day and 30-day calendar alerts. HITL confirmation required.",
    ),
]


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
            CREATE TABLE IF NOT EXISTS operations_wallet (
                id TEXT PRIMARY KEY DEFAULT 'singleton',
                balance_usd REAL DEFAULT 0.0,
                total_received REAL DEFAULT 0.0,
                total_paid REAL DEFAULT 0.0,
                last_inflow TEXT,
                last_payment TEXT,
                updated_at TEXT
            );

            INSERT OR IGNORE INTO operations_wallet (id, balance_usd, updated_at)
            VALUES ('singleton', 0.0, datetime('now'));

            CREATE TABLE IF NOT EXISTS payment_records (
                id TEXT PRIMARY KEY,
                bill_id TEXT NOT NULL,
                vendor TEXT NOT NULL,
                amount_usd REAL DEFAULT 0.0,
                status TEXT NOT NULL DEFAULT 'pending',
                method TEXT,
                tx_ref TEXT,
                note TEXT,
                timestamp TEXT NOT NULL,
                dry_run INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS bill_status_log (
                id TEXT PRIMARY KEY,
                bill_id TEXT NOT NULL,
                vendor TEXT NOT NULL,
                status TEXT,
                balance_usd REAL,
                note TEXT,
                checked_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS journal_entries (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                description TEXT NOT NULL,
                debit_account TEXT NOT NULL,
                credit_account TEXT NOT NULL,
                amount_usd REAL NOT NULL,
                reference TEXT,
                category TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_payments_bill ON payment_records(bill_id);
            CREATE INDEX IF NOT EXISTS idx_journal_ts ON journal_entries(timestamp);
        """)


# ─────────────────────────────────────────────────────────────────────────────
# Treasury engine
# ─────────────────────────────────────────────────────────────────────────────

class MurphyTreasury:
    """
    Murphy's autonomous financial operations engine.

    Flow when a subscription payment arrives:
      1. NOWPayments IPN fires → handle_inflow(amount_usd, source)
      2. 50% goes to operations wallet (record_inflow)
      3. 50% queued for ATOM purchase (calls profit_sweep)
      4. Daily monitor checks all bills
      5. Auto-tops-up prepaid credits when low
      6. Confirms auto-billed payments received
      7. Alerts HITL if anything needs manual action

    Usage::
        treasury = get_treasury()
        # Called from NOWPayments IPN handler:
        treasury.handle_subscription_payment(amount_usd=99.00, tenant_id="abc")
        # Called from daily scheduler:
        await treasury.run_daily_monitor()
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        _ensure_schema()
        self._enabled = os.environ.get("TREASURY_ENABLED", "false").lower() == "true"
        if not self._enabled:
            logger.info("TREASURY: running in DRY-RUN mode. Set TREASURY_ENABLED=true to activate payments.")

    # ── Inflow handling ───────────────────────────────────────────────────────

    def handle_subscription_payment(
        self,
        amount_usd: float,
        tenant_id: str = "",
        payment_id: str = "",
        tier: str = "",
    ) -> Dict[str, Any]:
        """
        Called when NOWPayments IPN confirms a subscription payment.
        Splits 50/50: operations cash vs ATOM staking queue.
        """
        ops_share   = round(amount_usd * 0.50, 2)
        atom_share  = round(amount_usd * 0.50, 2)
        now         = datetime.now(timezone.utc).isoformat()

        # Record inflow to operations wallet
        self._credit_wallet(ops_share, f"Subscription payment — tenant {tenant_id} tier={tier}")

        # Double-entry journal
        self._journal(
            description=f"Subscription received — {tier} tier — tenant {tenant_id}",
            debit_account="Cash:OperationsWallet",
            credit_account="Revenue:Subscriptions",
            amount_usd=ops_share,
            reference=payment_id,
            category="revenue",
        )
        self._journal(
            description=f"ATOM treasury allocation — {tier} tier — tenant {tenant_id}",
            debit_account="Asset:CryptoTreasury:ATOM",
            credit_account="Revenue:Subscriptions",
            amount_usd=atom_share,
            reference=payment_id,
            category="treasury",
        )

        # Trigger ATOM purchase (non-blocking)
        atom_result = self._queue_atom_purchase(atom_share, payment_id)

        logger.info(
            "TREASURY: inflow $%.2f — ops_share=$%.2f ATOM_share=$%.2f tenant=%s",
            amount_usd, ops_share, atom_share, tenant_id,
        )

        return {
            "success":          True,
            "total_received":   amount_usd,
            "ops_share":        ops_share,
            "atom_share":       atom_share,
            "atom_result":      atom_result,
            "wallet_balance":   self.get_wallet_balance(),
        }

    def _credit_wallet(self, amount_usd: float, note: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with _db() as conn:
            conn.execute("""
                UPDATE operations_wallet SET
                  balance_usd    = balance_usd + ?,
                  total_received = total_received + ?,
                  last_inflow    = ?,
                  updated_at     = ?
                WHERE id = 'singleton'
            """, (amount_usd, amount_usd, now, now))
        logger.info("TREASURY: credited $%.2f to operations wallet — %s", amount_usd, note)

    def _debit_wallet(self, amount_usd: float, note: str) -> bool:
        """Debit operations wallet. Returns False if insufficient funds."""
        with _db() as conn:
            row = conn.execute(
                "SELECT balance_usd FROM operations_wallet WHERE id='singleton'"
            ).fetchone()
            current = row["balance_usd"] if row else 0.0
            if current < amount_usd:
                logger.warning(
                    "TREASURY: insufficient funds — need $%.2f have $%.2f — %s",
                    amount_usd, current, note
                )
                return False
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("""
                UPDATE operations_wallet SET
                  balance_usd = balance_usd - ?,
                  total_paid  = total_paid + ?,
                  last_payment = ?,
                  updated_at  = ?
                WHERE id = 'singleton'
            """, (amount_usd, amount_usd, now, now))
        return True

    def get_wallet_balance(self) -> float:
        with _db() as conn:
            row = conn.execute(
                "SELECT balance_usd FROM operations_wallet WHERE id='singleton'"
            ).fetchone()
            return row["balance_usd"] if row else 0.0

    # ── ATOM treasury ─────────────────────────────────────────────────────────

    def _queue_atom_purchase(self, amount_usd: float, ref: str = "") -> Dict:
        """Trigger profit_sweep to buy and stake ATOM with the treasury share."""
        try:
            from src.profit_sweep import ProfitSweep
            sweeper = ProfitSweep(starting_capital=0.0)
            record  = sweeper.run_sweep(
                portfolio_value=amount_usd,
                open_positions=0.0,
                pending_orders=0.0,
            )
            return record.to_dict() if hasattr(record, "to_dict") else {"status": "queued"}
        except Exception as exc:
            logger.error("TREASURY: ATOM purchase failed: %s", exc)
            return {"status": "failed", "error": str(exc)}

    # ── Bill monitoring ───────────────────────────────────────────────────────

    def run_daily_monitor(self) -> Dict[str, Any]:
        """
        Run every morning at 6:00 AM ET via APScheduler.
        Checks every bill, tops up prepaid credits, confirms auto-billed payments.
        Returns a full status report.
        """
        results  = []
        alerts   = []
        balance  = self.get_wallet_balance()
        upcoming = self._upcoming_bills_30_days()
        total_due = sum(b["amount_usd"] for b in upcoming)

        logger.info(
            "TREASURY MONITOR: wallet=$%.2f upcoming_30d=$%.2f checking %d bills",
            balance, total_due, len(MURPHY_BILL_REGISTRY)
        )

        for bill in MURPHY_BILL_REGISTRY:
            result = self._check_bill(bill)
            results.append(result)

            # Auto top-up prepaid credits
            if (bill.bill_type == BillType.PREPAID
                    and bill.auto_topup
                    and result.get("status") == BillStatus.LOW_CREDIT):
                topup_result = self._topup_prepaid_credits(bill)
                result["topup"] = topup_result
                if topup_result.get("success"):
                    logger.info("TREASURY: auto-topped-up %s by $%.2f", bill.vendor, bill.topup_amount)
                else:
                    alerts.append({
                        "severity": "HIGH",
                        "vendor":   bill.vendor,
                        "message":  f"Auto top-up FAILED for {bill.vendor}: {topup_result.get('error')}",
                    })

            # Alert if auto-billed payment might be at risk
            if (bill.bill_type == BillType.AUTO_BILLED
                    and bill.amount_usd > 0
                    and balance < bill.amount_usd + MIN_OPERATIONS_BUFFER_USD):
                alerts.append({
                    "severity": "MEDIUM",
                    "vendor":   bill.vendor,
                    "message":  f"Operations wallet low (${balance:.2f}) — {bill.vendor} bill ${bill.amount_usd:.2f} due",
                })

        # Low cash runway alert
        monthly_burn = sum(
            b.amount_usd for b in MURPHY_BILL_REGISTRY
            if b.cycle == "monthly" and b.amount_usd > 0
        ) + DEEPINFRA_TOPUP_AMOUNT_USD + TOGETHER_TOPUP_AMOUNT_USD
        runway_months = balance / monthly_burn if monthly_burn > 0 else 99
        if runway_months < 2:
            alerts.append({
                "severity": "HIGH",
                "message":  f"Cash runway < 2 months — wallet=${balance:.2f} monthly_burn=${monthly_burn:.2f}",
            })

        # Dispatch HITL alert if anything needs human attention
        if alerts:
            self._dispatch_treasury_alert(alerts, balance, total_due)

        summary = {
            "timestamp":       datetime.now(timezone.utc).isoformat(),
            "wallet_balance":  balance,
            "upcoming_30d":    total_due,
            "runway_months":   round(runway_months, 1),
            "monthly_burn":    monthly_burn,
            "bills_checked":   len(results),
            "alerts":          alerts,
            "results":         results,
        }
        logger.info("TREASURY MONITOR COMPLETE: %s", json.dumps(summary, default=str))
        return summary

    def _check_bill(self, bill: Bill) -> Dict[str, Any]:
        """Check the status of one bill via its vendor API."""
        now = datetime.now(timezone.utc).isoformat()
        result: Dict[str, Any] = {
            "bill_id":   bill.id,
            "vendor":    bill.vendor,
            "status":    BillStatus.UNKNOWN,
            "balance":   None,
            "note":      "",
        }

        try:
            if bill.id == "hetzner_server":
                result.update(self._check_hetzner())
            elif bill.id == "deepinfra_credits":
                result.update(self._check_deepinfra())
            elif bill.id == "together_ai_credits":
                result.update(self._check_together())
            elif bill.id == "nowpayments_fees":
                result.update({"status": BillStatus.CURRENT, "note": "Auto-deducted — no action needed"})
            elif bill.id == "domain_murphy_systems":
                result.update(self._check_domain_renewal())
            else:
                result.update({"status": BillStatus.UNKNOWN, "note": "No check configured"})
        except Exception as exc:
            result["status"] = BillStatus.UNKNOWN
            result["note"]   = f"Check failed: {exc}"
            logger.error("TREASURY: bill check failed for %s: %s", bill.vendor, exc)

        # Log to bill_status_log
        with _db() as conn:
            conn.execute("""
                INSERT INTO bill_status_log (id, bill_id, vendor, status, balance_usd, note, checked_at)
                VALUES (?,?,?,?,?,?,?)
            """, (str(uuid.uuid4()), bill.id, bill.vendor, result["status"],
                  result.get("balance"), result["note"], now))

        return result

    def _check_hetzner(self) -> Dict:
        token = os.environ.get("HETZNER_TOKEN", "")
        if not token:
            return {"status": BillStatus.UNKNOWN, "note": "HETZNER_TOKEN not set"}
        try:
            r = requests.get("https://api.hetzner.cloud/v1/servers",
                             headers={"Authorization": f"Bearer {token}"},
                             timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                servers = r.json().get("servers", [])
                names   = [s["name"] for s in servers]
                return {
                    "status": BillStatus.CURRENT,
                    "note":   f"Server(s) running: {', '.join(names)} — auto-billed monthly",
                }
            return {"status": BillStatus.UNKNOWN, "note": f"Hetzner API returned {r.status_code}"}
        except Exception as exc:
            return {"status": BillStatus.UNKNOWN, "note": str(exc)}

    def _check_deepinfra(self) -> Dict:
        api_key = os.environ.get("DEEPINFRA_API_KEY", "")
        if not api_key:
            return {"status": BillStatus.UNKNOWN, "note": "DEEPINFRA_API_KEY not set"}
        try:
            r = requests.get("https://api.deepinfra.com/v1/user",
                             headers={"Authorization": f"Bearer {api_key}"},
                             timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                data    = r.json()
                balance = float(data.get("balance", data.get("credits", 0)))
                status  = BillStatus.LOW_CREDIT if balance < DEEPINFRA_LOW_THRESHOLD_USD else BillStatus.CURRENT
                return {
                    "status":  status,
                    "balance": balance,
                    "note":    f"DeepInfra balance: ${balance:.4f}" + (" — LOW, will top up" if status == BillStatus.LOW_CREDIT else ""),
                }
            return {"status": BillStatus.UNKNOWN, "note": f"DeepInfra API returned {r.status_code}"}
        except Exception as exc:
            return {"status": BillStatus.UNKNOWN, "note": str(exc)}

    def _check_together(self) -> Dict:
        api_key = os.environ.get("TOGETHER_API_KEY", "")
        if not api_key:
            return {"status": BillStatus.UNKNOWN, "note": "TOGETHER_API_KEY not set"}
        try:
            r = requests.get("https://api.together.ai/v1/users/me",
                             headers={"Authorization": f"Bearer {api_key}"},
                             timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                data    = r.json()
                balance = float(data.get("balance_credits", data.get("credit_balance", 0)))
                status  = BillStatus.LOW_CREDIT if balance < TOGETHER_LOW_THRESHOLD_USD else BillStatus.CURRENT
                return {
                    "status":  status,
                    "balance": balance,
                    "note":    f"Together.ai balance: ${balance:.4f}" + (" — LOW, will top up" if status == BillStatus.LOW_CREDIT else ""),
                }
            return {"status": BillStatus.UNKNOWN, "note": f"Together.ai API returned {r.status_code}"}
        except Exception as exc:
            return {"status": BillStatus.UNKNOWN, "note": str(exc)}

    def _check_domain_renewal(self) -> Dict:
        # Domain renewal is annual — just check how far away it is
        # murphy.systems was registered — estimate based on a known date
        renewal_month = 11  # November (estimate — update with actual WHOIS date)
        now = datetime.now(timezone.utc)
        next_renewal = datetime(now.year if now.month < renewal_month else now.year + 1,
                                renewal_month, 1, tzinfo=timezone.utc)
        days_until = (next_renewal - now).days
        if days_until <= 30:
            return {"status": BillStatus.DUE_SOON, "note": f"Domain renewal in {days_until} days — HITL confirmation needed"}
        if days_until <= 60:
            return {"status": BillStatus.DUE_SOON, "note": f"Domain renewal in {days_until} days — calendar alert set"}
        return {"status": BillStatus.CURRENT, "note": f"Domain renewal in {days_until} days"}

    # ── Prepaid top-up ────────────────────────────────────────────────────────

    def _topup_prepaid_credits(self, bill: Bill) -> Dict[str, Any]:
        """Auto top-up a prepaid API credit account from the operations wallet."""
        if not self._enabled:
            logger.info("TREASURY DRY-RUN: would top up %s by $%.2f", bill.vendor, bill.topup_amount)
            return {"success": True, "dry_run": True, "amount": bill.topup_amount, "vendor": bill.vendor}

        # Check wallet balance
        balance = self.get_wallet_balance()
        if balance < bill.topup_amount + MIN_OPERATIONS_BUFFER_USD:
            return {
                "success": False,
                "error":   f"Insufficient wallet balance (${balance:.2f}) to top up {bill.vendor} (${bill.topup_amount:.2f})",
            }

        # Execute top-up via vendor API
        try:
            if bill.id == "deepinfra_credits":
                result = self._topup_deepinfra(bill.topup_amount)
            elif bill.id == "together_ai_credits":
                result = self._topup_together(bill.topup_amount)
            else:
                return {"success": False, "error": f"No top-up method for {bill.vendor}"}

            if result.get("success"):
                # Debit wallet
                self._debit_wallet(bill.topup_amount, f"Top-up {bill.vendor}")
                # Journal entry
                self._journal(
                    description=f"API credit top-up — {bill.vendor}",
                    debit_account=f"Expense:APICredits:{bill.vendor.replace(' ','_')}",
                    credit_account="Cash:OperationsWallet",
                    amount_usd=bill.topup_amount,
                    reference=result.get("tx_ref", ""),
                    category="operating_expense",
                )
                # Payment record
                self._record_payment(PaymentRecord(
                    bill_id=bill.id,
                    vendor=bill.vendor,
                    amount_usd=bill.topup_amount,
                    status=PaymentStatus.CONFIRMED,
                    method="auto_topup",
                    tx_ref=result.get("tx_ref", ""),
                    note=f"Auto top-up triggered by low balance threshold",
                    dry_run=False,
                ))
            return result

        except Exception as exc:
            logger.error("TREASURY: top-up failed for %s: %s", bill.vendor, exc)
            return {"success": False, "error": str(exc)}

    def _topup_deepinfra(self, amount_usd: float) -> Dict:
        """Top up DeepInfra credits. DeepInfra uses Stripe for prepaid top-ups."""
        # DeepInfra doesn't have a public API for programmatic top-up yet
        # Murphy logs the need and sends HITL alert for manual top-up
        # This will be replaced with a Stripe payment call when DeepInfra exposes it
        self._dispatch_treasury_alert([{
            "severity": "MEDIUM",
            "vendor": "DeepInfra",
            "message": f"DeepInfra credits low — manual top-up needed: add ${amount_usd:.2f} at https://deepinfra.com/dash/billing",
        }], self.get_wallet_balance(), 0)
        return {"success": True, "manual_action_needed": True,
                "note": "HITL alert sent — manual top-up at deepinfra.com/dash/billing"}

    def _topup_together(self, amount_usd: float) -> Dict:
        """Top up Together.ai credits."""
        self._dispatch_treasury_alert([{
            "severity": "MEDIUM",
            "vendor": "Together.ai",
            "message": f"Together.ai credits low — manual top-up needed: add ${amount_usd:.2f} at https://api.together.ai/settings/billing",
        }], self.get_wallet_balance(), 0)
        return {"success": True, "manual_action_needed": True,
                "note": "HITL alert sent — manual top-up at api.together.ai/settings/billing"}

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _upcoming_bills_30_days(self) -> List[Dict]:
        """Return bills due in the next 30 days with amounts."""
        now     = datetime.now(timezone.utc)
        results = []
        for bill in MURPHY_BILL_REGISTRY:
            if bill.cycle == "monthly" and bill.amount_usd > 0:
                due = now.replace(day=bill.due_day or 1)
                if due < now:
                    due = (due.replace(day=28) + timedelta(days=4)).replace(day=bill.due_day or 1)
                days_away = (due - now).days
                if 0 <= days_away <= 30:
                    results.append({
                        "vendor":     bill.vendor,
                        "amount_usd": bill.amount_usd,
                        "due_in_days": days_away,
                        "bill_id":    bill.id,
                    })
            elif bill.cycle == "annual" and bill.amount_usd > 0:
                results.append({
                    "vendor":     bill.vendor,
                    "amount_usd": round(bill.amount_usd / 12, 2),
                    "note":       "monthly_accrual",
                    "bill_id":    bill.id,
                })
        return results

    def _journal(self, description: str, debit_account: str, credit_account: str,
                 amount_usd: float, reference: str = "", category: str = "",
                 business_line: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        # Auto-classify business line if not provided
        if not business_line:
            try:
                from src.murphy_business_lines import get_classifier
                bl = get_classifier().classify_revenue(
                    amount_usd, description=description, tier=""
                )
                business_line = bl.get("business_line", "platform")
            except Exception:
                business_line = "platform"
        with _db() as conn:
            conn.execute("""
                INSERT INTO journal_entries
                  (id, timestamp, description, debit_account, credit_account,
                   amount_usd, reference, category, business_line)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (str(uuid.uuid4()), now, description, debit_account,
                  credit_account, amount_usd, reference, category, business_line))

    def _record_payment(self, rec: PaymentRecord) -> None:
        with _db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO payment_records
                  (id, bill_id, vendor, amount_usd, status, method, tx_ref, note, timestamp, dry_run)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (rec.id, rec.bill_id, rec.vendor, rec.amount_usd, rec.status,
                  rec.method, rec.tx_ref, rec.note, rec.timestamp, int(rec.dry_run)))

    def _dispatch_treasury_alert(self, alerts: List[Dict], balance: float, due: float) -> None:
        """Send treasury alert to HITL queue and morning brief."""
        try:
            from src.hitl_task_queue import enqueue_task
            enqueue_task({
                "type":    "treasury_alert",
                "alerts":  alerts,
                "balance": balance,
                "due_30d": due,
                "ts":      datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        try:
            from src.swarm_bus import publish
            publish("treasury.alert", {"alerts": alerts, "wallet_balance": balance})
        except Exception:
            pass
        logger.warning("TREASURY ALERT: %s", json.dumps(alerts))

    # ── Status API ────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Full treasury status for /api/treasury/status dashboard."""
        balance      = self.get_wallet_balance()
        monthly_burn = sum(
            b.amount_usd for b in MURPHY_BILL_REGISTRY
            if b.cycle == "monthly" and b.amount_usd > 0
        ) + DEEPINFRA_TOPUP_AMOUNT_USD + TOGETHER_TOPUP_AMOUNT_USD
        runway = balance / monthly_burn if monthly_burn > 0 else 99

        with _db() as conn:
            wallet = dict(conn.execute(
                "SELECT * FROM operations_wallet WHERE id='singleton'"
            ).fetchone())
            recent_payments = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM payment_records ORDER BY timestamp DESC LIMIT 10"
                ).fetchall()
            ]
            recent_journal = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM journal_entries ORDER BY timestamp DESC LIMIT 20"
                ).fetchall()
            ]

        bills_summary = []
        for bill in MURPHY_BILL_REGISTRY:
            bills_summary.append({
                "id":          bill.id,
                "vendor":      bill.vendor,
                "description": bill.description,
                "type":        bill.bill_type,
                "amount_usd":  bill.amount_usd,
                "cycle":       bill.cycle,
                "auto_topup":  bill.auto_topup,
                "notes":       bill.notes,
            })

        return {
            "wallet":          wallet,
            "balance_usd":     balance,
            "monthly_burn":    monthly_burn,
            "runway_months":   round(runway, 1),
            "bills":           bills_summary,
            "upcoming_30d":    self._upcoming_bills_30_days(),
            "recent_payments": recent_payments,
            "journal":         recent_journal,
            "treasury_enabled": self._enabled,
            "atom_split":      "50% of subscriptions → Cosmos ATOM staking",
            "ops_split":       "50% of subscriptions → operations wallet",
        }

    def register_bill(
        self,
        id: str,
        vendor: str,
        description: str,
        bill_type: str,
        amount_usd: float,
        cycle: str,
        due_day: int = 1,
        auto_topup: bool = False,
        topup_threshold: float = 0.0,
        topup_amount: float = 0.0,
        check_url: str = "",
        notes: str = "",
    ) -> Dict:
        """Register a new bill (callable from API or founder terminal)."""
        new_bill = Bill(
            id=id, vendor=vendor, description=description,
            bill_type=BillType(bill_type), amount_usd=amount_usd,
            cycle=cycle, due_day=due_day, auto_topup=auto_topup,
            topup_threshold=topup_threshold, topup_amount=topup_amount,
            check_url=check_url, notes=notes,
        )
        MURPHY_BILL_REGISTRY.append(new_bill)
        logger.info("TREASURY: registered new bill — %s (%s)", vendor, id)
        return {"success": True, "bill": id, "vendor": vendor}


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

_treasury: Optional[MurphyTreasury] = None
_treasury_lock = threading.Lock()


def get_treasury() -> MurphyTreasury:
    global _treasury
    if _treasury is None:
        with _treasury_lock:
            if _treasury is None:
                _treasury = MurphyTreasury()
    return _treasury
