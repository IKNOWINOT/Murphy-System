# Copyright © 2020 Inoni LLC / Corey Post / BSL 1.1
"""
Murphy Tenant Intelligence Engine — PATCH-381
==============================================
Governs the critical separation between:
  1. WHO can affect WHAT in the Murphy system
  2. WHAT Murphy knows about each user's actual business
  3. HOW Murphy generates strategies scaled to the user's real budget

═══════════════════════════════════════════════════════════════════════
PART 1 — AUTHORITY SCOPE
═══════════════════════════════════════════════════════════════════════

  FOUNDER (cpost@murphy.systems, role=owner):
    → Changes affect the entire Murphy platform system
    → Can modify: agent souls, pricing, global config, all tenants,
                  system-wide capabilities, Murphy's own business ops
    → Every founder command is tagged: scope="platform"

  USER (any subscribed tenant):
    → Changes affect ONLY their own tenant context
    → Can modify: their own CRM, their own agent config, their own
                  schedule, their own compliance settings, their own
                  business strategy, their own integrations
    → Every user command is tagged: scope="tenant:{tenant_id}"
    → Cannot: change pricing, modify other tenants, alter system
              agents, affect Murphy's own operations

  This scope is injected at the outermost dispatch layer so every
  downstream agent, gate, and journal entry carries it.

═══════════════════════════════════════════════════════════════════════
PART 2 — TENANT BUSINESS PROFILE
═══════════════════════════════════════════════════════════════════════

  The single most important thing we learn during onboarding.
  Without this, Murphy can't generate a real strategy.

  Required fields:
    business_stage    — "idea" | "pre_revenue" | "early" | "existing" | "scaling"
    industry          — freeform + mapped to NAICS
    monthly_budget    — how much can they actually spend per month on growth
    current_mrr       — $0 for startups
    biggest_problem   — their #1 pain point in plain language
    time_available    — hours/week the owner can dedicate (affects strategy type)
    existing_tools    — what they already use (avoid redundant recommendations)
    primary_goal      — "get first customer" | "grow revenue" | "cut costs" |
                        "hire" | "comply" | "automate" | "exit"

═══════════════════════════════════════════════════════════════════════
PART 3 — BUDGET-SCALED STRATEGY ENGINE
═══════════════════════════════════════════════════════════════════════

  Murphy generates a 90-day action plan tailored to EXACTLY what the
  user can actually do — time, money, and current business state.

  Four strategy archetypes by available monthly budget:

  ZERO_BUDGET ($0/mo extra beyond Murphy subscription):
    → Zero cash outlay strategies only
    → Leverage: free tiers, sweat equity, time, Murphy's automation
    → Examples: organic content, free lead gen, barter partnerships,
                government grants Murphy identifies and applies for,
                optimizing existing revenue before finding new
    → Murphy runs: CRM, follow-up sequences, proposal writing,
                   scheduling, compliance — all included in subscription

  SEED_BUDGET ($1–$500/mo):
    → Small paid amplification on top of free strategies
    → Examples: $50 Google Ads test, $100 LinkedIn outreach tool,
                basic Canva Pro for branded materials
    → Murphy recommends highest-ROI spend for the budget
    → Still maximizes free/sweat strategies

  GROWTH_BUDGET ($500–$2,500/mo):
    → Real paid acquisition channels
    → Examples: content marketing, SEO tools, paid ads, contractor help
    → Murphy manages campaigns, tracks ROI per dollar spent
    → Can begin hiring decisions (Murphy drafts JDs, screens)

  SCALE_BUDGET ($2,500+/mo):
    → Full growth stack — paid, earned, owned channels running in parallel
    → Murphy manages the whole thing: ads, sales, operations, HR, finance
    → Investment/funding strategies become viable at this level

  All strategy tracks share one constant:
    Murphy does the WORK. The user brings the budget and makes
    decisions Murphy flags for HITL review.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.tenant_engine")

DB_PATH = "/var/lib/murphy-production/tenants.db"

# ─────────────────────────────────────────────────────────────────────────────
# Authority scopes
# ─────────────────────────────────────────────────────────────────────────────

FOUNDER_EMAIL    = "cpost@murphy.systems"
FOUNDER_ROLES    = {"owner", "admin", "founder"}

class DispatchScope(str, Enum):
    PLATFORM = "platform"   # affects whole Murphy system — founder only
    TENANT   = "tenant"     # affects only the requesting user's context


def _tenant_has_addon(account_id: str, addon: str) -> bool:
    """Check if a tenant has purchased a specific add-on feature."""
    try:
        import sqlite3 as _sq
        conn = _sq.connect("/var/lib/murphy-production/billing.db", timeout=3)
        row = conn.execute(
            "SELECT 1 FROM tenant_addons WHERE tenant_id=? AND addon=? AND active=1",
            (account_id, addon)
        ).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def resolve_dispatch_scope(
    account_id: str, role: str, email: str,
    check_addons: bool = True
) -> Dict[str, Any]:
    """
    Called at every dispatch entry point.
    Returns {scope, tenant_id, can_affect_platform, restrictions, addons}.

    Founder (cpost@murphy.systems): platform scope — free.
    User with system_influence add-on ($50/mo): platform scope — paid.
    Standard user: tenant scope only.
    """
    is_founder = (
        email == FOUNDER_EMAIL
        or role in FOUNDER_ROLES
        or account_id == "cpost"
    )

    has_influence_addon = (
        not is_founder
        and check_addons
        and _tenant_has_addon(account_id, "system_influence")
    )

    if is_founder:
        return {
            "scope":               DispatchScope.PLATFORM,
            "tenant_id":           account_id,
            "can_affect_platform": True,
            "restrictions":        [],
            "addons":              ["system_influence"],
            "addon_cost":          "$0 (founder — included free)",
            "note":                "Founder — changes affect entire Murphy platform",
        }
    elif has_influence_addon:
        return {
            "scope":               DispatchScope.PLATFORM,
            "tenant_id":           account_id,
            "can_affect_platform": True,
            "restrictions":        [
                "Cannot access other tenants' data",
                "Cannot modify billing or pricing",
            ],
            "addons":              ["system_influence"],
            "addon_cost":          "$50/mo",
            "note":                f"Tenant with System Influence add-on — platform-wide config access enabled",
        }
    else:
        return {
            "scope":               DispatchScope.TENANT,
            "tenant_id":           account_id,
            "can_affect_platform": False,
            "restrictions": [
                "Cannot modify system-wide agent souls or global config",
                "Cannot change pricing or access other tenants",
                "Cannot affect Murphy's platform operations",
                f"All changes scoped to tenant:{account_id}",
                "Upgrade available: System Influence add-on ($50/mo) unlocks platform config access",
            ],
            "addons":   [],
            "addon_cost": None,
            "note": f"Standard tenant — changes affect only tenant:{account_id}",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Business profile
# ─────────────────────────────────────────────────────────────────────────────

class BusinessStage(str, Enum):
    IDEA        = "idea"          # hasn't started yet, no customers, no revenue
    PRE_REVENUE = "pre_revenue"   # building, no paying customers yet
    EARLY       = "early"         # first 1-10 customers, finding product-market fit
    EXISTING    = "existing"      # established, 10+ customers, predictable revenue
    SCALING     = "scaling"       # actively growing, hiring, expanding


class PrimaryGoal(str, Enum):
    FIRST_CUSTOMER  = "get_first_customer"
    GROW_REVENUE    = "grow_revenue"
    CUT_COSTS       = "cut_costs"
    AUTOMATE          = "automate_operations"
    AUTOMATE_OPERATIONS = "automate_operations"
    HIRE            = "hire_and_scale"
    COMPLY          = "compliance_and_legal"
    RAISE_FUNDING   = "raise_funding"
    EXIT            = "prepare_for_exit"


class BudgetTier(str, Enum):
    ZERO   = "zero"    # $0/mo extra (Murphy sub only)
    SEED   = "seed"    # $1–$500/mo
    GROWTH = "growth"  # $500–$2,500/mo
    SCALE  = "scale"   # $2,500+/mo


def classify_budget(monthly_budget_usd: float) -> BudgetTier:
    if monthly_budget_usd <= 0:
        return BudgetTier.ZERO
    elif monthly_budget_usd <= 500:
        return BudgetTier.SEED
    elif monthly_budget_usd <= 2500:
        return BudgetTier.GROWTH
    else:
        return BudgetTier.SCALE


@dataclass
class TenantBusinessProfile:
    """Everything Murphy needs to run a user's business intelligently."""
    tenant_id:          str
    # Core identity
    business_name:      str = ""
    owner_name:         str = ""
    industry:           str = ""
    location:           str = ""     # city/state/country
    # Business state
    stage:              str = BusinessStage.IDEA
    current_mrr:        float = 0.0  # current monthly revenue
    monthly_budget:     float = 0.0  # extra budget beyond Murphy sub
    budget_tier:        str = BudgetTier.ZERO
    hours_per_week:     int = 10     # how many hours owner can dedicate
    # Goals and problems
    primary_goal:       str = PrimaryGoal.FIRST_CUSTOMER
    biggest_problem:    str = ""     # in their own words
    secondary_goals:    List[str] = field(default_factory=list)
    # Existing setup
    existing_tools:     List[str] = field(default_factory=list)
    existing_employees: int = 0
    existing_customers: int = 0
    # ── User domain knowledge — feeds ALL content, equipment, deliverable generation ──
    # This is what makes Murphy's output actually match the user's professional reality
    owner_profession:       str = ""     # "licensed electrician" | "MEP engineer" | "chef" etc.
    licenses_certs:         List[str] = field(default_factory=list)
                                         # ["Master Electrician License FL", "PE - Mechanical", "ServSafe"]
    years_experience:       int = 0      # years in their trade/profession
    specializations:        List[str] = field(default_factory=list)
                                         # ["commercial HVAC", "tenant improvement", "cold storage"]
    known_codes_standards:  List[str] = field(default_factory=list)
                                         # ["NFPA 70", "ASHRAE 90.1", "IBC 2021", "NEC 2023"]
    preferred_vendors:      List[str] = field(default_factory=list)
                                         # ["Trane", "Lennox", "Ferguson Supply", "Graybar"]
    preferred_brands:       List[str] = field(default_factory=list)
                                         # used in equipment specs and purchasing recommendations
    equipment_familiarity:  List[str] = field(default_factory=list)
                                         # ["VFDs", "DDC controls", "BACnet", "Modbus"]
    software_expertise:     List[str] = field(default_factory=list)
                                         # ["AutoCAD MEP", "Revit", "QuickBooks", "Procore"]
    typical_project_size:   str = ""     # "$5K-$50K", "$50K-$500K", "$500K+"
    typical_deliverables:   List[str] = field(default_factory=list)
                                         # ["stamped drawings", "BOMs", "submittal packages", "RFIs"]
    professional_memberships: List[str] = field(default_factory=list)
                                         # ["ASHRAE", "NECA", "SMACNA", "ASPE"]
    service_area:           str = ""     # geographic scope: "Miami-Dade County" | "Southeast US"
    union_affiliation:      str = ""     # "IBEW Local 349" or "" if non-union
    # Content voice / style preferences
    content_tone:           str = "professional"  # "technical" | "professional" | "casual"
    avoids:                 List[str] = field(default_factory=list)
                                         # things Murphy should never say/recommend for this user
    # Murphy config for this tenant
    murphy_focus_areas: List[str] = field(default_factory=list)
    active_strategy_id: str = ""
    onboarding_complete: bool = False
    # Metadata
    created_at:         str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at:         str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    profile_version:    int = 1


# ─────────────────────────────────────────────────────────────────────────────
# Onboarding intake questions
# ─────────────────────────────────────────────────────────────────────────────

INTAKE_QUESTIONS = [
    {
        "id":       "business_name",
        "question": "What's the name of your business? (If you haven't named it yet, what are you thinking?)",
        "type":     "text",
        "required": True,
    },
    {
        "id":       "industry",
        "question": "What kind of business is this? Describe what you do in one sentence.",
        "type":     "text",
        "required": True,
        "hint":     "e.g. 'plumbing contractor in Phoenix' or 'online fitness coaching' or 'SaaS for accountants'",
    },
    {
        "id":       "stage",
        "question": "Where are you right now?",
        "type":     "choice",
        "required": True,
        "choices": [
            {"value": "idea",        "label": "I have an idea but haven't started yet"},
            {"value": "pre_revenue", "label": "I've started building but have no paying customers yet"},
            {"value": "early",       "label": "I have a few customers (1–10) and some revenue"},
            {"value": "existing",    "label": "I'm established with steady customers and revenue"},
            {"value": "scaling",     "label": "I'm actively growing and need to systematize everything"},
        ],
    },
    {
        "id":       "current_mrr",
        "question": "Roughly how much revenue does the business bring in per month right now?",
        "type":     "number",
        "required": True,
        "placeholder": "0 if you're just starting",
        "unit":     "USD/month",
    },
    {
        "id":       "monthly_budget",
        "question": "Beyond what you're paying for Murphy, how much can you spend per month on growing this business? Be honest — $0 is a completely valid answer and Murphy will build a strategy around it.",
        "type":     "number",
        "required": True,
        "placeholder": "0",
        "unit":     "USD/month",
        "note":     "Murphy doesn't provide startup capital. This is YOUR budget for ads, tools, contractors, etc.",
    },
    {
        "id":       "hours_per_week",
        "question": "How many hours per week can YOU personally put into this business right now?",
        "type":     "number",
        "required": True,
        "placeholder": "10",
        "unit":     "hours/week",
        "note":     "Murphy handles the operations — this is your time for decisions, meetings, and things only you can do.",
    },
    {
        "id":       "primary_goal",
        "question": "What's the #1 thing you want Murphy to help you accomplish in the next 90 days?",
        "type":     "choice",
        "required": True,
        "choices": [
            {"value": "get_first_customer",  "label": "Get my first paying customer"},
            {"value": "grow_revenue",        "label": "Grow my existing revenue"},
            {"value": "cut_costs",           "label": "Cut costs and improve margins"},
            {"value": "automate_operations", "label": "Automate my day-to-day operations so I can focus on growth"},
            {"value": "hire_and_scale",      "label": "Hire people and build a team"},
            {"value": "compliance_and_legal","label": "Get compliant (licenses, contracts, taxes, etc.)"},
            {"value": "raise_funding",       "label": "Raise investment or get a business loan"},
            {"value": "prepare_for_exit",    "label": "Prepare the business for sale or acquisition"},
        ],
    },
    {
        "id":       "biggest_problem",
        "question": "In your own words — what's the single biggest thing holding this business back right now?",
        "type":     "textarea",
        "required": True,
        "hint":     "Be specific. 'I don't have time' or 'I can't find customers' or 'I'm drowning in admin' — whatever it really is.",
    },
    {
        "id":       "existing_tools",
        "question": "What tools or software are you already using? (Don't list anything you want to replace — just what's staying.)",
        "type":     "text",
        "required": False,
        "hint":     "e.g. QuickBooks, Gmail, Jobber, Slack — or 'nothing yet'",
    },
    {
        "id":       "existing_employees",
        "question": "How many people work in this business right now (including you)?",
        "type":     "number",
        "required": True,
        "placeholder": "1",
    },
    {
        "id":       "location",
        "question": "Where is your business based?",
        "type":     "text",
        "required": True,
        "placeholder": "City, State / Country",
    },

    # ── User Knowledge & Domain Expertise ─────────────────────────────────
    # These make Murphy's content, specs, and deliverables match the user's
    # professional reality instead of being generic
    {
        "id":       "owner_profession",
        "question": "What is your profession or trade? Be specific.",
        "type":     "text",
        "required": True,
        "hint":     "e.g. 'Licensed Master Electrician', 'MEP Engineer PE', 'Executive Chef', 'Freight Broker', 'General Contractor' — the more specific the better",
        "note":     "Murphy uses this to generate content, specs, and documents that sound like YOU wrote them — not like a generic AI.",
    },
    {
        "id":       "licenses_certs",
        "question": "What licenses or certifications do you hold?",
        "type":     "text",
        "required": False,
        "hint":     "e.g. 'Master Electrician License FL', 'PE - Mechanical Engineering TX', 'LEED AP', 'ServSafe Manager', 'CDL Class A' — list all that apply",
        "note":     "Murphy includes your credentials in proposals, bids, and client-facing documents automatically.",
    },
    {
        "id":       "years_experience",
        "question": "How many years have you been working in this trade or profession?",
        "type":     "number",
        "required": True,
        "placeholder": "10",
        "unit":     "years",
    },
    {
        "id":       "specializations",
        "question": "What do you specialize in within your field? What are you known for being especially good at?",
        "type":     "text",
        "required": False,
        "hint":     "e.g. 'commercial HVAC design', 'tenant improvement buildouts', 'cold storage facilities', 'healthcare kitchens', 'hazmat freight' — be specific",
    },
    {
        "id":       "known_codes_standards",
        "question": "What codes, standards, or regulations do you regularly work with?",
        "type":     "text",
        "required": False,
        "hint":     "e.g. 'NEC 2023, NFPA 72, IBC 2021' or 'ASHRAE 90.1, SMACNA' or 'FDA Food Code, HACCP' — Murphy will reference these correctly in your deliverables",
    },
    {
        "id":       "preferred_vendors",
        "question": "Which vendors or suppliers do you prefer to use or have accounts with?",
        "type":     "text",
        "required": False,
        "hint":     "e.g. 'Ferguson Supply, Graybar, Trane, Carrier' — Murphy uses your preferred vendors in BOMs, equipment specs, and purchasing recommendations",
    },
    {
        "id":       "typical_deliverables",
        "question": "What types of documents or deliverables do you regularly produce for clients?",
        "type":     "text",
        "required": False,
        "hint":     "e.g. 'stamped engineering drawings, BOMs, submittal packages, RFIs, change orders, job cost reports, HACCP plans' — Murphy will generate these in your voice",
    },
    {
        "id":       "typical_project_size",
        "question": "What is the typical size of a project or job in your business?",
        "type":     "choice",
        "required": False,
        "choices": [
            {"value": "under_5k",      "label": "Under $5,000"},
            {"value": "5k_50k",        "label": "$5,000 – $50,000"},
            {"value": "50k_500k",      "label": "$50,000 – $500,000"},
            {"value": "500k_plus",     "label": "$500,000+"},
            {"value": "mixed",         "label": "Varies widely"},
        ],
    },
    {
        "id":       "content_tone",
        "question": "How do you communicate with clients? What tone should Murphy match?",
        "type":     "choice",
        "required": True,
        "choices": [
            {"value": "technical",     "label": "Highly technical — clients are engineers or tradespeople who speak the language"},
            {"value": "professional",  "label": "Professional but plain — clients are business owners who don't need jargon"},
            {"value": "casual",        "label": "Casual and direct — clients are neighbors, small business owners, everyday people"},
        ],
    },
    {
        "id":       "avoids",
        "question": "Is there anything Murphy should NEVER say, recommend, or do when representing your business?",
        "type":     "textarea",
        "required": False,
        "hint":     "e.g. 'Never recommend Brand X — we had a bad experience', 'Never quote jobs under $10K — not worth our time', 'Never use the word cheap'",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Strategy generator — budget-scaled, goal-specific
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StrategyAction:
    id:           str
    title:        str
    description:  str
    who_does_it:  str     # "murphy" | "you" | "murphy+you"
    cost_usd:     float   # per month
    time_hours:   float   # owner hours per week
    expected_outcome: str
    timeline_days:    int
    priority:         int  # 1 = highest


@dataclass
class TenantStrategy:
    id:              str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id:       str = ""
    budget_tier:     str = ""
    primary_goal:    str = ""
    business_stage:  str = ""
    summary:         str = ""
    actions:         List[StrategyAction] = field(default_factory=list)
    murphy_commits:  List[str] = field(default_factory=list)  # what Murphy will do automatically
    user_commits:    List[str] = field(default_factory=list)  # what requires the user
    milestones:      List[Dict] = field(default_factory=list)
    generated_at:    str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    next_review:     str = ""


class StrategyEngine:
    """
    Generates a 90-day action plan calibrated to:
      - The user's budget tier (zero/seed/growth/scale)
      - Their primary goal
      - Their business stage
      - Their available hours
      - Their existing tools (avoid redundant recommendations)
    """

    def generate(self, profile: TenantBusinessProfile) -> TenantStrategy:
        tier    = classify_budget(profile.monthly_budget)
        goal    = profile.primary_goal
        stage   = profile.stage
        hours   = profile.hours_per_week
        mrr     = profile.current_mrr
        problem = profile.biggest_problem

        strategy = TenantStrategy(
            tenant_id=profile.tenant_id,
            budget_tier=tier,
            primary_goal=goal,
            business_stage=stage,
        )

        # Build actions from the applicable playbook
        actions = []
        murphy_commits = []
        user_commits   = []

        # ── Always-on Murphy operations (included in every subscription) ──
        always_on = self._always_on_murphy(profile)
        actions       += always_on["actions"]
        murphy_commits += always_on["commits"]

        # ── Goal-specific strategy layer ──
        goal_layer = self._goal_strategy(profile, tier)
        actions       += goal_layer["actions"]
        murphy_commits += goal_layer["murphy_commits"]
        user_commits   += goal_layer["user_commits"]

        # ── Budget-specific amplification ──
        if tier == BudgetTier.ZERO:
            budget_layer = self._zero_budget_amplification(profile)
        elif tier == BudgetTier.SEED:
            budget_layer = self._seed_budget_amplification(profile)
        elif tier == BudgetTier.GROWTH:
            budget_layer = self._growth_budget_amplification(profile)
        else:
            budget_layer = self._scale_budget_amplification(profile)
        actions       += budget_layer["actions"]
        murphy_commits += budget_layer["murphy_commits"]
        user_commits   += budget_layer["user_commits"]

        # Deduplicate and sort by priority
        seen = set()
        unique_actions = []
        for a in sorted(actions, key=lambda x: x.priority):
            if a.id not in seen:
                seen.add(a.id)
                unique_actions.append(a)

        strategy.actions       = unique_actions[:15]  # top 15 actions
        strategy.murphy_commits = list(dict.fromkeys(murphy_commits))
        strategy.user_commits   = list(dict.fromkeys(user_commits))
        strategy.summary        = self._generate_summary(profile, tier, goal)
        strategy.milestones     = self._milestones(profile, tier)

        return strategy

    def _always_on_murphy(self, p: TenantBusinessProfile) -> Dict:
        """Murphy does these automatically for every tenant regardless of tier."""
        commits = [
            "Run your CRM — log every contact, track every interaction",
            "Write and send follow-up sequences for every lead (you approve content)",
            "Generate proposals and quotes from your specs",
            "Monitor compliance requirements for your industry and location",
            "Draft contracts, SOWs, and NDAs for your review",
            "Track your pipeline and flag deals going cold",
            "Generate weekly business summary every Monday 8 AM",
            "Alert you to any regulatory changes that affect your business",
        ]
        actions = [
            StrategyAction("crm_setup", "CRM setup + contact import",
                "Murphy configures your CRM with your existing contacts and deal pipeline",
                "murphy", 0, 0.5, "All your contacts and deals organized, tracked, followed up automatically",
                3, 1),
            StrategyAction("follow_up_sequences", "Automated follow-up sequences",
                "Murphy writes and runs follow-up email sequences for every prospect",
                "murphy", 0, 0.5, "No more leads falling through the cracks — Murphy follows up until they respond",
                7, 2),
            StrategyAction("weekly_brief", "Weekly executive brief",
                "Every Monday Murphy sends you a business summary: revenue, pipeline, wins, risks",
                "murphy", 0, 0, "You always know exactly where your business stands without digging for data",
                1, 3),
        ]
        return {"actions": actions, "commits": commits}

    def _goal_strategy(self, p: TenantBusinessProfile, tier: BudgetTier) -> Dict:
        """Strategy actions specific to the user's primary goal."""
        goal = p.primary_goal
        actions = []
        murphy_commits = []
        user_commits   = []

        if goal in (PrimaryGoal.FIRST_CUSTOMER, 'get_first_customer'):
            murphy_commits += [
                "Identify 50 ideal customer profiles from your industry description",
                "Write 3 outreach email sequences — cold, warm referral, LinkedIn",
                "Build a one-page pitch doc / landing page for your offer",
                "Draft your pricing and packaging options for review",
                "Set up a booking link so prospects can schedule calls",
            ]
            user_commits += [
                "Review and approve the outreach copy before Murphy sends (30 min)",
                "Get on the calls Murphy books — closing is yours",
                "Tell Murphy what happened on each call so it can improve targeting",
            ]
            actions += [
                StrategyAction("icp_research", "Ideal Customer Profile research",
                    "Murphy analyzes your industry and defines who your best first customer looks like",
                    "murphy", 0, 0, "Clear target: who to go after, where to find them, what they care about",
                    3, 1),
                StrategyAction("outreach_build", "Cold outreach sequence (50 targets)",
                    "Murphy identifies 50 real companies/people who match your ICP and writes personalized outreach",
                    "murphy+you", 0, 1, "First responses and booked calls within 2 weeks",
                    14, 2),
                StrategyAction("offer_doc", "One-page offer document",
                    "Murphy writes your pitch: what you do, who it's for, what it costs, why now",
                    "murphy+you", 0, 0.5, "Something real you can send to prospects that converts",
                    5, 3),
            ]

        elif goal in (PrimaryGoal.GROW_REVENUE, 'grow_revenue'):
            murphy_commits += [
                "Analyze your current customer base — who pays most, who refers most",
                "Identify upsell and cross-sell opportunities in existing accounts",
                "Build a referral program and automated referral request sequence",
                "Find 3 partnership opportunities with complementary businesses",
                "Run win-back sequences for churned customers",
            ]
            user_commits += [
                "Approve the upsell offers Murphy drafts",
                "Make intro calls Murphy schedules with referral partners",
            ]
            actions += [
                StrategyAction("customer_analysis", "Revenue concentration analysis",
                    "Murphy analyzes which customers drive 80% of your revenue and why",
                    "murphy", 0, 0, "Clarity on where revenue actually comes from so you can get more of it",
                    5, 1),
                StrategyAction("upsell_sequences", "Upsell + expansion sequences",
                    "Murphy identifies upsell opportunities and runs campaigns to existing customers",
                    "murphy", 0, 0, "10-20% revenue increase from existing base without new customer acquisition",
                    21, 2),
                StrategyAction("referral_engine", "Referral program build",
                    "Murphy builds and automates a referral program — ask, track, reward",
                    "murphy+you", 0, 0.5, "First referral customers within 30 days",
                    14, 3),
            ]

        elif goal in (PrimaryGoal.CUT_COSTS, 'cut_costs'):
            murphy_commits += [
                "Audit all current tool subscriptions — find redundancies",
                "Identify which tasks are taking your time that Murphy can own",
                "Model your cost structure — fixed vs variable per customer",
                "Find free/cheaper alternatives to your current paid tools",
            ]
            user_commits += [
                "Approve tool cancellations Murphy recommends",
                "Confirm which tasks you're willing to hand to Murphy",
            ]
            actions += [
                StrategyAction("tool_audit", "Tool subscription audit",
                    "Murphy audits every tool you pay for, finds overlaps, recommends cuts",
                    "murphy+you", 0, 1, "Typical result: $200-800/mo in cancelled redundant subscriptions",
                    7, 1),
                StrategyAction("time_audit", "Time + task delegation map",
                    "Murphy maps everything you spend time on and identifies what it can take over",
                    "murphy+you", 0, 1, "Hours freed per week for revenue-generating activities",
                    5, 2),
            ]

        elif goal in ('automate_operations', 'AUTOMATE', PrimaryGoal.AUTOMATE):
            murphy_commits += [
                "Map your current operational workflow end-to-end",
                "Identify the top 5 repetitive tasks Murphy can own immediately",
                "Build automated sequences for: intake, delivery, invoicing, follow-up",
                "Set up scheduling, dispatch, and task tracking",
            ]
            user_commits += [
                "Spend 2 hours with Murphy mapping your current workflow",
                "Approve the automation scripts before they go live",
            ]
            actions += [
                StrategyAction("workflow_mapping", "Operational workflow map",
                    "Murphy interviews you to map exactly how your business works today",
                    "murphy+you", 0, 2, "Complete picture of your operations so Murphy can take over the repeatable parts",
                    7, 1),
                StrategyAction("intake_automation", "Client intake automation",
                    "Murphy builds your intake form, welcome sequence, and first-week client communication",
                    "murphy", 0, 0, "Every new client gets a perfect onboarding experience with zero manual effort from you",
                    14, 2),
            ]

        elif goal in (PrimaryGoal.RAISE_FUNDING, 'raise_funding'):
            murphy_commits += [
                "Build your investor data room from your actual business metrics",
                "Identify 20 investors aligned with your industry and stage",
                "Write your pitch deck narrative and one-pager",
                "Research grant programs you qualify for (SBA, state, industry-specific)",
                "Draft your executive summary for review",
            ]
            user_commits += [
                "Review and approve all investor materials before Murphy sends",
                "Get on the investor calls Murphy books",
                "Provide monthly financials so Murphy can keep the data room current",
            ]
            actions += [
                StrategyAction("data_room", "Investor data room build",
                    "Murphy builds a complete investor package from your real numbers",
                    "murphy+you", 0, 2, "Professional investor package ready within a week",
                    7, 1),
                StrategyAction("grant_research", "Grant opportunity research",
                    "Murphy finds every grant you qualify for — federal, state, industry-specific",
                    "murphy", 0, 0, "Typically $10K-500K in non-dilutive funding opportunities identified",
                    14, 2),
                StrategyAction("investor_outreach", "Investor outreach sequence",
                    "Murphy identifies aligned investors and writes personalized pitches",
                    "murphy+you", 0, 1, "First investor conversations within 30 days",
                    21, 3),
            ]

        return {"actions": actions, "murphy_commits": murphy_commits, "user_commits": user_commits}

    def _zero_budget_amplification(self, p: TenantBusinessProfile) -> Dict:
        return {
            "actions": [
                StrategyAction("free_lead_gen", "Free lead generation (organic)",
                    "Murphy builds you a content + organic outreach plan using only free channels: LinkedIn, Google Business, local directories, industry forums",
                    "murphy+you", 0, 1, "Consistent inbound leads with zero ad spend",
                    30, 4),
                StrategyAction("grant_sweep", "Government grant sweep",
                    "Murphy searches every federal, state, and local grant program you qualify for and drafts applications",
                    "murphy", 0, 0, "Non-dilutive funding you didn't know existed — SBIR, SBA, state programs, industry grants",
                    14, 5),
                StrategyAction("barter_partnerships", "Barter + partnership outreach",
                    "Murphy identifies businesses you can trade services with — referrals for referrals, co-marketing, shared customers",
                    "murphy+you", 0, 0.5, "Revenue from referral partnerships without any cash outlay",
                    21, 6),
                StrategyAction("existing_revenue_optimize", "Squeeze existing revenue first",
                    "Before finding new customers, Murphy analyzes if you can raise prices, upsell existing customers, or reduce your service cost",
                    "murphy", 0, 0, "More money from what you already have before spending anything on growth",
                    7, 3),
            ],
            "murphy_commits": [
                "Build your entire growth strategy using zero-cash channels only",
                "Apply for every grant you qualify for (with your signature where required)",
                "Run organic outreach — LinkedIn, Google My Business, directories, forums",
                "Write all content, emails, proposals — you approve, Murphy sends",
                "Find and pursue barter/partnership deals with complementary businesses",
            ],
            "user_commits": [
                "Approve outreach copy and content before Murphy sends (30 min/week)",
                "Sign grant applications Murphy prepares",
                "Get on calls Murphy books — closing is yours",
                "Give Murphy feedback after every customer interaction",
            ],
        }

    def _seed_budget_amplification(self, p: TenantBusinessProfile) -> Dict:
        budget = p.monthly_budget
        return {
            "actions": [
                StrategyAction("small_ads_test", f"Paid channel test (${min(budget*0.4, 100):.0f}/mo)",
                    "Murphy designs a small paid test on the highest-ROI channel for your business type — Google Ads, LinkedIn, or local",
                    "murphy+you", min(budget*0.4, 100), 0.5,
                    "Data on what actually converts before committing more budget",
                    21, 4),
                StrategyAction("content_tools", "Content + brand tools ($50/mo)",
                    "Murphy recommends 1-2 essential paid tools for your specific situation (e.g. Canva Pro for contractors, Apollo for B2B sales)",
                    "murphy", 50, 0, "Professional materials and data that would take 10x as long to build manually",
                    7, 5),
            ],
            "murphy_commits": [
                "All zero-budget strategies PLUS:",
                f"Manage your ${budget:.0f}/mo budget — recommend where to allocate each dollar",
                "Run paid channel tests and report ROI weekly",
                "Pause spend that isn't converting before you waste the budget",
            ],
            "user_commits": [
                "Approve budget allocation each month (15 min)",
                "Connect your payment method to the tools Murphy recommends",
            ],
        }

    def _growth_budget_amplification(self, p: TenantBusinessProfile) -> Dict:
        budget = p.monthly_budget
        return {
            "actions": [
                StrategyAction("paid_acquisition", "Multi-channel paid acquisition",
                    "Murphy builds and manages your paid acquisition stack — Google, LinkedIn, retargeting, depending on your ICP",
                    "murphy", budget * 0.6, 1, "Predictable leads at a known cost per acquisition",
                    30, 4),
                StrategyAction("contractor_hire", "First contractor hire",
                    "Murphy drafts the job description, posts it, screens applicants, and recommends who to hire",
                    "murphy+you", budget * 0.3, 2, "Leverage your time — pay for help on specific deliverables",
                    30, 5),
            ],
            "murphy_commits": [
                "All seed strategies PLUS:",
                "Full paid acquisition management — campaign build, optimization, reporting",
                "Recruiting pipeline — JD, posting, screening, scheduling interviews",
                "Weekly spend report with ROI by channel",
            ],
            "user_commits": [
                "Approve campaigns before launch",
                "Final interviews and hire decisions",
                "Manage the contractor Murphy places",
            ],
        }

    def _scale_budget_amplification(self, p: TenantBusinessProfile) -> Dict:
        budget = p.monthly_budget
        return {
            "actions": [
                StrategyAction("full_growth_stack", "Full growth operations",
                    "Murphy manages your entire growth stack: paid, content, SEO, sales team, partnerships, events",
                    "murphy", budget * 0.7, 2, "Systematic, predictable growth across all channels",
                    30, 4),
                StrategyAction("team_build", "Team building program",
                    "Murphy manages recruiting across multiple roles simultaneously",
                    "murphy+you", budget * 0.2, 3, "The team that lets you stop doing everything yourself",
                    45, 5),
            ],
            "murphy_commits": [
                "All growth strategies PLUS:",
                "Full growth stack management — every channel, every campaign",
                "Team operations management — onboarding, performance, scheduling",
                "Monthly board-ready reporting for investors or partners",
            ],
            "user_commits": [
                "Weekly 1-hour review session with Murphy",
                "Final decisions on hires, partnerships, and major spend",
            ],
        }

    def _generate_summary(self, p: TenantBusinessProfile, tier: BudgetTier, goal: str) -> str:
        stage_labels = {
            "idea": "starting from scratch",
            "pre_revenue": "pre-revenue",
            "early": "early stage",
            "existing": "established",
            "scaling": "scaling",
        }
        tier_labels = {
            BudgetTier.ZERO:   "zero extra budget",
            BudgetTier.SEED:   f"${p.monthly_budget:.0f}/mo growth budget",
            BudgetTier.GROWTH: f"${p.monthly_budget:.0f}/mo growth budget",
            BudgetTier.SCALE:  f"${p.monthly_budget:,.0f}/mo growth budget",
        }
        goal_labels = {
            "get_first_customer":    "get your first paying customer",
            "grow_revenue":          "grow your existing revenue",
            "cut_costs":             "cut costs and improve margins",
            "automate_operations":   "automate your operations",
            "hire_and_scale":        "build your team",
            "compliance_and_legal":  "get compliant",
            "raise_funding":         "raise funding",
            "prepare_for_exit":      "prepare for exit",
        }
        return (
            f"Murphy's 90-day strategy for {p.business_name or 'your business'} — "
            f"{stage_labels.get(p.stage,'')}, {tier_labels.get(tier,'')}, "
            f"primary focus: {goal_labels.get(goal,goal)}. "
            f"Murphy runs the operations. You make the decisions."
        )

    def _milestones(self, p: TenantBusinessProfile, tier: BudgetTier) -> List[Dict]:
        return [
            {"day": 3,  "milestone": "CRM live, contacts imported, follow-up sequences running"},
            {"day": 7,  "milestone": "First outreach batch sent, offer document ready"},
            {"day": 14, "milestone": "First responses, Murphy reporting on what's working"},
            {"day": 30, "milestone": "First measurable result (customer, meeting, grant app, or revenue increase)"},
            {"day": 60, "milestone": "Pattern established — Murphy optimizing based on real data"},
            {"day": 90, "milestone": "Review with Murphy: what worked, next 90-day strategy"},
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Profile storage
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_schema() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tenant_profiles (
            tenant_id TEXT PRIMARY KEY,
            profile_json TEXT NOT NULL,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tenant_strategies (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            strategy_json TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_strategies_tenant
          ON tenant_strategies(tenant_id);
    """)
    conn.commit()
    conn.close()


def save_profile(profile: TenantBusinessProfile) -> None:
    _ensure_schema()
    profile.updated_at = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("""
        INSERT OR REPLACE INTO tenant_profiles (tenant_id, profile_json, created_at, updated_at)
        VALUES (?,?,?,?)
    """, (profile.tenant_id, json.dumps(asdict(profile)),
          profile.created_at, profile.updated_at))
    conn.commit()
    conn.close()


def load_profile(tenant_id: str) -> Optional[TenantBusinessProfile]:
    try:
        _ensure_schema()
        conn = sqlite3.connect(DB_PATH, timeout=5)
        row = conn.execute(
            "SELECT profile_json FROM tenant_profiles WHERE tenant_id=?",
            (tenant_id,)
        ).fetchone()
        conn.close()
        if row:
            data = json.loads(row[0])
            return TenantBusinessProfile(**{k: v for k, v in data.items()
                                           if k in TenantBusinessProfile.__dataclass_fields__})
    except Exception as exc:
        logger.error("Profile load error for %s: %s", tenant_id, exc)
    return None


def save_strategy(strategy: TenantStrategy) -> None:
    _ensure_schema()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("UPDATE tenant_strategies SET is_active=0 WHERE tenant_id=?",
                 (strategy.tenant_id,))
    conn.execute("""
        INSERT INTO tenant_strategies (id, tenant_id, strategy_json, is_active, created_at)
        VALUES (?,?,?,1,?)
    """, (strategy.id, strategy.tenant_id,
          json.dumps(asdict(strategy)), strategy.generated_at))
    conn.commit()
    conn.close()


def get_active_strategy(tenant_id: str) -> Optional[TenantStrategy]:
    try:
        _ensure_schema()
        conn = sqlite3.connect(DB_PATH, timeout=5)
        row = conn.execute(
            "SELECT strategy_json FROM tenant_strategies WHERE tenant_id=? AND is_active=1",
            (tenant_id,)
        ).fetchone()
        conn.close()
        if row:
            data = json.loads(row[0])
            s = TenantStrategy(
                id=data["id"], tenant_id=data["tenant_id"],
                budget_tier=data["budget_tier"], primary_goal=data["primary_goal"],
                business_stage=data["business_stage"], summary=data["summary"],
                murphy_commits=data["murphy_commits"], user_commits=data["user_commits"],
                milestones=data["milestones"], generated_at=data["generated_at"],
            )
            s.actions = [StrategyAction(**a) for a in data.get("actions", [])]
            return s
    except Exception as exc:
        logger.error("Strategy load error for %s: %s", tenant_id, exc)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge context injector — called at every content/deliverable generation point
# ─────────────────────────────────────────────────────────────────────────────

def build_knowledge_context(tenant_id: str) -> Dict[str, Any]:
    """
    Returns a structured context dict that gets injected into every LLM prompt
    when generating content, proposals, equipment specs, engineering deliverables,
    or any tenant-facing output.

    This is what makes Murphy sound like the user wrote it — not a generic AI.

    Usage:
        context = build_knowledge_context(tenant_id)
        prompt = f\"""
        {context['system_prefix']}

        Task: Write a proposal for...
        \"""
    """
    profile = load_profile(tenant_id)
    if not profile:
        return {
            "system_prefix": "",
            "has_knowledge":  False,
            "tenant_id":      tenant_id,
        }

    parts = []

    if profile.owner_profession:
        parts.append(f"You are writing on behalf of {profile.owner_profession}")
        if profile.years_experience:
            parts.append(f"with {profile.years_experience} years of experience")
        if profile.business_name:
            parts.append(f"at {profile.business_name}")
        parts.append(".")

    if profile.specializations:
        parts.append(
            f"Their specializations are: {', '.join(profile.specializations)}."
        )

    if profile.licenses_certs:
        parts.append(
            f"Active licenses and certifications: {', '.join(profile.licenses_certs)}."
        )

    if profile.known_codes_standards:
        parts.append(
            f"Always reference and comply with these codes/standards: "
            f"{', '.join(profile.known_codes_standards)}."
        )

    if profile.preferred_vendors:
        parts.append(
            f"When recommending equipment or materials, prefer these vendors: "
            f"{', '.join(profile.preferred_vendors)}."
        )

    if profile.typical_deliverables:
        parts.append(
            f"Typical deliverables this business produces: "
            f"{', '.join(profile.typical_deliverables)}."
        )

    if profile.typical_project_size:
        size_labels = {
            "under_5k": "under $5,000",
            "5k_50k":   "$5,000–$50,000",
            "50k_500k": "$50,000–$500,000",
            "500k_plus": "$500,000+",
            "mixed":    "a wide range",
        }
        parts.append(
            f"Typical project size: "
            f"{size_labels.get(profile.typical_project_size, profile.typical_project_size)}."
        )

    tone_instructions = {
        "technical":    "Use precise technical language. Reference code sections, model numbers, and engineering standards directly. Clients are peers.",
        "professional": "Use clear, professional language. Explain technical concepts plainly without dumbing them down. Clients are business owners.",
        "casual":       "Use direct, friendly language. Avoid jargon. Be human. Clients are regular people.",
    }
    if profile.content_tone and profile.content_tone in tone_instructions:
        parts.append(tone_instructions[profile.content_tone])

    if profile.avoids:
        parts.append(
            f"NEVER include the following in any output: "
            f"{'; '.join(profile.avoids)}."
        )

    if profile.service_area:
        parts.append(f"Service area: {profile.service_area}.")

    if profile.union_affiliation:
        parts.append(f"Union affiliation: {profile.union_affiliation}.")

    system_prefix = " ".join(parts) if parts else ""

    return {
        "system_prefix":         system_prefix,
        "has_knowledge":         bool(parts),
        "tenant_id":             tenant_id,
        "owner_profession":      profile.owner_profession,
        "licenses_certs":        profile.licenses_certs,
        "years_experience":      profile.years_experience,
        "specializations":       profile.specializations,
        "known_codes_standards": profile.known_codes_standards,
        "preferred_vendors":     profile.preferred_vendors,
        "typical_deliverables":  profile.typical_deliverables,
        "content_tone":          profile.content_tone,
        "avoids":                profile.avoids,
        "business_name":         profile.business_name,
        "industry":              profile.industry,
        "location":              profile.location,
    }


# Add-on management helpers
def grant_addon(tenant_id: str, addon: str, price_usd: float = 0.0, notes: str = "") -> Dict:
    """Grant a tenant access to a paid add-on feature."""
    import sqlite3 as _sq
    from datetime import datetime, timezone
    conn = _sq.connect("/var/lib/murphy-production/billing.db", timeout=5)
    conn.execute("""
        INSERT OR REPLACE INTO tenant_addons
          (tenant_id, addon, active, price_usd, started_at, notes)
        VALUES (?,?,1,?,?,?)
    """, (tenant_id, addon, price_usd,
          datetime.now(timezone.utc).isoformat(), notes))
    conn.commit()
    conn.close()
    return {"success": True, "tenant_id": tenant_id, "addon": addon}


def revoke_addon(tenant_id: str, addon: str) -> Dict:
    """Revoke a tenant's add-on (on cancellation or non-payment)."""
    import sqlite3 as _sq
    from datetime import datetime, timezone
    conn = _sq.connect("/var/lib/murphy-production/billing.db", timeout=5)
    conn.execute("""
        UPDATE tenant_addons SET active=0, cancelled_at=?
        WHERE tenant_id=? AND addon=?
    """, (datetime.now(timezone.utc).isoformat(), tenant_id, addon))
    conn.commit()
    conn.close()
    return {"success": True, "tenant_id": tenant_id, "addon": addon, "status": "revoked"}
