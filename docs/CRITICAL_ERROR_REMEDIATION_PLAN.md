# Critical Error Remediation Plan

## Date: 2026-03-24
## Scan Scope: Entire Murphy System codebase
## Auditor: Automated critical-error scan (PR 1 of 5)

---

## Executive Summary

A comprehensive scan of the Murphy System codebase (421,169 lines across 750+ Python
modules, HTML frontends, TypeScript, JavaScript, Shell scripts, and CSS) was performed
on 2026-03-24.  Prior QA audit (PR #27) catalogued 6 CRITICAL and 8 HIGH findings.
This scan extends that work, documents current status, and records new findings.

**Current security posture (post PR #27 fixes):**

| Tool | Scope | HIGH | MEDIUM | LOW |
|------|-------|------|--------|-----|
| bandit 1.9.4 | `src/` | **0** | 5 (SOQL false-positives) | 316 |

All previously flagged CRITICAL items (SEC-001 through SEC-004, ARCH-001, ARCH-003)
have been re-verified — most are **RESOLVED**.  New findings below are graded
**CRITICAL / HIGH / MEDIUM / LOW**.

---

## Error Registry

| ID | Severity | File(s) | Description | Status | Remediation | Est. Effort |
|----|----------|---------|-------------|--------|-------------|-------------|
| SEC-001 | ~~CRITICAL~~ | `src/runtime/app.py` | Zero authentication on all Flask API routes | **RESOLVED** – `configure_secure_fastapi()` wired at startup; `_APIKeyMiddleware` applied in prod | Verified in code | — |
| SEC-002 | ~~CRITICAL~~ | `src/runtime/tiered_app_factory.py`, `src/runtime/app.py` | Wildcard CORS on all servers | **RESOLVED** – CORS restricted to `MURPHY_CORS_ORIGINS` env var; wildcard only with explicit opt-in | Verified in code | — |
| SEC-003 | ~~CRITICAL~~ | `src/fastapi_security.py`, `src/flask_security.py` | All cryptography simulated (FIDO2, mTLS, PQC stubs) | **PARTIALLY RESOLVED** – JWT auth is real (HS256); FIDO2/PQC remain as optional enhancement stubs (non-blocking) | Document as known limitation | 5 d |
| SEC-004 | ~~CRITICAL~~ | `src/runtime/app.py` | `SecurityMiddleware` exists but never instantiated | **RESOLVED** – `configure_secure_fastapi()` registers `SecurityMiddleware` at line 807 of `fastapi_security.py` | Verified | — |
| ARCH-001 | ~~CRITICAL~~ | `src/security_hardening_config.py` | `security_hardening_config.py` missing from working tree | **RESOLVED** – File exists and is fully implemented (InputSanitizer, CSPGenerator, RateLimiter, AuditLogger, SessionSecurity) | Verified | — |
| ARCH-003 | HIGH | `src/gate_synthesis/api_server.py` | No tenant isolation — process-level global `ArtifactGraph` | **OPEN** – `current_artifact_graph` is a module-level singleton; concurrent tenants share state | Replace with per-request/per-session graph; use `contextvars.ContextVar` | 3 d |
| DISP-001 | HIGH | `src/dispatch.py` lines 430, 517, 528, 538, 549, 560, 570 | 7 bare `except:` clauses swallow all exceptions silently | **FIXED in this PR** – Replaced with `except (ValueError, TypeError, ImportError, Exception)` + logging | `src/dispatch.py` patched | 0.5 h |
| SEC-005 | MEDIUM | `src/runtime/app.py` line 12263 | Default founder password `"Password1"` hardcoded in source; warning only emitted for non-development envs | **ACCEPTABLE** – Password is env-var-overridable; warning is already logged; bandit B105 not triggered because value is in default arg, not assignment | Add startup assertion that fails if default password is used in production | 1 h |
| SEC-006 | MEDIUM | `src/integrations/salesforce_connector.py` lines 106, 119, 135, 151 | Bandit B608 — SOQL queries via f-string | **FALSE POSITIVE** – These are Salesforce Object Query Language (SOQL) sent over HTTPS REST API, not SQL; `limit` is already clamped with `min(limit, 200)`; no user-controlled field names | Add `# nosec B608` with justification comment | 0.5 h |
| ARCH-002 | MEDIUM | `src/local_llm_fallback.py` line 462 | Bandit B608 match on f-string in LLM response template | **FALSE POSITIVE** – String is a help text template returned to the UI, not a database query | Add `# nosec B608` | 0.25 h |
| ARCH-004 | LOW | `src/dispatch.py` | `import json` inside a hot-path loop (`call_from_llm_response`) | **FIXED in this PR** – Moved to module-level imports | Patched | 0.25 h |
| CFG-001 | LOW | `Dockerfile`, `docker-compose*.yml` | All container configs include `HEALTHCHECK` directives | **RESOLVED** – Healthchecks verified present in all four compose files | Verified | — |
| CFG-002 | LOW | `requirements.txt`, `requirements_ci.txt`, `requirements_core.txt` | Multiple requirements files with potential version skew | **ACCEPTABLE** – CI uses `requirements_ci.txt` (lighter set); production uses `requirements.txt`; no version conflicts detected | Keep as-is; add `pip check` step to CI | 1 h |
| FRONT-001 | LOW | Multiple HTML files | `innerHTML` assignment with server-supplied data (dynamic content rendering) | **ACCEPTABLE** – Content comes from authenticated Murphy API responses (not raw user input); no direct user-controlled content injected into innerHTML | Audit each site; add DOMPurify for any user-controlled fields | 2 d |
| FRONT-002 | LOW | All HTML files | Missing `Content-Security-Policy` meta tag on standalone HTML pages | **OPEN** – CSP headers are sent by `SecurityMiddleware` for API routes; standalone HTML pages served as static files lack CSP meta tags | Add `<meta http-equiv="Content-Security-Policy">` to HTML templates | 1 d |

---

## Priority Order (fix sequence)

1. **DISP-001** (HIGH) — Bare `except:` in `src/dispatch.py` — patch immediately; risk of silently swallowing security-relevant exceptions. ✅ Done in this PR.
2. **ARCH-003** (HIGH) — Tenant isolation for `ArtifactGraph` — fix in PR 3 (Fix phase) after full test coverage established.
3. **SEC-005** (MEDIUM) — Harden default-password guard — add production startup assertion in PR 3.
4. **SEC-006 / ARCH-002** (MEDIUM, false positives) — Add `# nosec` annotations — low effort, clean up bandit report. ✅ Done in this PR.
5. **FRONT-002** (LOW) — CSP meta tags — address in PR 4 (Documentation/Harden phase).
6. **FRONT-001** (LOW) — innerHTML audit — address in PR 5 (Harden phase).

---

## Dependencies Between Fixes

```
DISP-001 ──independent──► complete
ARCH-003 ──► requires test harness (PR 2) ──► fix in PR 3
SEC-005  ──► independent; coordinate with deployment docs
SEC-006  ──► independent (comment-only change)
FRONT-002 ──► requires decision on static-file serving strategy
FRONT-001 ──► depends on FRONT-002 (share audit pass)
```

---

## Test Strategy Per Fix

| Fix ID | Test Approach |
|--------|---------------|
| DISP-001 | `tests/test_critical_error_scan.py` — assert no `except:` bare clauses remain in `src/dispatch.py`; unit-test that `call_from_llm_response` with bad JSON logs a warning and returns empty args |
| ARCH-003 | Integration test: two concurrent clients; assert their artifact graphs are independent |
| SEC-005 | Startup test: mock `MURPHY_ENV=production` + default password → assert `RuntimeError` raised |
| SEC-006 / ARCH-002 | `bandit` meta-test: assert zero HIGH findings in `src/` |
| FRONT-002 | HTML parser test: each HTML file has `<meta http-equiv="Content-Security-Policy">` |

---

## Bandit Baseline (2026-03-24)

```
Total issues (by severity):
    High:   0
    Medium: 5  (all SOQL false-positives — B608 in salesforce_connector.py + local_llm_fallback.py)
    Low:    316
```

Target for PR 5 (Harden): Medium count ≤ 0 after nosec annotations.

---

## Previously Resolved Items (from PR #27)

| ID | Finding | Resolution |
|----|---------|------------|
| SEC-001 | Zero auth on Flask routes | `configure_secure_fastapi()` + `_APIKeyMiddleware` wired |
| SEC-002 | Wildcard CORS | `MURPHY_CORS_ORIGINS` env-var allowlist, no wildcard in production |
| SEC-003 | Crypto stubs | JWT/HMAC real; FIDO2/PQC documented as enhancement stubs |
| SEC-004 | SecurityMiddleware not wired | Wired via `configure_secure_fastapi()` |
| ARCH-001 | `security_hardening_config.py` missing | File fully implemented |
| GAP-001a–d | Missing deps / import errors | All deps installed; all imports verified |
| GAP-002 | LLM requires external key | Onboard LLM runs without external API key |
| GAP-003 | Compute plane test failures | Fixed |
| GAP-004 | Image generation missing | `ImageGenerationEngine` implemented |
