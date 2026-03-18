# Security Policy

<!--
  Copyright © 2020 Inoni Limited Liability Company
  Creator: Corey Post
  License: BSL 1.1 (Business Source License 1.1)
-->

**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

---

## Supported Versions

Only the current stable release receives security patches. We recommend always running the latest version.

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅ Active support |
| < 1.0   | ❌ No longer supported |

---

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability in the Murphy System, please **do not open a public GitHub issue**. Instead, follow the responsible disclosure process below.

### How to Report

1. **Email:** Send a detailed report to **security@inoni.io**
   - Subject line: `[SECURITY] Murphy System — <brief description>`
   - Include: affected version, reproduction steps, potential impact, and any suggested mitigations.

2. **PGP-encrypted reports (optional):**
   Our PGP public key is available at `https://inoni.io/.well-known/security.asc` (placeholder — key forthcoming).  
   Fingerprint: `[PGP KEY FINGERPRINT PLACEHOLDER]`

3. **GitHub private vulnerability reporting:**
   You may also use GitHub's [private security advisory](https://github.com/Murphy-System/Murphy-System/security/advisories/new) feature.

---

## Response Timeline

| Stage | Target |
|-------|--------|
| Initial acknowledgement | Within **48 hours** |
| Triage and severity assessment | Within **5 business days** |
| Patch / mitigation for critical issues | Within **14 days** |
| Patch / mitigation for high issues | Within **30 days** |
| Public disclosure | Coordinated with reporter after patch is available |

We follow a coordinated disclosure model. We will work with you to agree on a disclosure date that allows users adequate time to upgrade.

---

## Scope

The following are **in scope** for security testing:

- `murphy_system_1.0_runtime.py` — thin entry-point (delegates to `src/runtime/`)
- `src/runtime/app.py` — FastAPI application factory and all API endpoints
- `src/runtime/murphy_system_core.py` — MurphySystem orchestration class
- `src/fastapi_security.py` — Authentication, CORS, rate limiting
- `src/` — All source modules
- `bots/` — Bot modules and agents
- Docker and Kubernetes deployment configurations

The following are **out of scope**:

- Third-party LLM provider APIs (Groq, OpenAI, Anthropic) — report those to the respective provider
- Social engineering attacks against Inoni LLC employees
- Physical security
- Denial-of-service attacks against our infrastructure (rate-limit bypass testing against your own local instance is fine)
- Bugs in dependencies (report those upstream; notify us if the vulnerability directly affects Murphy System)

---

## Security Architecture

Murphy System implements the following controls (see `docs/QA_AUDIT_REPORT.md` for details):

| Control | Implementation |
|---------|---------------|
| Authentication | Session cookie (`murphy_session`) or `Authorization: Bearer <session_token>` or `X-API-Key`; enforced in `src/fastapi_security.py` via `SecurityMiddleware` |
| Session management | bcrypt-hashed passwords; `secrets.token_urlsafe(32)` session tokens stored in in-memory dict guarded by `threading.Lock`; HttpOnly + SameSite=lax + Secure cookies |
| Authorization | Scope-based access; production mode requires `MURPHY_API_KEYS` |
| CORS | Origin allowlist via `MURPHY_CORS_ORIGINS`; no wildcard `*` |
| Rate limiting | Token-bucket per IP/key; configurable via env vars |
| Input sanitization | Request body validation via Pydantic; iterative path-traversal stripping in `src/input_validation.py` (CWE-22 defence) |
| Security headers | `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security` injected by middleware |
| Secrets | API keys never logged; masked in `/api/llm/configure` responses; warning emitted when key stored in `os.environ` |
| Audit logging | Every task execution generates an immutable `audit_id` |
| API key comparison | Constant-time `hmac.compare_digest` used in both Flask and FastAPI validators (CWE-208 defence) |
| DLP trusted-destination | `security_plane/middleware.py` uses `urllib.parse.urlparse` for hostname extraction — substring attacks like `evil-localhost.attacker.com` are rejected (CWE-20 defence) |
| Subprocess execution | All `subprocess.run` calls use `shell=False` + `shlex.split()` (CWE-78 defence) |

---

## Known Security Gaps (Public Disclosure)

The following gaps are tracked in `STATUS.md` and are being addressed:

| ID | Gap | Status |
|----|-----|--------|
| G-006 | Formal third-party penetration test not yet completed | Planned |
| SEC-PENDING | Full security audit of bot modules | In progress |

---

## Acknowledgements

We appreciate responsible security researchers. Confirmed vulnerability reporters will be credited in the release notes (unless they prefer to remain anonymous).

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
