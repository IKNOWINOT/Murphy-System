"""R66 — Signup Profile Loader.

Bridges the gap between the onboarding wizard (which captures tenant
industry, stage, budget, goal, problem, employee count, etc. into
tenant_profiles.profile_json) and the MFGC/MSS pipelines (which
previously ran with zero customer-specific factors).

Public API:
    load_tenant_factors(tenant_id) -> MFGCFactorSet
    inject_into_mfgc_context(ctx, tenant_id) -> ctx  (mutates + returns)
    inject_into_mss_context(ctx, tenant_id) -> ctx   (mutates + returns)

Reads:
    /var/lib/murphy-production/tenants.db
        tenant_profiles(tenant_id PK, profile_json TEXT, ...)

The actual JSON columns we extract:
    industry          (e.g. "plumbing contractor", "commercial cleaning")
    business_name
    stage             (idea / early / growing / scaling)
    current_mrr
    monthly_budget
    hours_per_week
    primary_goal
    biggest_problem
    existing_employees
    existing_customers
    murphy_focus_areas

We DERIVE (not stored on the profile):
    compliance_regimes   — from industry keywords (plumbing→OSHA, cleaning→EPA/OSHA, ...)
    risk_tolerance       — from stage + budget (idea+zero budget = high risk OK; scaling = low)
    required_gates       — from industry + compliance
    audit_cadence        — from stage (idea=monthly, growing=weekly, scaling=daily)
    team_size_bucket     — from existing_employees (solo / small / mid / large)
    target_audience      — from industry + primary_goal

Failures degrade gracefully — returns an empty MFGCFactorSet rather than raising,
so the deliverable pipeline never crashes when a tenant_id is unknown or missing.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.signup_profile_loader")

TENANTS_DB = "/var/lib/murphy-production/tenants.db"


@dataclass
class MFGCFactorSet:
    """Customer-specific factors that drive MFGC gating and MSS context."""
    tenant_id: str = ""
    business_name: str = ""
    industry: str = ""
    stage: str = ""
    compliance_regimes: List[str] = field(default_factory=list)
    risk_tolerance: str = "medium"          # low | medium | high
    required_gates: List[str] = field(default_factory=list)
    audit_cadence: str = "weekly"           # daily | weekly | monthly
    team_size_bucket: str = "solo"          # solo | small | mid | large
    target_audience: str = ""
    primary_goal: str = ""
    biggest_problem: str = ""
    source: str = "default"                 # "tenant_profile" | "default" | "error"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def is_empty(self) -> bool:
        return not self.industry and not self.business_name


# ────────────────────────────────────────────────────────────────────────
# Derivation rules
# ────────────────────────────────────────────────────────────────────────

# Industry keyword → compliance regime mapping.
# Conservative: only include regimes that are objectively required for that vertical.
_INDUSTRY_COMPLIANCE: Dict[str, List[str]] = {
    "plumbing":          ["OSHA", "EPA-water", "local-licensing"],
    "electrical":        ["OSHA", "NEC-electrical-code", "local-licensing"],
    "hvac":              ["OSHA", "EPA-refrigerant", "local-licensing"],
    "cleaning":          ["OSHA", "EPA-chemical"],
    "janitorial":        ["OSHA", "EPA-chemical"],
    "landscaping":       ["OSHA", "EPA-pesticide"],
    "roofing":           ["OSHA", "local-licensing"],
    "construction":      ["OSHA", "local-licensing", "ICC-building-code"],
    "general contractor":["OSHA", "local-licensing", "ICC-building-code"],
    "restaurant":        ["FDA-food-safety", "local-health-dept", "OSHA"],
    "food":              ["FDA-food-safety", "local-health-dept"],
    "trucking":          ["DOT-FMCSA", "OSHA"],
    "logistics":         ["DOT-FMCSA"],
    "accounting":        ["SOC2", "GAAP", "IRS-circular-230"],
    "cpa":               ["SOC2", "GAAP", "IRS-circular-230", "AICPA"],
    "tax":               ["IRS-circular-230", "AICPA"],
    "legal":             ["state-bar", "ABA-model-rules"],
    "law":               ["state-bar", "ABA-model-rules"],
    "medical":           ["HIPAA", "state-medical-board"],
    "dental":            ["HIPAA", "state-dental-board"],
    "healthcare":        ["HIPAA", "state-medical-board"],
    "wellness":          ["HIPAA-lite", "state-licensing"],
    "fitness":           ["state-licensing"],
    "real estate":       ["state-RE-licensing", "RESPA", "fair-housing"],
    "insurance":         ["state-DOI", "NAIC"],
    "finance":           ["SEC", "FINRA"],
    "fintech":           ["SEC", "FINRA", "SOC2"],
    "software":          ["SOC2"],
    "saas":              ["SOC2", "GDPR-EU", "CCPA"],
    "cnc":               ["ISO9001", "AS9100"],
    "machining":         ["ISO9001"],
    "manufacturing":     ["ISO9001", "OSHA"],
    "engineering":       ["PE-licensure", "state-licensing"],
}

# Industry → standard gate names that should be active by default.
_INDUSTRY_GATES: Dict[str, List[str]] = {
    "plumbing":     ["safety_inspection", "permit_pulled", "code_compliance", "customer_signoff"],
    "electrical":   ["permit_pulled", "code_compliance", "safety_inspection", "customer_signoff"],
    "hvac":         ["permit_pulled", "refrigerant_handling", "customer_signoff"],
    "cleaning":     ["chemical_msds_logged", "customer_signoff", "before_after_photos"],
    "construction": ["permit_pulled", "safety_briefing", "code_compliance", "punch_list_closed"],
    "restaurant":   ["health_inspection_passed", "food_safety_log", "allergen_chart"],
    "accounting":   ["client_engagement_letter", "workpaper_review", "partner_signoff", "audit_trail"],
    "cpa":          ["client_engagement_letter", "workpaper_review", "partner_signoff", "audit_trail"],
    "tax":          ["client_engagement_letter", "form_review", "ptin_logged", "client_signoff"],
    "legal":        ["conflict_check", "engagement_letter", "partner_review", "client_signoff"],
    "medical":      ["informed_consent", "hipaa_notice", "chart_review", "billing_audit"],
    "wellness":     ["intake_form", "consent", "session_notes"],
    "software":     ["code_review", "tests_passing", "security_scan", "deploy_approval"],
    "saas":         ["code_review", "tests_passing", "security_scan", "deploy_approval", "data_handling_review"],
    "cnc":          ["first_article_inspection", "in_process_qc", "final_qc", "customer_dimensional_report"],
    "manufacturing":["first_article_inspection", "in_process_qc", "final_qc"],
}

_DEFAULT_GATES = ["intent_clarified", "scope_agreed", "deliverable_review", "customer_signoff"]


def _derive_compliance(industry: str) -> List[str]:
    if not industry:
        return []
    s = industry.lower()
    for key, regimes in _INDUSTRY_COMPLIANCE.items():
        if key in s:
            return list(regimes)
    return []


def _derive_required_gates(industry: str, compliance_regimes: List[str]) -> List[str]:
    base = list(_DEFAULT_GATES)
    if not industry:
        return base
    s = industry.lower()
    for key, gates in _INDUSTRY_GATES.items():
        if key in s:
            # industry-specific gates replace the deliverable_review default
            specific = list(gates)
            # always keep intent_clarified + customer_signoff
            for must in ("intent_clarified", "customer_signoff"):
                if must not in specific:
                    specific.append(must)
            return specific
    return base


def _derive_risk_tolerance(stage: str, current_mrr: float, monthly_budget: float) -> str:
    s = (stage or "").lower()
    # Idea/early stage with low MRR can stomach more risk to learn fast.
    if s in ("idea", "early") and current_mrr < 5000:
        return "high"
    if s in ("scaling",) or current_mrr >= 50_000:
        return "low"
    return "medium"


def _derive_audit_cadence(stage: str) -> str:
    s = (stage or "").lower()
    if s in ("scaling",):
        return "daily"
    if s in ("growing", "growth"):
        return "weekly"
    return "monthly"


def _derive_team_bucket(existing_employees: int) -> str:
    if existing_employees <= 0:
        return "solo"
    if existing_employees <= 5:
        return "small"
    if existing_employees <= 25:
        return "mid"
    return "large"


def _derive_target_audience(industry: str, primary_goal: str) -> str:
    ind = (industry or "").strip().lower()
    goal = (primary_goal or "").strip().lower()
    if not ind:
        return "general business owner"
    if "first_customer" in goal or "get_first" in goal:
        return f"early-stage {ind} owner, no marketing budget"
    if "grow_revenue" in goal:
        return f"established {ind} owner looking to expand customer base"
    if "automate" in goal or "scale" in goal:
        return f"{ind} operator ready to systematize operations"
    return f"{ind} business owner"


# ────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────

def load_tenant_factors(tenant_id: str, db_path: str = TENANTS_DB) -> MFGCFactorSet:
    """Return an MFGCFactorSet for the given tenant_id.

    Never raises — on any failure returns an empty set with source='error' or 'default'.
    """
    if not tenant_id:
        return MFGCFactorSet(source="default")
    try:
        con = sqlite3.connect(db_path, timeout=5.0)
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT profile_json FROM tenant_profiles WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        con.close()
        if not row:
            logger.info("R66: no tenant_profile row for tenant_id=%s — using defaults", tenant_id)
            return MFGCFactorSet(tenant_id=tenant_id, source="default")
        profile = json.loads(row["profile_json"] or "{}")
    except Exception as exc:
        logger.warning("R66 loader error for tenant_id=%s: %s", tenant_id, exc)
        return MFGCFactorSet(tenant_id=tenant_id, source="error")

    industry = str(profile.get("industry", "")).strip()
    stage = str(profile.get("stage", "")).strip()
    mrr = float(profile.get("current_mrr", 0) or 0)
    budget = float(profile.get("monthly_budget", 0) or 0)
    employees = int(profile.get("existing_employees", 0) or 0)
    primary_goal = str(profile.get("primary_goal", "")).strip()

    compliance = _derive_compliance(industry)
    gates = _derive_required_gates(industry, compliance)
    risk = _derive_risk_tolerance(stage, mrr, budget)
    cadence = _derive_audit_cadence(stage)
    team = _derive_team_bucket(employees)
    audience = _derive_target_audience(industry, primary_goal)

    return MFGCFactorSet(
        tenant_id=tenant_id,
        business_name=str(profile.get("business_name", "")).strip(),
        industry=industry,
        stage=stage,
        compliance_regimes=compliance,
        risk_tolerance=risk,
        required_gates=gates,
        audit_cadence=cadence,
        team_size_bucket=team,
        target_audience=audience,
        primary_goal=primary_goal,
        biggest_problem=str(profile.get("biggest_problem", "")).strip(),
        source="tenant_profile",
    )


def inject_into_mfgc_context(ctx: Dict[str, Any], tenant_id: Optional[str]) -> Dict[str, Any]:
    """Mutate ctx with factor_set + factors dict, return it."""
    if not isinstance(ctx, dict):
        ctx = {}
    if not tenant_id:
        return ctx
    fs = load_tenant_factors(tenant_id)
    ctx["tenant_id"] = tenant_id
    ctx["factor_set"] = fs.to_dict()
    ctx["factors"] = {
        "industry": fs.industry,
        "compliance_regimes": fs.compliance_regimes,
        "required_gates": fs.required_gates,
        "risk_tolerance": fs.risk_tolerance,
        "audit_cadence": fs.audit_cadence,
        "team_size_bucket": fs.team_size_bucket,
    }
    return ctx


def inject_into_mss_context(ctx: Dict[str, Any], tenant_id: Optional[str]) -> Dict[str, Any]:
    """Same as MFGC, plus MSS-specific surface keys (industry, target_audience)."""
    ctx = inject_into_mfgc_context(ctx, tenant_id)
    if tenant_id:
        fs = ctx.get("factor_set") or {}
        # Direct top-level keys for MSS magnify/solidify
        ctx["industry"] = fs.get("industry", "")
        ctx["target_audience"] = fs.get("target_audience", "")
        ctx["compliance_regimes"] = fs.get("compliance_regimes", [])
        ctx["business_name"] = fs.get("business_name", "")
        ctx["primary_goal"] = fs.get("primary_goal", "")
        ctx["biggest_problem"] = fs.get("biggest_problem", "")
    return ctx
