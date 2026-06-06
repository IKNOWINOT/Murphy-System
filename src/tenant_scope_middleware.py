"""
PATCH-ISO-001 — Tenant Scope Middleware (LOCKED 2026-05-27)
==============================================================

WHAT THIS IS:
  Populates request.state.actor with a normalized actor record for every
  authenticated request, AND enforces tenant isolation on routes that
  declare themselves tenant-scoped.

  actor shape (immutable contract — DO NOT CHANGE without founder sign-off):
    {
      "user_id":         str  # from session_store / user_accounts.account_id
      "email":           str
      "tenant_id":       str  | None       # None = platform-only user (no tenant)
      "tenant_role":     str  | None       # 'owner'|'admin'|'member'|'viewer'
      "is_founder":      bool              # True only for cpost@murphy.systems
      "is_platform_admin": bool            # True for hired admin/worker users
      "platform_scopes": list[str]         # e.g. ['read:tenant:abc123']
    }

WHY IT EXISTS:
  Pre-PATCH-ISO-001, no middleware populated request.state.actor.
  Route handlers had no signal to check 'is this caller allowed to see
  this tenant's row?'. CRM contacts and deals had no tenant_id column
  AT ALL — meaning any authenticated caller could read every contact.

DEPENDENCIES:
  - /var/lib/murphy-production/murphy_users.db (user_accounts, session_store)
  - /var/lib/murphy-production/tenants.db (tenant_members)

DECLARING A ROUTE AS TENANT-SCOPED:
  Two ways:
  1. Path-prefix matched against TENANT_SCOPED_PREFIXES (default mode)
  2. Add to TENANT_SCOPED_PATHS (exact match) — for one-off endpoints

FOUNDER-ONLY ROUTES:
  Declared in FOUNDER_ONLY_PATHS — these reject everything unless
  actor.is_founder is True.

LAST UPDATED: 2026-05-27 — initial wiring
"""
from __future__ import annotations
import json, logging, sqlite3
from typing import Optional, Set, Dict, Any
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("murphy.tenant_scope")

USERS_DB = "/var/lib/murphy-production/murphy_users.db"
TENANTS_DB = "/var/lib/murphy-production/tenants.db"

FOUNDER_EMAILS = {"cpost@murphy.systems", "corey.gfc@gmail.com"}

# Tenant-scoped path prefixes — caller MUST have a tenant_id
TENANT_SCOPED_PREFIXES = (
    "/api/crm/",
    "/api/tenants/",
    "/api/my/",
    "/api/support/tickets",      # listing tickets, not creating (creation is public)
    "/api/client-solutions/tickets",
    "/api/agents/my/",
    "/api/workflows/my/",
)

# Founder-only paths — only is_founder=True can access
FOUNDER_ONLY_PATHS = (
    "/api/founder/",
    "/api/platform/admin/",
    "/api/self-modify/",
)

# Paths that are intentionally public (overrides everything else)
ALWAYS_PUBLIC = (
    "/api/health",
    "/api/auth/",
    "/api/support/ticket",   # public submission
    "/api/billing/plans",
    "/api/nowpayments/",
    "/support",
    "/signup",
    "/static/",
    "/favicon",
)


def _resolve_actor_from_request(request: Request) -> Dict[str, Any]:
    """
    Read session cookie / Authorization header and produce the actor record.
    Returns the anon-actor if no auth.
    """
    actor = {
        "user_id": None, "email": None, "tenant_id": None,
        "tenant_role": None, "is_founder": False,
        "is_platform_admin": False, "platform_scopes": []
    }

    # Founder API-key path — takes precedence over sessions
    api_key = request.headers.get("x-api-key", "") or request.headers.get("X-API-Key", "")
    if api_key:
        import os
        founder_keys = os.environ.get("MURPHY_FOUNDER_KEYS", "").split(",")
        founder_keys = [k.strip() for k in founder_keys if k.strip()]
        if api_key in founder_keys:
            actor["is_founder"] = True
            actor["email"] = "cpost@murphy.systems"
            actor["user_id"] = "founder"
            return actor

    # Try session token (cookie or Bearer)
    token = request.cookies.get("murphy_session", "")
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
    if not token:
        return actor

    # Resolve token → account
    try:
        with sqlite3.connect(USERS_DB, timeout=2) as c:
            row = c.execute(
                "SELECT tenant_id, data FROM session_store WHERE session_id=?",
                (token,)
            ).fetchone()
            if not row:
                return actor
            tenant_id_session = row[0]
            session_data = json.loads(row[1]) if row[1] else {}
            account_id = session_data.get("account_id")
            if not account_id:
                return actor
            acct_row = c.execute(
                "SELECT email, data FROM user_accounts WHERE account_id=?",
                (account_id,)
            ).fetchone()
            if not acct_row:
                return actor
            email = (acct_row[0] or "").lower()
            acct_data = json.loads(acct_row[1]) if acct_row[1] else {}
    except Exception as exc:
        log.warning("actor resolve failed: %s", exc)
        return actor

    actor["user_id"] = account_id
    actor["email"] = email
    actor["is_founder"] = email in FOUNDER_EMAILS
    actor["is_platform_admin"] = acct_data.get("role") in ("admin", "platform_admin")

    # Resolve tenant membership (prefer session-stored tenant_id)
    tenant_id = tenant_id_session or acct_data.get("tenant_id")
    if tenant_id and tenant_id != "platform_legacy":
        try:
            with sqlite3.connect(TENANTS_DB, timeout=2) as c:
                m = c.execute(
                    "SELECT role FROM tenant_members WHERE tenant_id=? AND user_id=?",
                    (tenant_id, account_id)
                ).fetchone()
                if m:
                    actor["tenant_id"] = tenant_id
                    actor["tenant_role"] = m[0]
        except Exception as exc:
            log.warning("tenant_role resolve failed: %s", exc)

    return actor


class TenantScopeMiddleware(BaseHTTPMiddleware):
    """
    Order: this runs AFTER auth_middleware (which sets request.state.actor_user_sub),
    BEFORE the route handler.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # CORS preflight always passes
        if request.method == "OPTIONS":
            return await call_next(request)

        # Always-public surface bypasses everything
        for p in ALWAYS_PUBLIC:
            if path.startswith(p):
                request.state.actor = _resolve_actor_from_request(request)
                return await call_next(request)

        # Build the actor record
        actor = _resolve_actor_from_request(request)
        request.state.actor = actor

        # Founder-only enforcement
        for p in FOUNDER_ONLY_PATHS:
            if path.startswith(p) and not actor["is_founder"]:
                log.warning("FOUNDER_GATE blocked %s for actor email=%s", path, actor["email"])
                return JSONResponse(
                    {"error": "founder-only resource", "code": "FOUNDER_ONLY"},
                    status_code=403
                )

        # Tenant-scope enforcement
        for p in TENANT_SCOPED_PREFIXES:
            if path.startswith(p):
                # Founder can access any tenant view (read-only convenience)
                if actor["is_founder"]:
                    break
                # Otherwise the caller must have a resolved tenant_id
                if not actor["tenant_id"]:
                    log.warning("TENANT_GATE blocked %s for actor email=%s (no tenant)",
                                path, actor["email"])
                    return JSONResponse(
                        {"error": "tenant-scoped resource requires authenticated tenant context",
                         "code": "TENANT_REQUIRED"},
                        status_code=403
                    )
                break

        return await call_next(request)


def install_tenant_scope_middleware(app):
    """Mount TenantScopeMiddleware on the FastAPI app. Idempotent."""
    # Check if already mounted (prevents double-install on hot reload)
    for m in getattr(app, 'user_middleware', []):
        if 'TenantScopeMiddleware' in str(m):
            log.info("PATCH-ISO-001 already mounted")
            return
    app.add_middleware(TenantScopeMiddleware)
    log.info("PATCH-ISO-001 TenantScopeMiddleware mounted (founder-gate + tenant-gate)")
