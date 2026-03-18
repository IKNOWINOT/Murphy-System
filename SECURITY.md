# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them responsibly:

1. **Email:** Send details to the project maintainers via GitHub private vulnerability reporting
2. **GitHub:** Use the [Security Advisories](https://github.com/IKNOWINOT/Murphy-System/security/advisories) feature to report privately

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment:** Within 48 hours
- **Initial Assessment:** Within 1 week
- **Fix Timeline:** Depends on severity (critical: ASAP, high: 1-2 weeks, medium: next release)

## Security Best Practices

When deploying Murphy System:

- Never commit `.env` files or API keys to version control
- Use strong, unique API keys for production
- Run behind a reverse proxy (nginx/Caddy) in production
- Enable HTTPS for all external connections
- Restrict CORS origins to your known domains
- Review the [Deployment Guide](Murphy%20System/DEPLOYMENT_GUIDE.md) for hardening steps

## Authentication Architecture

Murphy System uses **session-based authentication** via HttpOnly cookies:

| Mechanism | Where set | Where validated |
|-----------|-----------|-----------------|
| `murphy_session` cookie | `/api/auth/signup`, `/api/auth/login`, OAuth callback | `SecurityMiddleware` via `register_session_validator()` |
| `Authorization: Bearer <token>` | Client `localStorage.murphy_session_token` | `SecurityMiddleware` → `_authenticate_request()` |
| `X-API-Key` header | Environment / dashboard | `SecurityMiddleware` → `validate_api_key()` |

**Password hashing:** bcrypt (cost factor from `bcrypt.gensalt()`) — never stored in plaintext.

**Session tokens:** cryptographically-random 32-byte URL-safe base64 strings from
`secrets.token_urlsafe(32)`. Stored in an in-memory dict (`_session_store`, guarded by
`threading.Lock`). Replace with Redis or a database for multi-process deployments.

**Cookie flags:** `HttpOnly=True` (XSS protection), `SameSite=lax` (CSRF protection),
`Secure=True` in staging/production, 24-hour `Max-Age`.

## Scope

This security policy covers the Murphy System core runtime and all modules in the `src/` directory. Third-party dependencies are covered by their own security policies.

## Cryptographic Hash Policy

Murphy System enforces **SHA-256 minimum** for all hashing in production code paths:

| Use Case | Algorithm | Module |
|----------|-----------|--------|
| Audit log hash-chain | SHA-256 | `src/audit_logging_system.py` |
| Webhook HMAC signing | HMAC-SHA256 | `src/webhook_dispatcher.py` |
| Bot identity verification | HMAC-SHA256 | `src/security_plane/bot_identity_verifier.py` |
| Commissioning test IDs | SHA-256 | `src/cutsheet_engine.py` |
| Onboarding dedup hash | SHA-256 | `src/runtime/murphy_system_core.py` |

**Prohibited algorithms:** MD5 and SHA-1 are not used in production code for any security-relevant or identifier-generation purpose. Test code may use these algorithms for negative-validation only. The codebase was scanned with bandit and AST analysis to verify compliance (round 55).

## Security Enhancement Roadmap

All planned security enhancements have been implemented. The following multi-agent security controls are now operational:

- **Per-request authorization** — ownership verification on every mutating request (`src/security_plane/authorization_enhancer.py`)
- **PII sanitization** — automated detection and redaction of 8 sensitive data types in logs (`src/security_plane/log_sanitizer.py`)
- **Bot resource quotas** — per-bot and per-swarm resource limits with automatic suspension (`src/security_plane/bot_resource_quotas.py`)
- **Communication loop detection** — DFS-based cycle detection and rate limiting in swarm messaging (`src/security_plane/swarm_communication_monitor.py`)
- **Bot identity verification** — HMAC-SHA256 message signing with key revocation (`src/security_plane/bot_identity_verifier.py`)
- **Behavioral anomaly detection** — z-score analysis, resource spikes, and API pattern monitoring (`src/security_plane/bot_anomaly_detector.py`)
- **Unified security dashboard** — event aggregation, correlation, and compliance reporting (`src/security_plane/security_dashboard.py`)
