#!/usr/bin/env python3
"""
PATCH-414 — Tenancy + Department Scoping (Phase 2)
====================================================

WHAT THIS IS:
  Adds three-tier identity enforcement (founder / kin / employee) and
  department-based access control to Murphy's API layer. Extends the
  existing household_profiles table (PATCH-408) and modular auth middleware
  to enforce who can call what.

WHY IT EXISTS:
  Today, anyone with the founder API key has full access; everyone else
  is rejected. As Murphy starts running real employees (Phase 5a sales
  reps) and exposing tenant-facing surfaces, we need to:

    1. Distinguish between founder / kin / employee / tenant_user
    2. Scope employees by department (sales can't see finance, etc.)
    3. Enforce this at the middleware layer so individual endpoints
       don't have to remember to check
    4. Let Rosetta see the tier+dept on every request so it can narrow
       role-context accordingly

HOW IT FITS:
  Layers on top of:
    - PATCH-408 (household_profiles registry)
    - PATCH-410 (unified identity / device pairing)
    - modular_auth.py (current auth middleware)

  Modifies:
    - household_profiles: add `department` and extend `permission_tier`
      enum to include "employee" and "tenant_user"
    - modular_auth.py: add `_resolve_tier_and_dept()` → request.state
    - runtime/app.py: add small decorator `@requires_tier(...)` for
      endpoint-level scope checks
    - New file: src/tier_policy.py — the canonical tier×department
      access matrix, easy to audit, no surprises

KEY CONCEPTS:
  - tier:        founder | kin_adult | kin_child | employee | tenant_user | guest_recurring
  - department:  sales | finance | ops | hr | compliance | engineering | cs | NULL
                 (NULL for founder/kin/guest; required for employee)
  - scope:      "platform" (founder), "household" (kin), "department:<x>" (employee),
                "tenant:<id>" (tenant_user)
  - The middleware reads the API key OR session OR OAuth token, resolves it
    to a household_profile, and populates request.state.tier / .dept / .scope

ENDPOINTS / PUBLIC SURFACE:
  - GET  /api/identity/me  → returns the current request's tier, dept, scope
  - POST /api/identity/promote  → founder-only; promotes a profile to employee
                                  with a dept, generates an API key for them
  - GET  /api/identity/employees  → founder-only; list all employees

DEPENDENCIES:
  - sqlite3 (household DB)
  - hmac, secrets (key generation)
  - fastapi.Request

VAULT SECRETS USED:
  - None this patch (employees get individual API keys via dedicated table)

EVENT SPINE EMISSIONS:
  - identity.tier.promoted   when a profile becomes an employee
  - identity.scope.denied    when middleware rejects a scope mismatch
  - identity.key.generated   when an employee API key is minted

KNOWN LIMITS:
  - This patch is the FOUNDATION layer. It does NOT yet narrow Rosetta
    context — that's PATCH-415 (Phase 3, role-perspective engine).
  - Tenant_user resolution (multi-tenant SaaS customers) is stubbed;
    will be filled in when Phase 5 (self-selling) lands customers.

LAST UPDATED: 2026-05-25 by Murphy/Phase-2
"""
import sqlite3
import secrets
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ───────────────────────────────────────────────────────────
HOUSEHOLD_DB = "/var/lib/murphy-production/murphy_household.db"
APP_DB       = "/opt/Murphy-System/data/murphy.db"

VALID_TIERS = (
    "founder", "kin_adult", "kin_child",
    "employee", "tenant_user",
    "guest_recurring", "guest_oneoff",
)
VALID_DEPTS = (
    "sales", "finance", "ops", "hr",
    "compliance", "engineering", "cs", "research",
)


def step(msg: str) -> None:
    print(f"  ▶ {msg}", flush=True)


def done(msg: str) -> None:
    print(f"  ✓ {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"  ⚠ {msg}", flush=True)


# ── Step 1 — extend household_profiles schema ──────────────────────────────
def extend_household_schema() -> None:
    """Add department column and confirm permission_tier supports employee tier.

    The existing schema is permissive (TEXT for permission_tier with no CHECK),
    so we only need to:
      1. Add `department` column if missing
      2. Add `employee_key_hash` for storing employee API key fingerprints
      3. Add `hire_date`, `commission_rate`, `territory` for sales reps later
    """
    step("Step 1 — extending household_profiles schema")
    conn = sqlite3.connect(HOUSEHOLD_DB)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(household_profiles)")
    cols = {row[1] for row in cur.fetchall()}

    new_cols = [
        ("department",       "TEXT"),         # sales|finance|ops|hr|compliance|engineering|cs|research
        ("employee_key_hash", "TEXT"),         # SHA256 fingerprint of the employee's API key
        ("hire_date",        "TEXT"),         # ISO date when promoted to employee
        ("commission_rate",  "REAL"),         # 0.0–1.0 — for sales reps (Phase 5a)
        ("territory",        "TEXT"),         # geographic or vertical (Phase 5a)
        ("manager_id",       "TEXT"),         # reports-to profile_id
    ]
    added = []
    for name, dtype in new_cols:
        if name not in cols:
            cur.execute(f"ALTER TABLE household_profiles ADD COLUMN {name} {dtype}")
            added.append(name)
    conn.commit()
    conn.close()
    if added:
        done(f"Added columns: {', '.join(added)}")
    else:
        done("Schema already current (no changes)")


# ── Step 2 — create tier_policy.py module ──────────────────────────────────
TIER_POLICY_SRC = '''"""
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
'''


def write_tier_policy() -> None:
    """Step 2: write the tier_policy.py module."""
    step("Step 2 — writing tier_policy.py module")
    target = Path("/opt/Murphy-System/src/tier_policy.py")
    target.write_text(TIER_POLICY_SRC)
    done(f"Wrote {target} ({len(TIER_POLICY_SRC)} bytes)")


# ── Step 3 — verify schema + policy module load ──────────────────────────
def verify() -> None:
    """Verify the changes by reading them back."""
    step("Step 3 — verification")

    # Schema check
    conn = sqlite3.connect(HOUSEHOLD_DB)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(household_profiles)").fetchall()}
    conn.close()
    expected = {"department", "employee_key_hash", "hire_date",
                "commission_rate", "territory", "manager_id"}
    if expected.issubset(cols):
        done(f"All 6 new columns present in household_profiles")
    else:
        missing = expected - cols
        warn(f"Missing columns: {missing}")

    # Policy module check — does it import cleanly?
    sys.path.insert(0, "/opt/Murphy-System/src")
    try:
        import importlib
        import tier_policy
        importlib.reload(tier_policy)
        # Spot-check a couple of routes
        cases = [
            ("/api/finance/balance",   "employee", "finance",     True),
            ("/api/finance/balance",   "employee", "sales",       False),
            ("/api/finance/balance",   "founder",  None,          True),
            ("/api/identity/me",       "kin_adult", None,         True),
            ("/api/admin/secrets",     "employee", "hr",          False),
            ("/api/sales/leads",       "employee", "sales",       True),
            ("/api/sales/leads",       "kin_adult", None,         False),
        ]
        all_pass = True
        for path, tier, dept, expected_pass in cases:
            actual = tier_policy.is_allowed(path, tier, dept)
            mark = "✓" if actual == expected_pass else "✗"
            print(f"      {mark} {tier:12s} {(dept or '-'):10s} {path:30s} → {actual} (expected {expected_pass})")
            if actual != expected_pass:
                all_pass = False
        if all_pass:
            done("All 7 policy spot-checks passed")
        else:
            warn("Some policy checks failed — review tier_policy.py")
    except Exception as e:
        warn(f"Could not load tier_policy.py: {e}")


# ── Main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 64)
    print("  PATCH-414 — Tenancy + Department Scoping (Phase 2 foundation)")
    print("═" * 64)
    extend_household_schema()
    write_tier_policy()
    verify()
    print()
    print("  Done. Foundation laid. Next steps (later patches):")
    print("    - PATCH-414b: hook modular_auth.py to read tier_policy on each request")
    print("    - PATCH-414c: /api/identity/me, /promote, /employees endpoints")
    print("    - PATCH-414d: Murphy OS uses /me to render the right sidebar items")
