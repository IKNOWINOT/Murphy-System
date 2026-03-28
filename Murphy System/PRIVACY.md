# Privacy Policy — Murphy System

**Last Updated:** 2026-03-08
**License:** BSL 1.1

---

## Overview

Murphy System is an AI-powered business automation platform. This document
describes what data Murphy collects, why, how it is stored, and how long
it is retained.

## Data We Collect

### 1. User Profile Data

| Field         | Purpose                                      | Retention          |
|---------------|----------------------------------------------|--------------------|
| `user_id`     | Unique identifier for session continuity     | Account lifetime   |
| `email`       | Email validation during signup               | Account lifetime   |
| `name`        | Display name in terminal UI                  | Account lifetime   |
| `role`        | RBAC permission assignment                   | Account lifetime   |
| `org_id`      | Multi-tenant workspace isolation             | Account lifetime   |

### 2. EULA Acceptance Records

| Field         | Purpose                                      | Retention          |
|---------------|----------------------------------------------|--------------------|
| `record_id`   | Audit trail for legal compliance             | Indefinite (legal) |
| `ip_address`  | Fraud prevention, legal compliance           | Redacted in logs   |
| `user_agent`  | Device identification for support            | Redacted in logs   |
| `accepted_at` | Timestamp of acceptance                      | Indefinite (legal) |

### 3. API Keys and Credentials

| Field            | Purpose                                   | Retention          |
|------------------|-------------------------------------------|--------------------|
| `api_key` hashes | Authentication verification               | Account lifetime   |
| LLM provider keys | Connecting to LLM services on user behalf | Encrypted at rest  |

**Security:** All API keys are stored encrypted via `SecureKeyManager` using
Fernet symmetric encryption. Keys are never logged in plaintext. Log output
redacts keys to the format `di_...XXXX` or `sk-...XXXX`.

## Data We Do NOT Collect

- We do **not** collect browsing history or tracking cookies.
- We do **not** sell or share personal data with third parties.
- We do **not** use personal data for advertising.
- We do **not** store full API keys in plaintext.

## Log Redaction

All logging pipelines apply PII redaction via `LogSanitizer`
(`src/security_plane/log_sanitizer.py`):

| Data Type    | Redaction Format         |
|--------------|--------------------------|
| Email        | `u***@domain.com`        |
| Phone        | `[REDACTED_PHONE]`       |
| IP Address   | `192.168.xxx.xxx`        |
| API Key      | `[REDACTED_API_KEY]`     |
| Password     | `[REDACTED_PASSWORD]`    |
| Auth Token   | `[REDACTED_TOKEN]`       |
| SSN          | `[REDACTED_SSN]`         |
| Credit Card  | `[REDACTED_CC]`          |

## Third-Party API Data Sharing

Murphy System integrates with external APIs (DeepInfra, OpenAI, Anthropic,
HeyGen, Tavus, Vapi, Coinbase, Twilio, SendGrid, Stripe, Cloudflare).
When using these integrations:

- Only the minimum data required for the API call is transmitted.
- API keys for third-party services are stored encrypted and never logged.
- Each integration respects the provider's Terms of Service.
- Users must provide their own API keys; Murphy does not proxy or resell access.

## Data Deletion

Users may request deletion of their profile data by contacting the system
administrator. EULA acceptance records are retained for legal compliance
but IP addresses and user agents within those records are redacted.

## Security Controls

- **Encryption at rest**: Fernet symmetric encryption for credentials
- **Encryption in transit**: TLS/HTTPS for all external API calls
- **Access control**: RBAC with role-based permission gating
- **Audit logging**: Bounded, in-memory audit log with PII redaction
- **DLP**: `SensitiveDataClassifier` scans data pipelines for PII leaks

## Contact

For privacy questions, contact the repository maintainers at:
https://github.com/IKNOWINOT/Murphy-System/issues
