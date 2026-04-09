#!/usr/bin/env python3
"""
Murphy System — PATCH-001 Auth Middleware + Account Profile
=============================================================
Label:    PATCH-001-AUTH-MIDDLEWARE / PATCH-002-ACCOUNT-PROFILE
Date:     2026-04-08
Author:   Steve (AI engineer)
Reviewed: Corey Post

ENGINEERING AUDIT SUMMARY
--------------------------
Questions asked per module per team standard:

MODULE: Auth Middleware Stack
  Designed to do:  Enforce auth on /api/* while allowing public routes + logged-in users
  Does it do that: NO — every browser user gets 401 on every /api/* call
  Root cause:      _APIKeyMiddleware runs FIRST (Starlette LIFO) and only accepts
                   x-api-key header. SecurityMiddleware (which handles session cookies)
                   never runs for protected routes.
  Fix:             Remove _APIKeyMiddleware. SecurityMiddleware is strictly a superset.
  Hardening:       SecurityMiddleware adds rate limiting, CSRF, brute-force protection,
                   security headers, DLP, RBAC — no security regression.

MODULE: /api/account/profile
  Designed to do:  Return the logged-in user's profile
  Does it do that: NO — returns global _account_data dict, same data for every caller
  Root cause:      Handler ignores request/session entirely; reads shared module-level dict
  Fix:             Read from _user_store via _get_account_from_session()

MODULE: /api/auth/session-token  
  Designed to do:  Mirror HttpOnly cookie → localStorage for OAuth users (frontend use)
  Does it do that: Was only exempted via _APIKeyMiddleware (now removed)
  Fix:             Add to SecurityMiddleware _PUBLIC_EXACT list (handler self-validates)

ROLLBACK
--------
  cp /opt/Murphy-System/src/runtime/app.py.patch001.bak /opt/Murphy-System/src/runtime/app.py
  cp /opt/Murphy-System/src/fastapi_security.py.patch001.bak /opt/Murphy-System/src/fastapi_security.py
  systemctl restart murphy-production

COMMISSIONING VERIFICATION
--------------------------
After restart, run:

  # Login and get session cookie
  curl -s -X POST https://murphy.systems/api/auth/login \\
    -H 'Content-Type: application/json' -c /tmp/verify.txt \\
    -d '{"email":"cpost@murphy.systems","password":"YOUR_PASSWORD"}'

  # Profile should return real user data with role/tier
  curl -s -b /tmp/verify.txt https://murphy.systems/api/account/profile

  # Admin panel should return user list
  curl -s -b /tmp/verify.txt https://murphy.systems/api/admin/users

  # Regular user should get 403 on admin routes (not 401)
  # (sign up a test user, login, verify 403 on /api/admin/*)
"""

import shutil
import sys
from pathlib import Path

APP_PY      = Path("/opt/Murphy-System/src/runtime/app.py")
SECURITY_PY = Path("/opt/Murphy-System/src/fastapi_security.py")

# ── Pre-flight ────────────────────────────────────────────────────────────
for f in [APP_PY, SECURITY_PY]:
    if not f.exists():
        print(f"ABORT: {f} not found")
        sys.exit(1)

# ── Backup ────────────────────────────────────────────────────────────────
app_bak = APP_PY.with_suffix(".py.patch001.bak")
sec_bak = SECURITY_PY.with_suffix(".py.patch001.bak")
shutil.copy2(APP_PY, app_bak)
shutil.copy2(SECURITY_PY, sec_bak)
print(f"Backup: {app_bak}")
print(f"Backup: {sec_bak}")

app_content = APP_PY.read_text()
sec_content = SECURITY_PY.read_text()
errors = []

# ════════════════════════════════════════════════════════════════════════════
# CHANGE 1: Remove _APIKeyMiddleware from app.py
# PATCH-001-AUTH-MIDDLEWARE
# ════════════════════════════════════════════════════════════════════════════

OLD_MIDDLEWARE = '''    # ══════════════════════════════════════════════════════════════════════

    from starlette.middleware.base import BaseHTTPMiddleware as _BHMW

    class _APIKeyMiddleware(_BHMW):
        """Unified API key enforcement for all /api/* routes.

        Auth, demo, and other public-facing routes are always exempt so that
        visitors can log in / sign up / use the demo even when MURPHY_API_KEY
        is configured for protecting internal API routes.
        """

        # Exact-path exemptions
        EXEMPT_PATHS = {"/api/health", "/api/info", "/api/manifest"}

        # Prefix-based exemptions — any path that starts with one of these is
        # treated as a public endpoint regardless of API key configuration.
        EXEMPT_PREFIXES = (
            "/api/auth/",    # login, signup, OAuth, password reset — must be public
            "/api/demo/",    # demo runner and deliverable generator — no login required
            "/api/system/",  # system status / health endpoints
        )

        async def dispatch(self, request: Request, call_next):
            path = request.url.path
            if path.startswith("/api/"):
                is_exempt = (
                    path in self.EXEMPT_PATHS
                    or any(path.startswith(pfx) for pfx in self.EXEMPT_PREFIXES)
                )
                if not is_exempt:
                    expected_key = os.environ.get("MURPHY_API_KEY", "") or os.environ.get("MURPHY_API_KEYS", "")
                    if expected_key:
                        # Starlette normalises header names to lowercase (RFC 7230);
                        # use lowercase "x-api-key" here to match that behaviour.
                        api_key = request.headers.get("x-api-key", "")
                        if api_key != expected_key:
                            return JSONResponse(
                                {"success": False, "error": {"code": "AUTH_REQUIRED", "message": "Valid X-API-Key header required"}},
                                status_code=401,
                            )
            return await call_next(request)

    app.add_middleware(_APIKeyMiddleware)'''

NEW_MIDDLEWARE = '''    # ── PATCH-001-AUTH-MIDDLEWARE 2026-04-08 ────────────────────────────────
    # _APIKeyMiddleware REMOVED.
    #
    # Root cause: It ran FIRST in Starlette's LIFO middleware stack and only
    # accepted the x-api-key header, causing every browser user (who sends a
    # murphy_session cookie) to receive 401 on every /api/* call.
    #
    # SecurityMiddleware (added by configure_secure_fastapi above) handles all
    # of this correctly and more: X-API-Key, Bearer JWT, Bearer session-token,
    # murphy_session cookie, rate limiting, CSRF, brute-force lockout,
    # security headers, DLP, RBAC, and risk classification.
    # ─────────────────────────────────────────────────────────────────────────'''

if OLD_MIDDLEWARE not in app_content:
    errors.append("CHANGE 1: _APIKeyMiddleware block not found — already patched or changed.")
else:
    app_content = app_content.replace(OLD_MIDDLEWARE, NEW_MIDDLEWARE, 1)
    if 'app.add_middleware(_APIKeyMiddleware)' in app_content:
        errors.append("CHANGE 1: add_middleware call still present after replacement.")
    else:
        print("✓ CHANGE 1: _APIKeyMiddleware removed from app.py")

# ════════════════════════════════════════════════════════════════════════════
# CHANGE 2: Fix /api/account/profile to be session-scoped
# PATCH-002-ACCOUNT-PROFILE
# ════════════════════════════════════════════════════════════════════════════

OLD_PROFILE = '''    @app.get("/api/account/profile")
    async def account_profile():
        """Get account profile and subscription info."""
        return JSONResponse({"success": True, **_account_data})

    @app.put("/api/account/profile")
    async def account_update_profile(request: Request):
        """Update account profile."""
        body = await request.json()
        for key in ("name", "email"):
            if body.get(key):
                _account_data[key] = body[key]
        _account_data["updated_at"] = _now_iso()
        return JSONResponse({"success": True, **_account_data})'''

NEW_PROFILE = '''    @app.get("/api/account/profile")
    async def account_profile(request: Request):
        """Get account profile and subscription info.

        PATCH-002-ACCOUNT-PROFILE 2026-04-08:
        Was returning a global _account_data dict — same hardcoded response
        for every caller regardless of who was logged in. Now reads from
        _user_store via the session token to return per-user data.
        """
        account = _get_account_from_session(request)
        if account is None:
            return JSONResponse(
                {"success": False, "error": {"code": "AUTH_REQUIRED", "message": "Authentication required"}},
                status_code=401,
            )
        profile = {
            "success":         True,
            "id":              account.get("account_id", ""),
            "email":           account.get("email", ""),
            "name":            account.get("full_name", account.get("name", "")),
            "full_name":       account.get("full_name", ""),
            "job_title":       account.get("job_title", ""),
            "company":         account.get("company", ""),
            "role":            account.get("role", "user"),
            "tier":            account.get("tier", "free"),
            "plan":            account.get("tier", "free"),
            "plan_name":       account.get("tier", "free").title() + " Tier",
            "email_validated": account.get("email_validated", False),
            "created_at":      account.get("created_at", ""),
            "updated_at":      account.get("updated_at", ""),
        }
        # Merge legacy billing fields from _account_data without overwriting real values
        for k, v in _account_data.items():
            if k not in profile and k != "id":
                profile[k] = v
        return JSONResponse(profile)

    @app.put("/api/account/profile")
    async def account_update_profile(request: Request):
        """Update account profile.

        PATCH-002-ACCOUNT-PROFILE 2026-04-08:
        Was writing to global _account_data (shared across all users).
        Now writes to the caller's own record in _user_store.
        """
        account = _get_account_from_session(request)
        if account is None:
            return JSONResponse(
                {"success": False, "error": {"code": "AUTH_REQUIRED", "message": "Authentication required"}},
                status_code=401,
            )
        body = await request.json()
        updatable = ("full_name", "name", "job_title", "company")
        with _session_lock:
            user_rec = _user_store.get(account.get("account_id", ""))
            if user_rec:
                for key in updatable:
                    if body.get(key) is not None:
                        user_rec[key] = body[key]
                user_rec["updated_at"] = _now_iso()
        # Keep _account_data in sync for any downstream readers not yet migrated
        for key in updatable:
            if body.get(key) is not None:
                _account_data[key] = body[key]
        _account_data["updated_at"] = _now_iso()
        return JSONResponse({"success": True, "message": "Profile updated"})'''

if OLD_PROFILE not in app_content:
    errors.append("CHANGE 2: account_profile block not found.")
else:
    app_content = app_content.replace(OLD_PROFILE, NEW_PROFILE, 1)
    print("✓ CHANGE 2: account_profile and account_update_profile fixed (session-scoped)")

# ════════════════════════════════════════════════════════════════════════════
# CHANGE 3: Add /api/auth/session-token to SecurityMiddleware public routes
# PATCH-001-AUTH-MIDDLEWARE (ancillary)
# ════════════════════════════════════════════════════════════════════════════

OLD_PUBLIC = '''    _PUBLIC_EXACT = frozenset({
        "/api/health",
        "/api/manifest",
        "/api/info",
        "/api/ui/links",
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/register",
        "/api/auth/signup",
        "/api/auth/verify-email",
        "/api/auth/resend-verification",
        "/api/auth/register-free",
        "/api/auth/callback",
        "/api/auth/providers",
        "/api/usage/daily",
    })'''

NEW_PUBLIC = '''    _PUBLIC_EXACT = frozenset({
        "/api/health",
        "/api/manifest",
        "/api/info",
        "/api/ui/links",
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/register",
        "/api/auth/signup",
        "/api/auth/verify-email",
        "/api/auth/resend-verification",
        "/api/auth/register-free",
        "/api/auth/callback",
        "/api/auth/providers",
        "/api/usage/daily",
        # PATCH-001-AUTH-MIDDLEWARE 2026-04-08: was only in _APIKeyMiddleware exempt list
        # (now removed). Handler self-validates the cookie; listing here lets it
        # reach the handler without SecurityMiddleware blocking it first.
        "/api/auth/session-token",
    })'''

if OLD_PUBLIC not in sec_content:
    errors.append("CHANGE 3: _PUBLIC_EXACT block not found in fastapi_security.py.")
else:
    sec_content = sec_content.replace(OLD_PUBLIC, NEW_PUBLIC, 1)
    print("✓ CHANGE 3: /api/auth/session-token added to SecurityMiddleware public routes")

# ── Error check ───────────────────────────────────────────────────────────
if errors:
    print("\n⚠ ERRORS — patch NOT applied:")
    for e in errors:
        print(f"  • {e}")
    sys.exit(1)

# ── Write files ───────────────────────────────────────────────────────────
APP_PY.write_text(app_content)
SECURITY_PY.write_text(sec_content)

print("\n✅ PATCH-001 applied successfully.")
print("\nRestart the service:")
print("  systemctl restart murphy-production")
print("\nCommission (verify after restart):")
print("  curl -s -X POST https://murphy.systems/api/auth/login \\")
print("    -H 'Content-Type: application/json' -c /tmp/v.txt \\")
print("    -d '{\"email\":\"cpost@murphy.systems\",\"password\":\"YOUR_PASS\"}'")
print("  curl -s -b /tmp/v.txt https://murphy.systems/api/account/profile")
print("  curl -s -b /tmp/v.txt https://murphy.systems/api/admin/users")
print("\nRollback:")
print(f"  cp {app_bak} {APP_PY} && cp {sec_bak} {SECURITY_PY}")
print("  systemctl restart murphy-production")
