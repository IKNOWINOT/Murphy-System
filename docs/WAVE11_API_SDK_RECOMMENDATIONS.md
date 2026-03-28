# Murphy System — API & SDK Recommendations

**Date:** 2025-03-27  
**Scope:** Platform-side API keys and SDK integrations required for full demo capability  
**Branch:** `audit/comprehensive-production-readiness`

---

## Overview

The Murphy System demo pipeline routes through multiple subsystems (MFGC → MSS Magnify → MSS Solidify → AI Workflow Generator → Automation Spec). Each stage has graceful fallbacks so the demo always completes, but the quality of output improves significantly when upstream APIs are configured. Below is the prioritized list of API keys and SDKs that should be obtained and configured.

---

## Priority 1 — Critical for Demo Quality

### 1.1 LLM Provider API Keys

| Provider | Purpose | Environment Variable | Status |
|----------|---------|---------------------|--------|
| **DeepInfra** | Primary LLM for custom deliverable generation, enrichment, and natural language processing | `DEEPINFRA_API_KEY` | **Required** — Primary provider after Groq→DeepInfra migration (Wave 1) |
| **Together.ai** | Fallback LLM when DeepInfra is unavailable | `TOGETHER_API_KEY` | **Recommended** — Resilience layer |
| **Ollama (local)** | On-premise LLM fallback, zero external dependency | N/A (runs locally) | **Configured** — Auto-detected at runtime |

**Impact when missing:** Deliverables fall back to domain-aware templates (`_build_minimal_custom_content`). These are professional but not personalized to the user's specific query.

**Action:** Ensure `DEEPINFRA_API_KEY` is set in GitHub Secrets and deployment environment. Optionally add `TOGETHER_API_KEY` for redundancy.

### 1.2 Email / SMTP Configuration

| Setting | Purpose | Environment Variable |
|---------|---------|---------------------|
| **SMTP Host** | Sending demo completion emails, signup confirmations | `MURPHY_SMTP_HOST` |
| **SMTP Credentials** | Authentication for email delivery | `MURPHY_SMTP_USER`, `MURPHY_SMTP_PASS` |

**Impact when missing:** Email-based features (demo result delivery, account activation) will not function. Non-blocking for the demo itself.

---

## Priority 2 — Enhances Demo Value

### 2.1 Payment Processing

| Provider | Purpose | SDK/Key |
|----------|---------|---------|
| **Stripe** | Subscription management, checkout for Solo/Business/Professional tiers | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` |

**Impact when missing:** The "Activate this automation" link in the spec summary leads to a signup page. Without Stripe, paid tier upgrades cannot be processed. The demo still functions completely.

**SDK:** `stripe` Python package (already in requirements)

### 2.2 Matrix / Communication Bridge

| Provider | Purpose | Environment Variable |
|----------|---------|---------------------|
| **Matrix Synapse** | Inter-agent communication, HITL chat bridge | `MATRIX_HOMESERVER`, `MATRIX_ACCESS_TOKEN` |

**Impact when missing:** Agent-to-agent communication falls back to in-memory messaging. Demo unaffected. Production multi-agent workflows benefit from Matrix bridge persistence.

---

## Priority 3 — Extended Platform Capabilities

### 3.1 External Integration APIs

These APIs enable Murphy to connect to real external systems during automation execution. They are NOT required for the demo but are required for production automation delivery.

| API | Purpose | SDK/Package | Key Variable |
|-----|---------|-------------|--------------|
| **Slack** | Workflow notifications, team alerts, approval flows | `slack-sdk` | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` |
| **Jira** | Project management integration, task creation | `jira` | `JIRA_URL`, `JIRA_API_TOKEN` |
| **Salesforce** | CRM integration for sales/marketing workflows | `simple-salesforce` | `SF_USERNAME`, `SF_PASSWORD`, `SF_SECURITY_TOKEN` |
| **HubSpot** | Marketing automation, contact management | `hubspot-api-client` | `HUBSPOT_API_KEY` |
| **Twilio** | SMS/voice notifications in workflows | `twilio` | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` |
| **SendGrid** | Transactional email delivery | `sendgrid` | `SENDGRID_API_KEY` |
| **AWS S3** | File storage for generated deliverables and bundles | `boto3` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| **Google Workspace** | Calendar, Drive, Sheets integration | `google-api-python-client` | `GOOGLE_SERVICE_ACCOUNT_JSON` |
| **Zapier** | Third-party workflow orchestration | REST API | `ZAPIER_WEBHOOK_URL` |
| **DocuSign** | Document signing automation | `docusign-esign` | `DOCUSIGN_INTEGRATION_KEY` |

### 3.2 Data & Analytics APIs

| API | Purpose | Key Variable |
|-----|---------|--------------|
| **Plaid** | Financial data aggregation for finance workflows | `PLAID_CLIENT_ID`, `PLAID_SECRET` |
| **Clearbit** | Company/contact enrichment for sales workflows | `CLEARBIT_API_KEY` |
| **OpenAI** | Alternative LLM provider (GPT-4) for premium tier | `OPENAI_API_KEY` |
| **Anthropic** | Alternative LLM provider (Claude) for premium tier | `ANTHROPIC_API_KEY` |

---

## Current GitHub Secrets Audit

Based on the codebase analysis, the following secrets should be configured:

### ✅ Already Referenced in Code
- `DEEPINFRA_API_KEY` — Primary LLM provider
- `TOGETHER_API_KEY` — Fallback LLM provider
- `GITHUB_TOKEN` — Repository access (auto-provided by GitHub Actions)

### ⚠️ Referenced but May Need Configuration
- `MURPHY_SECRET_KEY` — Session encryption key
- `MURPHY_SMTP_HOST` / `MURPHY_SMTP_USER` / `MURPHY_SMTP_PASS` — Email delivery
- `STRIPE_SECRET_KEY` — Payment processing

### 📋 Recommended to Add
- `SLACK_BOT_TOKEN` — For Slack integration demos
- `SENDGRID_API_KEY` — For email delivery in production
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — For S3 file storage

---

## SDK Installation Status

| Package | Status | Used By |
|---------|--------|---------|
| `httpx` | ✅ Installed | DeepInfra/Together.ai API calls |
| `starlette` | ✅ Installed | Web framework, test client |
| `pydantic` | ✅ Installed | Data validation |
| `stripe` | ⚠️ Check | Payment processing |
| `slack-sdk` | ❌ Not installed | Slack integration |
| `jira` | ❌ Not installed | Jira integration |
| `simple-salesforce` | ❌ Not installed | Salesforce integration |
| `boto3` | ❌ Not installed | AWS S3 storage |

---

## Recommendation Summary

| Priority | Action | Impact |
|----------|--------|--------|
| **P1** | Ensure `DEEPINFRA_API_KEY` is set | Demo produces personalized LLM content |
| **P1** | Add `TOGETHER_API_KEY` as fallback | Resilience when DeepInfra is down |
| **P2** | Configure Stripe keys | Enable paid tier signups from demo |
| **P2** | Configure SMTP | Enable email delivery for demo results |
| **P3** | Add integration API keys as needed | Enable real external connections in production |

---

*Copyright © 2020 Inoni Limited Liability Company. License: BSL 1.1*