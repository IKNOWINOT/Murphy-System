# Murphy System — Engineering Audit
**Team:** Steve (Agent) + Corey (Founder)  
**Date:** 2026-04-08  
**Standard:** Act like a software team finishing what exists for production.

---

## Audit Methodology

For each module:
1. Does it do what it was designed to do?
2. What exactly is it supposed to do?
3. What conditions are possible?
4. Does the test profile reflect the full range?
5. What is the expected result at all points of operation?
6. What is the actual result?
7. If broken — work back from symptoms to root cause.
8. Has ancillary code/docs been updated?
9. Has hardening been applied?
10. Has the module been commissioned after fixes?

---

## MODULE 1: Auth Middleware Stack
**File:** `src/runtime/app.py` (~line 12655) + `src/fastapi_security.py`  
**Label:** `PATCH-001-AUTH-MIDDLEWARE`

### 1. Does it do what it was designed to do?
**NO.** Every authenticated user gets 401 on every `/api/*` call that isn't in a narrow exempt list.

### 2. What is it supposed to do?
Enforce authentication on all `/api/*` routes while allowing:
- Public routes (login, signup, health, demo)
- Logged-in users via session cookie OR API key

### 3. What conditions are possible?
- Unauthenticated user hits `/api/*` → should get 401
- Logged-in user (session cookie) hits `/api/*` → should pass through
- API-key client hits `/api/*` → should pass through
- Public route hit → should always pass through

### 4. Does the test profile reflect all conditions?
**NO.** Tests run with `MURPHY_ENV=development` which disables `SecurityMiddleware` auth checks entirely. The `_APIKeyMiddleware` bug is never exercised in tests.

### 5. Expected result
Logged-in users can reach all authenticated endpoints. Session cookie is respected.

### 6. Actual result
`_APIKeyMiddleware` runs FIRST (Starlette LIFO stack). It only accepts `x-api-key` header. Session cookie is never checked. Every browser user gets:
```json
{"success": false, "error": {"code": "AUTH_REQUIRED", "message": "Valid X-API-Key header required"}}
```

### 7. Root cause
**Double middleware registration — LIFO conflict.**

Middleware stack (LIFO — last added runs first):
```
[1] _APIKeyMiddleware   ← added at app.py:~12700, runs FIRST, X-API-Key only
[2] SecurityMiddleware  ← added by configure_secure_fastapi(), has full cookie/JWT/key support  
[3] DLP/Risk/RBAC       ← security plane
[4] CORSMiddleware      ← innermost
```

`SecurityMiddleware` in `fastapi_security.py` already does everything `_APIKeyMiddleware` does — plus session cookies, JWT, Bearer tokens, rate limiting, CSRF, security headers, and brute-force protection. `_APIKeyMiddleware` is a redundant, incomplete re-implementation that shadows the correct one.

### 8. Fix
**Remove `_APIKeyMiddleware` entirely from `app.py`.** `SecurityMiddleware` handles all auth. `register_session_validator()` is already wired correctly.

### 9. Hardening impact
Removing `_APIKeyMiddleware` does NOT reduce security. `SecurityMiddleware` is strictly more capable.

---

## MODULE 2: Account Profile API
**File:** `src/runtime/app.py` (~line 11710)  
**Label:** `PATCH-002-ACCOUNT-PROFILE`

### 1. Does it do what it was designed to do?
**NO.** Returns the same hardcoded global dict to every caller regardless of who is logged in.

### 2. What is it supposed to do?
Return the profile of the currently authenticated user.

### 3. What conditions are possible?
- Owner/admin calls → returns their real profile with role/tier
- Regular user calls → returns their profile
- Unauthenticated call → returns 401

### 4. Does the test profile reflect all conditions?
**NO.** Tests don't verify the profile response is user-scoped.

### 5. Expected result
```json
{"success": true, "email": "cpost@murphy.systems", "role": "owner", "tier": "enterprise", ...}
```

### 6. Actual result (when auth fixed)
```json
{"success": true, "id": "acct_default", "email": "cpost@murphy.systems", "name": "Murphy Admin", "plan": "free", ...}
```
Same response for every user. Plan always shows "free" regardless of subscription.

### 7. Root cause
`_account_data` is a module-level global dict initialized at startup. `account_profile()` and `account_update_profile()` read/write this shared state. Not user-scoped.

### 8. Fix
Read from `_user_store` via `_get_account_from_session()`. Return 401 if no session. Map `tier`→`plan` fields correctly.

---

## MODULE 3: Admin Panel Routing
**File:** `src/runtime/app.py` (~line 10881)  
**Label:** `PATCH-003-ADMIN-ROUTING`

### 1. Does it do what it was designed to do?
**PARTIAL.** `/ui/admin` → redirects to `/ui/login` (correct, requires auth). But the admin panel then calls `/api/admin/*` which gets blocked by middleware (Module 1). So the UI loads but is completely non-functional.

### 2. What is it supposed to do?
Admin users (role=admin or role=owner) can access user management, org management, session management, and audit logs.

### 3. What conditions are possible?
- Owner/admin user visits `/ui/admin` → sees full admin panel
- Regular user → redirected to `/ui/login` (actually redirected to admin then to login, which is fine)
- Unauthenticated → redirected to login

### 4. Fix
Module 1 fix unblocks all admin API calls. The admin panel HTML itself is correct.

---

## MODULE 4: User Data Persistence
**File:** `src/runtime/app.py` (session/user stores)  
**Label:** `PATCH-004-PERSISTENCE`

### 1. Does it do what it was designed to do?
**PARTIAL.** `_user_store` and `_email_to_account` are in-memory dicts. `_session_store` has Redis-backed persistence. But user accounts are lost on every restart.

### 2. What is it supposed to do?
Users who sign up should still exist after a server restart.

### 3. Root cause
`_SQLiteUserStore` exists in the code but `_user_store` is a plain dict. The SQLite backend is initialized but the signup/login handlers write to the in-memory dict, not the SQLite store.

### 4. Fix (Phase 2)
Wire `_user_store` writes through `_SQLiteUserStore`. Out of scope for Patch 1 — Patch 1 focuses on auth middleware to unblock testing.

---

## PATCH 1 SCOPE

**Goal: Make it possible to log in and use the system as any user level.**

Changes:
1. Remove `_APIKeyMiddleware` from `app.py` (root cause of all 401s)
2. Fix `account_profile` to be session-scoped
3. Fix `account_update_profile` to be session-scoped
4. Add `/api/auth/session-token` to `SecurityMiddleware` exempt list (already in _APIKeyMiddleware exempt but not in fastapi_security public routes list)

**Files changed:**
- `src/runtime/app.py`

**Not in Patch 1:**
- User persistence (needs separate migration work)
- Boards/CRM in-memory storage
- requirements.lock (already done separately)
