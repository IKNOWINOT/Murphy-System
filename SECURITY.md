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

Active security enhancements are tracked in the [Security Implementation Plan](SECURITY_IMPLEMENTATION_PLAN.md), which addresses multi-agent security risks including authorization hardening, data sanitization, resource quotas, swarm communication security, bot identity verification, and anomaly detection.
