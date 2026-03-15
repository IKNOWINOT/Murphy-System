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

## Scope

This security policy covers the Murphy System core runtime and all modules in the `src/` directory. Third-party dependencies are covered by their own security policies.

## Security Enhancement Roadmap

All planned security enhancements have been implemented. The following multi-agent security controls are now operational:

- **Per-request authorization** — ownership verification on every mutating request (`src/security_plane/authorization_enhancer.py`)
- **PII sanitization** — automated detection and redaction of 8 sensitive data types in logs (`src/security_plane/log_sanitizer.py`)
- **Bot resource quotas** — per-bot and per-swarm resource limits with automatic suspension (`src/security_plane/bot_resource_quotas.py`)
- **Communication loop detection** — DFS-based cycle detection and rate limiting in swarm messaging (`src/security_plane/swarm_communication_monitor.py`)
- **Bot identity verification** — HMAC-SHA256 message signing with key revocation (`src/security_plane/bot_identity_verifier.py`)
- **Behavioral anomaly detection** — z-score analysis, resource spikes, and API pattern monitoring (`src/security_plane/bot_anomaly_detector.py`)
- **Unified security dashboard** — event aggregation, correlation, and compliance reporting (`src/security_plane/security_dashboard.py`)
