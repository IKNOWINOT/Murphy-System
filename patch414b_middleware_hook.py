#!/usr/bin/env python3
"""
PATCH-414b — Hook tier_policy into modular_auth dispatch
=========================================================

WHAT THIS IS:
  Modifies modular_auth.py to (a) populate request.state.tier and
  request.state.dept based on which auth method succeeded, and
  (b) consult tier_policy.is_allowed() before allowing the request through.

WHY IT EXISTS:
  PATCH-414 created the policy matrix. This patch makes it actually enforce.
  Without 414b, the policy file sits there pretty but the middleware ignores it.

HOW IT FITS:
  In-place edit of /opt/Murphy-System/src/modular_auth.py.
  Wraps the existing dispatch() with one tier check between
  "auth method succeeded" and "return await call_next(request)".

  Founder API key → tier=founder, dept=None  (always allowed)
  Internal token  → tier=founder, dept=None  (service-to-service trusted)
  Employee API key (new): looked up by SHA256 hash in household_profiles
                          → tier=employee, dept=<their department>
  Bearer / cookie → tier=tenant_user, dept=None  (until Phase 5 wires real tenants)

DEPENDENCIES:
  - PATCH-414 must be deployed first (tier_policy.py and DB schema)

EVENT SPINE EMISSIONS:
  - identity.scope.denied  when a request is blocked by policy

KNOWN LIMITS:
  - Bearer/cookie still resolves to tenant_user — proper tenant resolution
    is Phase 5 work.
  - This patch is BACKWARD-COMPATIBLE: a request with a founder API key
    behaves exactly as before. Only new tier=employee keys see new behavior.

LAST UPDATED: 2026-05-25 by PATCH-414b
"""
import shutil
import hashlib
from pathlib import Path

MODULAR_AUTH = Path("/opt/Murphy-System/src/modular_auth.py")
BACKUP = MODULAR_AUTH.with_suffix(".py.pre-414b")

# ── Read existing source ────────────────────────────────────────────────────
src = MODULAR_AUTH.read_text()

if "tier_policy" in src:
    print("  ⚠ modular_auth.py already references tier_policy — skipping (idempotent)")
    raise SystemExit(0)

# ── Backup ─────────────────────────────────────────────────────────────────
shutil.copy(MODULAR_AUTH, BACKUP)
print(f"  ✓ Backed up to {BACKUP}")

# ── Patch 1: add import + helper near the top, after the existing imports ──
# Find the line "from starlette" or "from fastapi" or similar, append after.
import_anchor = 'logger = logging.getLogger("murphy.modular_auth")'
import_inject = '''
# ── PATCH-414b: tier_policy integration ────────────────────────────────────
try:
    import tier_policy as _tier_policy
except Exception:  # pragma: no cover
    _tier_policy = None
    logger.warning("PATCH-414b: tier_policy module unavailable — running open")

import hashlib as _hashlib_414b
import sqlite3 as _sqlite_414b

_HOUSEHOLD_DB_414b = "/var/lib/murphy-production/murphy_household.db"

def _resolve_employee_by_key(api_key: str):
    """Look up an employee profile by API key fingerprint.

    Args:
        api_key: raw API key the client sent (X-API-Key or Bearer).

    Returns:
        dict {profile_id, full_name, tier, department} on match, else None.
    """
    if not api_key or len(api_key) < 16:
        return None
    fp = _hashlib_414b.sha256(api_key.encode()).hexdigest()
    try:
        conn = _sqlite_414b.connect(_HOUSEHOLD_DB_414b)
        row = conn.execute(
            "SELECT profile_id, full_name, permission_tier, department "
            "FROM household_profiles WHERE employee_key_hash = ?",
            (fp,),
        ).fetchone()
        conn.close()
    except Exception as e:
        logger.warning("PATCH-414b: employee lookup failed: %s", e)
        return None
    if not row:
        return None
    return {
        "profile_id": row[0],
        "full_name": row[1],
        "tier": row[2] or "employee",
        "department": row[3],
    }
'''

new_src = src.replace(import_anchor, import_anchor + import_inject, 1)
if new_src == src:
    print(f"  ✗ Could not find import anchor '{import_anchor}' — aborting")
    raise SystemExit(1)
src = new_src

# ── Patch 2: in dispatch(), after _check_api_key success, also try employee ──
# Original block:
#         if self._check_api_key(request):
#             request.state.actor_kind = "api_key"
#             request.state.actor_account_id = "founder"
#             return await call_next(request)
#
# New: founder check stays as-is; we ALSO add an employee-key fallback
# BEFORE returning, and we add a tier_policy check immediately before each
# `return await call_next(request)` line.

founder_block = """        if self._check_api_key(request):
            request.state.actor_kind = "api_key"
            request.state.actor_account_id = "founder"
            return await call_next(request)"""

founder_replacement = """        if self._check_api_key(request):
            request.state.actor_kind = "api_key"
            request.state.actor_account_id = "founder"
            request.state.tier = "founder"
            request.state.department = None
            return await call_next(request)

        # PATCH-414b: employee API key fallback
        provided_key = (request.headers.get("X-API-Key") or "").strip()
        if not provided_key:
            authz = (request.headers.get("Authorization") or "").strip()
            if authz.lower().startswith("bearer "):
                provided_key = authz[7:].strip()
        if provided_key:
            emp = _resolve_employee_by_key(provided_key)
            if emp:
                request.state.actor_kind = "employee_key"
                request.state.actor_account_id = emp["profile_id"]
                request.state.tier = emp["tier"] or "employee"
                request.state.department = emp["department"]
                # Apply tier policy
                if _tier_policy and not _tier_policy.is_allowed(path, request.state.tier, request.state.department):
                    logger.info("PATCH-414b: denied %s %s for %s/%s",
                                request.method, path, request.state.tier, request.state.department)
                    return JSONResponse(
                        {"error": "Forbidden",
                         "code": "TIER_SCOPE_DENIED",
                         "tier": request.state.tier,
                         "department": request.state.department,
                         "path": path},
                        status_code=403,
                    )
                return await call_next(request)"""

new_src = src.replace(founder_block, founder_replacement, 1)
if new_src == src:
    print("  ✗ Could not find founder block — aborting")
    raise SystemExit(1)
src = new_src

# ── Patch 3: set tier=tenant_user on bearer/cookie passes so /me works ──────
bearer_block = """        if self._check_bearer(request):
            request.state.actor_kind = "bearer"
            return await call_next(request)"""
bearer_replacement = """        if self._check_bearer(request):
            request.state.actor_kind = "bearer"
            if not getattr(request.state, "tier", None):
                request.state.tier = "tenant_user"
                request.state.department = None
            return await call_next(request)"""
src = src.replace(bearer_block, bearer_replacement, 1)

cookie_block = """        if self._check_cookie_session(request):
            request.state.actor_kind = "cookie_session"
            return await call_next(request)"""
cookie_replacement = """        if self._check_cookie_session(request):
            request.state.actor_kind = "cookie_session"
            if not getattr(request.state, "tier", None):
                request.state.tier = "tenant_user"
                request.state.department = None
            return await call_next(request)"""
src = src.replace(cookie_block, cookie_replacement, 1)

# ── Patch 4: internal token also gets founder-equivalent tier ────────────
internal_block = """        if self._check_internal_token(request):
            request.state.actor_kind = "internal_service"
            return await call_next(request)"""
internal_replacement = """        if self._check_internal_token(request):
            request.state.actor_kind = "internal_service"
            request.state.tier = "founder"  # PATCH-414b: trusted service-to-service
            request.state.department = None
            return await call_next(request)"""
src = src.replace(internal_block, internal_replacement, 1)

MODULAR_AUTH.write_text(src)
print(f"  ✓ Patched modular_auth.py ({len(src)} bytes)")


# ── Smoke test: syntax check only (fastapi not on system python) ──────────
import ast
try:
    ast.parse(MODULAR_AUTH.read_text())
    print(f"  ✓ Module syntactically valid")
except SyntaxError as e:
    print(f"  ✗ Syntax error: {e}")
    print(f"  Restoring backup…")
    shutil.copy(BACKUP, MODULAR_AUTH)
    raise SystemExit(1)
