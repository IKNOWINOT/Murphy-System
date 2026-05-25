"""
tier_policy.py — Canonical tier × department access matrix
============================================================
PATCH-414 — single source of truth for "who can call what".

WHAT THIS IS:
  The authoritative access control matrix for Murphy. Every API endpoint
  is matched against a route-pattern → required-tier set. Middleware
  consults this before letting a request through.

WHY IT EXISTS:
  Scattering tier checks across hundreds of endpoints is a maintenance
  disaster. Centralizing the matrix here means: one place to audit, one
  place to change policy, one place that all docs can point to.

HOW IT FITS:
  Imported by:
    - modular_auth.py (the middleware)
    - patch414_tenancy_dept_scoping.py (this deploy patch, for tests)
  Read by:
    - /api/identity/me (returns the resolved scope for the current caller)

KEY CONCEPTS:
  - PATH_TIER_RULES: list of (regex pattern, allowed_tiers, optional_dept_filter)
  - FOUNDER tier ALWAYS passes (nothing locks the founder out of their own system)
  - EMPLOYEE tier needs a matching department for finance/sales/hr/etc routes
  - KIN_ADULT can read most things but not modify money/compliance
  - KIN_CHILD is read-only on household-context items only
  - GUEST is read-only on a small whitelist

LAST UPDATED: 2026-05-25 by PATCH-414
"""
import re
from typing import Iterable, Optional, Tuple

# ── Allowed tiers ──────────────────────────────────────────────────────────
TIER_FOUNDER     = "founder"
TIER_KIN_ADULT   = "kin_adult"
TIER_KIN_CHILD   = "kin_child"
TIER_EMPLOYEE    = "employee"
TIER_TENANT_USER = "tenant_user"
TIER_GUEST       = "guest_recurring"
TIER_GUEST_ONE   = "guest_oneoff"

ALL_TIERS = (
    TIER_FOUNDER, TIER_KIN_ADULT, TIER_KIN_CHILD,
    TIER_EMPLOYEE, TIER_TENANT_USER,
    TIER_GUEST, TIER_GUEST_ONE,
)

# ── Access matrix ──────────────────────────────────────────────────────────
# Each rule: (regex, tiers_allowed, dept_required_if_employee)
# Order matters: first match wins. Founder is implicit on every route.

PATH_TIER_RULES: list[Tuple[str, frozenset, Optional[frozenset]]] = [
    # ── Founder-only platform/admin surfaces ────────────────────────────
    (r"^/api/admin/",            frozenset({TIER_FOUNDER}), None),
    (r"^/api/founder/",          frozenset({TIER_FOUNDER}), None),
    (r"^/api/vault/",            frozenset({TIER_FOUNDER}), None),
    (r"^/api/security/",         frozenset({TIER_FOUNDER}), None),
    (r"^/api/identity/promote",  frozenset({TIER_FOUNDER}), None),
    (r"^/api/identity/employees",frozenset({TIER_FOUNDER}), None),
    (r"^/api/world/refresh",     frozenset({TIER_FOUNDER}), None),

    # ── Department-scoped employee surfaces ────────────────────────────
    (r"^/api/finance/",   frozenset({TIER_FOUNDER, TIER_EMPLOYEE}), frozenset({"finance"})),
    (r"^/api/payroll/",   frozenset({TIER_FOUNDER, TIER_EMPLOYEE}), frozenset({"finance", "hr"})),
    (r"^/api/hr/",        frozenset({TIER_FOUNDER, TIER_EMPLOYEE}), frozenset({"hr"})),
    (r"^/api/compliance/",frozenset({TIER_FOUNDER, TIER_EMPLOYEE}), frozenset({"compliance"})),
    (r"^/api/sales/",     frozenset({TIER_FOUNDER, TIER_EMPLOYEE}), frozenset({"sales"})),
    (r"^/api/crm/",       frozenset({TIER_FOUNDER, TIER_EMPLOYEE}), frozenset({"sales", "cs"})),

    # ── Kin-readable (whole household sees) ────────────────────────────
    (r"^/api/household/",     frozenset({TIER_FOUNDER, TIER_KIN_ADULT, TIER_KIN_CHILD}), None),
    (r"^/api/world/snapshot", frozenset({TIER_FOUNDER, TIER_KIN_ADULT, TIER_KIN_CHILD, TIER_EMPLOYEE}), None),
    (r"^/api/events/feed",    frozenset({TIER_FOUNDER, TIER_KIN_ADULT, TIER_EMPLOYEE}), None),

    # ── Identity self-read (anyone authenticated) ──────────────────────
    (r"^/api/identity/me",    frozenset({TIER_FOUNDER, TIER_KIN_ADULT, TIER_KIN_CHILD,
                                          TIER_EMPLOYEE, TIER_TENANT_USER, TIER_GUEST}), None),

    # ── Default: founder + employee (any dept) for catch-all /api/ ─────
    # Anything not explicitly listed requires at least employee tier.
    (r"^/api/",               frozenset({TIER_FOUNDER, TIER_EMPLOYEE}), None),
]

# ── Helpers ────────────────────────────────────────────────────────────────
_COMPILED = [(re.compile(p), tiers, depts) for p, tiers, depts in PATH_TIER_RULES]


def resolve_required(path: str) -> Tuple[frozenset, Optional[frozenset]]:
    """Return (allowed_tiers, required_depts_or_None) for a given path.

    If no rule matches, defaults to founder-only (safe fallback).

    Args:
        path: URL path like "/api/finance/crypto-wallet"

    Returns:
        (allowed_tiers, optional_dept_filter)

    Example:
        >>> resolve_required("/api/finance/balance")
        (frozenset({"founder", "employee"}), frozenset({"finance"}))
    """
    for pattern, tiers, depts in _COMPILED:
        if pattern.match(path):
            return tiers, depts
    # Unknown path: fail closed
    return frozenset({TIER_FOUNDER}), None


def is_allowed(path: str, tier: str, dept: Optional[str]) -> bool:
    """Check if a (tier, dept) tuple is allowed to access path."""
    if tier == TIER_FOUNDER:
        return True  # Founder is never locked out
    allowed_tiers, required_depts = resolve_required(path)
    if tier not in allowed_tiers:
        return False
    if required_depts is not None and tier == TIER_EMPLOYEE:
        if dept not in required_depts:
            return False
    return True
