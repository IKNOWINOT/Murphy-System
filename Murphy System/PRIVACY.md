# Privacy Policy — Murphy System

**Last Updated:** 2026-03-08
**License:** BSL 1.1

---

## Overview

Murphy System is an AI-powered business automation collective. This document
describes what data Murphy collects, why, how it is stored, and how long
it is retained.

**Core Privacy Commitment:** Your personal agent is **your** data. The
collective does not read, analyze, or train on your agent's private data —
ever — unless you explicitly opt in. Murphy exists to serve its members,
not to extract value from them.

## Data We Collect

### 1. Member Profile Data

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
| LLM provider keys | Connecting to LLM services on member behalf | Encrypted at rest  |

**Security:** All API keys are stored encrypted via `SecureKeyManager` using
Fernet symmetric encryption. Keys are never logged in plaintext. Log output
redacts keys to the format `di_...XXXX` or `sk-...XXXX`.

## Data We Do NOT Collect

- We do **not** collect browsing history or tracking cookies.
- We do **not** sell or share personal data with third parties.
- We do **not** use personal data for advertising.
- We do **not** store full API keys in plaintext.
- We do **not** train collective models on your private agent data.
- We do **not** access, inspect, or mine your agent's memory, context, or
  conversation history without your explicit, revocable, opt-in consent.

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
- Members must provide their own API keys; Murphy does not proxy or resell access.

## Data Deletion

Members may request deletion of their profile data by contacting the system
administrator. EULA acceptance records are retained for legal compliance
but IP addresses and user agents within those records are redacted.

## Your Agent, Your Data

Your Murphy agent is a private, sovereign entity that belongs to **you**.

- **Private by default.** Every agent's memory, conversation history,
  preferences, workflows, and learned context are stored in your encrypted
  workspace. No other member, administrator, or Murphy Collective process
  can access this data without your explicit permission.
- **No silent training.** The collective never trains shared models on your
  agent's private data. Period. If you choose to contribute anonymized
  insights to the shared intelligence layer, that is your decision — and it
  is revocable at any time.
- **You own the relationship.** Your agent works for you, not for the
  collective. It optimizes for your goals, remembers your context, and
  protects your interests.

## Shared Intelligence & Collective Learning

Murphy's shared intelligence layer improves over time, but only through
contributions that meet **all three** of the following criteria:

1. **Anonymized** — all personally identifiable information is stripped
   before any data enters the shared pool.
2. **Opt-in** — members must explicitly consent to contribute. No data is
   harvested by default.
3. **Consensus-approved** — contribution categories are reviewed and
   approved through the collective's governance process before they are
   enabled.

Members may review, modify, or revoke their contribution preferences at any
time through the Murphy dashboard. Revoking consent removes your future
contributions from the shared pool; previously anonymized contributions
that have already been aggregated cannot be individually extracted.

## Agent as Identity

Your Murphy agent serves as your **identity anchor** within the collective:

- **Wallet.** Your agent holds your cryptographic keys and manages
  transactions, token balances, and payment authorizations on your behalf.
- **Authentication key.** Your agent is your authentication credential.
  Access to Murphy services is gated through your agent's key pair, not
  through passwords or centralized identity providers.
- **Portable identity.** Your agent identity is yours to take. If you leave
  the collective, your agent, its keys, and its data go with you.

Because your agent doubles as your wallet and authentication key, Murphy
applies the highest security standards to agent storage and key management
(see Security Controls below).

## Security Controls

- **Encryption at rest**: Fernet symmetric encryption for credentials
- **Encryption in transit**: TLS/HTTPS for all external API calls
- **Access control**: RBAC with role-based permission gating
- **Audit logging**: Bounded, in-memory audit log with PII redaction
- **DLP**: `SensitiveDataClassifier` scans data pipelines for PII leaks

## Contact

For privacy questions, contact the Murphy Collective maintainers at:
https://github.com/IKNOWINOT/Murphy-System/issues
