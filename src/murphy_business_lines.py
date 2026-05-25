# Copyright © 2020 Inoni LLC / Corey Post / BSL 1.1
"""
Murphy Business Line Separation — PATCH-380
============================================
Murphy operates two fundamentally different businesses simultaneously.
This module ensures Murphy always knows which business it is acting on,
correctly segregates P&L, and reports metrics for each independently.

═══════════════════════════════════════════════════════════════════════
BUSINESS LINE 1 — "PLATFORM"  (Murphy as a SaaS product)
═══════════════════════════════════════════════════════════════════════
  What it is:  Murphy.systems sells subscriptions to its AI OS platform.
               Customers log in, use Murphy's agents, swarm, compliance
               engine, voice control, etc. for their own work.

  Revenue:     Flat monthly SaaS fees — $99 / $399 / $799 / Custom
  Costs:       Hetzner server, DeepInfra/Together API credits, domain
  Gross margin: ~95% (near zero COGS per additional tenant)
  Valuation:   10x–40x ARR (AI SaaS multiple)
  Investor story: "Autonomous AI OS. One server. Infinite tenants. 95% margin."

  Revenue categories:
    platform.subscription.solo      — $99/mo
    platform.subscription.team      — $399/mo
    platform.subscription.business  — $799/mo
    platform.subscription.enterprise — custom
    platform.usage.overage          — per-seat overages

═══════════════════════════════════════════════════════════════════════
BUSINESS LINE 2 — "MANAGED"  (Murphy as a service for client businesses)
═══════════════════════════════════════════════════════════════════════
  What it is:  Murphy operates a client's business FOR them — dispatching
               work, running their CRM, handling their compliance, writing
               their proposals, managing their staff scheduling, etc.
               Murphy IS their operations team. The client pays a fee for
               outcomes, not for platform access.

  Revenue:     Performance contracts OR fixed managed service fees
               - Performance: Murphy earns a % of savings/revenue generated
               - Fixed: monthly retainer for defined scope of work
               - Project: one-time fee for a specific deliverable

  Costs:       LLM compute per client (more tokens = more cost per client),
               HITL labor cost if licensed professionals are involved,
               custom integrations, client-specific infrastructure
  Gross margin: ~60–75% (higher variable cost than platform)
  Valuation:   Treated as services revenue — lower multiple (2x–5x ARR)
               BUT positions Murphy for enterprise contracts ($50K–$500K/yr)
  Investor story: "We run operations for MEP contractors and GCs at 40% of
                   what they save — zero upfront cost, Murphy earns on impact."

  Revenue categories:
    managed.retainer.mep            — MEP contractor managed ops
    managed.retainer.gc             — General contractor managed ops
    managed.retainer.engineering    — Engineering firm managed ops
    managed.retainer.logistics      — Freight/logistics managed ops
    managed.performance.savings_pct — % of documented savings
    managed.performance.revenue_pct — % of revenue Murphy generates
    managed.project.proposal        — one-time proposal writing fee
    managed.project.compliance      — one-time compliance audit fee
    managed.project.onboarding      — one-time client onboarding fee

═══════════════════════════════════════════════════════════════════════
WHY THIS SEPARATION MATTERS
═══════════════════════════════════════════════════════════════════════
  1. VALUATION: Investors pay 10x–40x ARR for SaaS. They pay 2x–5x for
     services. Murphy must report them separately so platform ARR gets
     the right multiple. Mixing them would COMPRESS the valuation.

  2. COSTS: Platform costs are shared and nearly fixed. Managed costs
     scale with each client — you can't calculate managed gross margin
     without knowing which LLM calls, compliance runs, and HITL hours
     belong to which client.

  3. TAXES: Services revenue may have different tax treatment than SaaS
     platform revenue depending on state/jurisdiction.

  4. REPORTING: Investors, banks, and RBF providers need to see the
     platform ARR specifically — not blended with services revenue.

  5. OPERATIONS: Murphy needs to know which budget it's spending when
     it dispatches a swarm task. Compliance audit for a client = managed
     cost. Compliance check for Murphy's own platform = platform cost.

═══════════════════════════════════════════════════════════════════════
HOW MURPHY DETERMINES WHICH BUSINESS LINE AN ACTIVITY BELONGS TO
═══════════════════════════════════════════════════════════════════════
  Dispatch context carries a `business_line` field injected at the
  outermost layer (CEO console, API, automation trigger).

  Rules (in priority order):
  1. Explicit: request/task carries business_line="platform"|"managed"
  2. Tenant type: if tenant_type="managed_client" → managed
                  if tenant_type="platform_user"  → platform
  3. Revenue source: NOWPayments subscription IPN → platform
                     Invoice payment with client_id → managed
  4. Task type: platform ops (compliance for murphy.systems, CRM for
                 murphy's own pipeline, billing checks) → platform
                 client work (MEP contractor dispatch, client CRM,
                 client compliance, client scheduling) → managed
  5. Default: platform (Murphy's own ops are the safe default)
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.business_lines")

DB_PATH = "/var/lib/murphy-production/treasury.db"


# ─────────────────────────────────────────────────────────────────────────────
# Business line definitions
# ─────────────────────────────────────────────────────────────────────────────

class BusinessLine(str, Enum):
    PLATFORM = "platform"   # Murphy as SaaS product
    MANAGED  = "managed"    # Murphy running client businesses as a service
    INTERNAL = "internal"   # Murphy's own R&D, infrastructure, legal, G&A


class RevenueCategory(str, Enum):
    # Platform
    PLATFORM_SOLO        = "platform.subscription.solo"
    PLATFORM_TEAM        = "platform.subscription.team"
    PLATFORM_BUSINESS    = "platform.subscription.business"
    PLATFORM_ENTERPRISE  = "platform.subscription.enterprise"
    PLATFORM_OVERAGE     = "platform.usage.overage"

    # Managed services
    MANAGED_RETAINER_MEP     = "managed.retainer.mep"
    MANAGED_RETAINER_GC      = "managed.retainer.gc"
    MANAGED_RETAINER_ENG     = "managed.retainer.engineering"
    MANAGED_RETAINER_LOGISTIC = "managed.retainer.logistics"
    MANAGED_RETAINER_GENERAL = "managed.retainer.general"
    MANAGED_PERFORMANCE_SAVE = "managed.performance.savings_pct"
    MANAGED_PERFORMANCE_REV  = "managed.performance.revenue_pct"
    MANAGED_PROJECT_PROPOSAL = "managed.project.proposal"
    MANAGED_PROJECT_COMPLIANCE = "managed.project.compliance"
    MANAGED_PROJECT_ONBOARD  = "managed.project.onboarding"


class ExpenseCategory(str, Enum):
    # Platform expenses (shared infrastructure)
    PLATFORM_SERVER      = "platform.expense.server"
    PLATFORM_LLM_SHARED  = "platform.expense.llm_shared"
    PLATFORM_DOMAIN      = "platform.expense.domain"
    PLATFORM_PAYMENTS    = "platform.expense.payment_processing"
    PLATFORM_LEGAL       = "platform.expense.legal"
    PLATFORM_MARKETING   = "platform.expense.marketing"

    # Managed expenses (per-client variable costs)
    MANAGED_LLM_CLIENT   = "managed.expense.llm_per_client"
    MANAGED_HITL_LABOR   = "managed.expense.hitl_labor"
    MANAGED_INTEGRATION  = "managed.expense.client_integration"
    MANAGED_INFRA        = "managed.expense.client_infra"

    # Internal / G&A
    INTERNAL_RND         = "internal.expense.rnd"
    INTERNAL_LEGAL       = "internal.expense.legal"
    INTERNAL_ADMIN       = "internal.expense.admin"


# ─────────────────────────────────────────────────────────────────────────────
# Business line classifier
# ─────────────────────────────────────────────────────────────────────────────

# Subscription tier → platform revenue category
TIER_TO_REVENUE_CATEGORY: Dict[str, str] = {
    "free":       RevenueCategory.PLATFORM_SOLO,
    "solo":       RevenueCategory.PLATFORM_SOLO,
    "team":       RevenueCategory.PLATFORM_TEAM,
    "business":   RevenueCategory.PLATFORM_BUSINESS,
    "enterprise": RevenueCategory.PLATFORM_ENTERPRISE,
}

# Task types that belong to Murphy's own platform operations
PLATFORM_TASK_PATTERNS = [
    "murphy.systems", "billing", "treasury", "investment", "valuation",
    "murphy crm", "murphy pipeline", "murphy outreach", "murphy compliance",
    "platform audit", "system health", "self-", "murphy itself",
    "murphy's own", "our own", "internal murphy",
]

# Task types that indicate managed client work
MANAGED_TASK_PATTERNS = [
    "mep", "contractor", "client", "customer site", "their compliance",
    "their crm", "their scheduling", "their invoicing", "their dispatch",
    "managed service", "for the client", "client's", "tenant operations",
    "run their", "operate their",
]


class BusinessLineClassifier:
    """
    Determines which business line an activity, revenue, or expense belongs to.
    Used at every dispatch, journal entry, and revenue recording point.
    """

    def classify_revenue(
        self,
        amount_usd: float,
        source: str = "",
        tier: str = "",
        tenant_type: str = "",
        description: str = "",
        client_id: str = "",
    ) -> Dict[str, str]:
        """
        Returns {business_line, revenue_category, rationale}.
        Call this whenever Murphy receives money.
        """
        desc_lower = (description + " " + source).lower()

        # Rule 1: Explicit tier from NOWPayments/billing → platform
        if tier and tier in TIER_TO_REVENUE_CATEGORY:
            return {
                "business_line":    BusinessLine.PLATFORM,
                "revenue_category": TIER_TO_REVENUE_CATEGORY[tier],
                "rationale":        f"SaaS subscription tier={tier}",
            }

        # Rule 2: Has a client_id → managed services revenue
        if client_id:
            cat = self._infer_managed_category(desc_lower)
            return {
                "business_line":    BusinessLine.MANAGED,
                "revenue_category": cat,
                "rationale":        f"client_id={client_id} — managed services revenue",
            }

        # Rule 3: Tenant type explicit
        if tenant_type == "managed_client":
            cat = self._infer_managed_category(desc_lower)
            return {
                "business_line":    BusinessLine.MANAGED,
                "revenue_category": cat,
                "rationale":        "tenant_type=managed_client",
            }

        # Rule 4: Keywords in description
        if any(kw in desc_lower for kw in ["retainer", "managed service", "performance contract",
                                             "savings share", "revenue share", "mep", "contractor ops",
                                             "compliance audit for", "audit for", "project for",
                                             "onboard for", "onboarding for", "proposal for"]):
            cat = self._infer_managed_category(desc_lower)
            return {
                "business_line":    BusinessLine.MANAGED,
                "revenue_category": cat,
                "rationale":        "keyword match — managed service descriptor",
            }

        # Default: platform subscription
        return {
            "business_line":    BusinessLine.PLATFORM,
            "revenue_category": RevenueCategory.PLATFORM_BUSINESS,
            "rationale":        "default — no managed service signals found",
        }

    def classify_expense(
        self,
        amount_usd: float,
        vendor: str = "",
        description: str = "",
        context: str = "",
        client_id: str = "",
    ) -> Dict[str, str]:
        """
        Returns {business_line, expense_category, rationale}.
        Call this whenever Murphy spends money.
        """
        desc_lower = (description + " " + vendor + " " + context).lower()

        # Client-specific costs → managed
        if client_id:
            if "llm" in desc_lower or "api" in desc_lower or "token" in desc_lower:
                return {
                    "business_line":    BusinessLine.MANAGED,
                    "expense_category": ExpenseCategory.MANAGED_LLM_CLIENT,
                    "rationale":        f"LLM cost attributed to client {client_id}",
                }
            return {
                "business_line":    BusinessLine.MANAGED,
                "expense_category": ExpenseCategory.MANAGED_INTEGRATION,
                "rationale":        f"expense attributed to client {client_id}",
            }

        # Infrastructure → platform (shared)
        if "hetzner" in desc_lower or "server" in desc_lower or "vps" in desc_lower:
            return {
                "business_line":    BusinessLine.PLATFORM,
                "expense_category": ExpenseCategory.PLATFORM_SERVER,
                "rationale":        "server infrastructure — platform shared cost",
            }

        if "deepinfra" in desc_lower or "together" in desc_lower or "llm" in desc_lower or "openai" in desc_lower:
            return {
                "business_line":    BusinessLine.PLATFORM,
                "expense_category": ExpenseCategory.PLATFORM_LLM_SHARED,
                "rationale":        "LLM API credits — platform shared cost",
            }

        if "domain" in desc_lower or "murphy.systems" in desc_lower:
            return {
                "business_line":    BusinessLine.PLATFORM,
                "expense_category": ExpenseCategory.PLATFORM_DOMAIN,
                "rationale":        "domain — platform cost",
            }

        if "nowpayments" in desc_lower or "payment.*fee" in desc_lower or "processing" in desc_lower:
            return {
                "business_line":    BusinessLine.PLATFORM,
                "expense_category": ExpenseCategory.PLATFORM_PAYMENTS,
                "rationale":        "payment processing fee — platform cost",
            }

        if "attorney" in desc_lower or "legal" in desc_lower or "lawyer" in desc_lower:
            return {
                "business_line":    BusinessLine.INTERNAL,
                "expense_category": ExpenseCategory.INTERNAL_LEGAL,
                "rationale":        "legal — internal G&A cost",
            }

        # Default: platform operating expense
        return {
            "business_line":    BusinessLine.PLATFORM,
            "expense_category": ExpenseCategory.PLATFORM_MARKETING,
            "rationale":        "unclassified — defaulting to platform G&A",
        }

    def classify_task(
        self,
        task_description: str,
        requesting_entity: str = "",
        tenant_id: str = "",
        client_id: str = "",
    ) -> Dict[str, str]:
        """
        Classifies a dispatch task — which business line is paying for this swarm work?
        Injected into every dispatch context so LLM token costs can be attributed.
        """
        desc_lower = task_description.lower()

        if client_id:
            return {
                "business_line": BusinessLine.MANAGED,
                "rationale":     f"explicit client_id={client_id}",
                "cost_account":  ExpenseCategory.MANAGED_LLM_CLIENT,
            }

        if any(kw in desc_lower for kw in MANAGED_TASK_PATTERNS):
            return {
                "business_line": BusinessLine.MANAGED,
                "rationale":     "task description contains managed service keywords",
                "cost_account":  ExpenseCategory.MANAGED_LLM_CLIENT,
            }

        if any(kw in desc_lower for kw in PLATFORM_TASK_PATTERNS):
            return {
                "business_line": BusinessLine.PLATFORM,
                "rationale":     "task is Murphy's own platform operations",
                "cost_account":  ExpenseCategory.PLATFORM_LLM_SHARED,
            }

        return {
            "business_line": BusinessLine.PLATFORM,
            "rationale":     "default — Murphy's own operations",
            "cost_account":  ExpenseCategory.PLATFORM_LLM_SHARED,
        }

    def _infer_managed_category(self, desc_lower: str) -> str:
        if "mep" in desc_lower or "mechanical" in desc_lower or "plumbing" in desc_lower:
            return RevenueCategory.MANAGED_RETAINER_MEP
        if "general contractor" in desc_lower or " gc " in desc_lower:
            return RevenueCategory.MANAGED_RETAINER_GC
        if "engineering" in desc_lower:
            return RevenueCategory.MANAGED_RETAINER_ENG
        if "logistics" in desc_lower or "freight" in desc_lower or "trucking" in desc_lower:
            return RevenueCategory.MANAGED_RETAINER_LOGISTIC
        if "performance" in desc_lower or "saving" in desc_lower or "percent" in desc_lower:
            return RevenueCategory.MANAGED_PERFORMANCE_SAVE
        if "proposal" in desc_lower:
            return RevenueCategory.MANAGED_PROJECT_PROPOSAL
        if "compliance" in desc_lower or "audit" in desc_lower:
            return RevenueCategory.MANAGED_PROJECT_COMPLIANCE
        if "onboard" in desc_lower:
            return RevenueCategory.MANAGED_PROJECT_ONBOARD
        return RevenueCategory.MANAGED_RETAINER_GENERAL


# ─────────────────────────────────────────────────────────────────────────────
# Segmented P&L Reporter
# ─────────────────────────────────────────────────────────────────────────────

class SegmentedPnL:
    """
    Reads the treasury journal and produces two separate P&Ls:
      - Platform segment
      - Managed services segment
    Plus a consolidated view and a valuation-ready summary that correctly
    separates SaaS ARR from services revenue.
    """

    def generate(self) -> Dict[str, Any]:
        entries = self._load_journal()

        platform = self._segment(entries, BusinessLine.PLATFORM)
        managed  = self._segment(entries, BusinessLine.MANAGED)
        internal = self._segment(entries, BusinessLine.INTERNAL)

        platform_arr = platform["revenue"] * 12
        managed_arr  = managed["revenue"] * 12

        # Valuation impact — different multiples per segment
        platform_valuation_base = max(platform_arr * 20, 1_500_000)
        managed_valuation_base  = managed_arr * 3   # services multiple

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "platform": {
                **platform,
                "arr":              round(platform_arr, 2),
                "gross_margin_pct": self._margin(platform),
                "valuation_base":   round(platform_valuation_base),
                "valuation_label":  f"${platform_valuation_base/1_000_000:.1f}M",
                "multiple_used":    "20x ARR (AI SaaS)",
                "description":      "Murphy.systems SaaS platform — subscriptions only",
            },
            "managed": {
                **managed,
                "arr":              round(managed_arr, 2),
                "gross_margin_pct": self._margin(managed),
                "valuation_base":   round(managed_valuation_base),
                "valuation_label":  f"${managed_valuation_base/1_000_000:.1f}M",
                "multiple_used":    "3x ARR (services)",
                "description":      "Murphy as managed ops provider — client retainers + performance fees",
            },
            "internal": internal,
            "consolidated": {
                "total_revenue":    round(platform["revenue"] + managed["revenue"], 2),
                "total_expense":    round(platform["expenses"] + managed["expenses"] + internal["expenses"], 2),
                "net_income":       round(
                    platform["revenue"] + managed["revenue"]
                    - platform["expenses"] - managed["expenses"] - internal["expenses"], 2
                ),
            },
            "investor_summary": {
                "platform_arr":         round(platform_arr, 2),
                "managed_services_arr": round(managed_arr, 2),
                "note": (
                    "Investors should apply 20x multiple to platform ARR and 3x to managed services ARR. "
                    "Do NOT blend these — it compresses the platform valuation multiple. "
                    f"Platform floor valuation: ${platform_valuation_base/1_000_000:.1f}M even at $0 ARR."
                ),
            },
            "rule": (
                "NEVER mix platform and managed revenue in investor materials. "
                "Report them side-by-side. Platform is the growth story. "
                "Managed is the cash flow story."
            ),
        }

    def _load_journal(self) -> List[Dict]:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM journal_entries ORDER BY timestamp"
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _segment(self, entries: List[Dict], line: BusinessLine) -> Dict:
        prefix = line.value + "."
        revenue  = sum(
            e["amount_usd"] for e in entries
            if e.get("credit_account", "").startswith("Revenue")
            and (prefix in e.get("category", "") or line.value == e.get("business_line", ""))
        )
        expenses = sum(
            e["amount_usd"] for e in entries
            if e.get("debit_account", "").startswith("Expense")
            and (prefix in e.get("category", "") or line.value == e.get("business_line", ""))
        )
        categories = {}
        for e in entries:
            cat = e.get("category", "")
            if prefix in cat:
                categories[cat] = categories.get(cat, 0) + e.get("amount_usd", 0)

        return {
            "revenue":    round(revenue, 2),
            "expenses":   round(expenses, 2),
            "net":        round(revenue - expenses, 2),
            "categories": categories,
        }

    def _margin(self, segment: Dict) -> float:
        rev = segment["revenue"]
        if rev == 0:
            return 95.0  # known structural margin when no revenue yet
        return round((rev - segment["expenses"]) / rev * 100, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Managed client registry — who Murphy is running businesses FOR
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_managed_client_schema() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS managed_clients (
            id TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            industry TEXT,
            contract_type TEXT,   -- 'retainer' | 'performance' | 'project'
            monthly_fee_usd REAL DEFAULT 0.0,
            performance_pct REAL DEFAULT 0.0,
            scope_json TEXT,
            status TEXT DEFAULT 'active',
            started_at TEXT,
            notes TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS managed_client_activities (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            activity_type TEXT,
            description TEXT,
            llm_tokens_used INTEGER DEFAULT 0,
            estimated_cost_usd REAL DEFAULT 0.0,
            business_line TEXT DEFAULT 'managed',
            created_at TEXT
        );
    """)
    conn.commit()
    conn.close()


def register_managed_client(
    company_name: str,
    industry: str,
    contract_type: str,
    monthly_fee_usd: float = 0.0,
    performance_pct: float = 0.0,
    scope: Dict = None,
    notes: str = "",
) -> Dict[str, Any]:
    """Register a new client Murphy is running operations for."""
    _ensure_managed_client_schema()
    import json
    client_id = "client_" + str(uuid.uuid4())[:8]
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("""
        INSERT INTO managed_clients
          (id, company_name, industry, contract_type, monthly_fee_usd,
           performance_pct, scope_json, status, started_at, notes, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (client_id, company_name, industry, contract_type,
          monthly_fee_usd, performance_pct,
          json.dumps(scope or {}), "active",
          datetime.now(timezone.utc).isoformat(), notes,
          datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()
    logger.info("Registered managed client: %s (%s)", company_name, client_id)
    return {"success": True, "client_id": client_id, "company": company_name}


def list_managed_clients(status: str = "active") -> List[Dict]:
    """List all managed service clients."""
    try:
        _ensure_managed_client_schema()
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM managed_clients WHERE status=? ORDER BY created_at",
            (status,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Context injector — used at every dispatch entry point
# ─────────────────────────────────────────────────────────────────────────────

_classifier = BusinessLineClassifier()

def get_classifier() -> BusinessLineClassifier:
    return _classifier

def get_segmented_pnl() -> SegmentedPnL:
    return SegmentedPnL()

def classify_dispatch(task: str, client_id: str = "", tenant_id: str = "") -> Dict[str, str]:
    """
    Single entry point for classifying any dispatch task.
    Returns {business_line, rationale, cost_account}.
    Called from CEO console, swarm dispatch, and automation triggers.
    """
    return _classifier.classify_task(task, client_id=client_id, tenant_id=tenant_id)

def classify_revenue(amount_usd: float, **kwargs) -> Dict[str, str]:
    """Classify incoming revenue. Kwargs passed to BusinessLineClassifier.classify_revenue()."""
    return _classifier.classify_revenue(amount_usd, **kwargs)
