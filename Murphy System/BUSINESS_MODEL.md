# Murphy System — Business Model

> Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post
> License: BSL 1.1 (Business Source License)

---

## Overview

Murphy System is an **autonomous business automation platform** that converts
natural-language requests into governed, auditable execution plans across every
vertical — from enterprise business automation to manufacturing, building
automation, energy management, SCADA/ICS, content creation, and social media
management. Licensed under the Business Source License 1.1 (BSL 1.1), which
converts to Apache 2.0 after four years per version release.

---

## Pricing Tiers

| Tier | Monthly | Annual | Users | Automations | Integrations |
|------|---------|--------|-------|-------------|--------------|
| **Solo** | $29/mo | $24/mo | 1 | 3 active | 5 integrations |
| **Business** | $299/mo | $249/mo | 10 | Unlimited | 20 integrations |
| **Professional** | Custom | Custom | Unlimited | Unlimited | All 90+ integrations |
| **Enterprise** | Custom | Custom | Unlimited | Unlimited | All + custom |

All tiers include:
- Full NL → DAG → Execute pipeline (describe-to-execute)
- Visual workflow canvas with AI suggestions
- SOC 2 Type II audit trail
- Docker / Kubernetes self-hosting option

---

## Feature Matrix

| Capability | Solo | Business | Professional | Enterprise |
|---|:---:|:---:|:---:|:---:|
| **Core Automation** | | | | |
| Describe → Execute (NL→DAG) | ✅ | ✅ | ✅ | ✅ |
| Visual Workflow Canvas | ✅ | ✅ | ✅ | ✅ |
| Workflow Templates | 50+ | 200+ | All | All + Custom |
| Concurrent Workflows | 3 | 25 | Unlimited | Unlimited |
| **Integrations** | | | | |
| Pre-built Connectors | 5 | 20 | 90+ | 90+ + Custom |
| CRM (HubSpot, Salesforce) | — | ✅ | ✅ | ✅ |
| Payments (Stripe, PayPal) | — | ✅ | ✅ | ✅ |
| Communication (Slack, Discord, Telegram) | ✅ | ✅ | ✅ | ✅ |
| Cloud Storage (Google Drive, Dropbox) | ✅ | ✅ | ✅ | ✅ |
| Social Media (YouTube, TikTok, Twitter) | — | ✅ | ✅ | ✅ |
| E-Commerce (Shopify, WooCommerce) | — | ✅ | ✅ | ✅ |
| AI/ML APIs (OpenAI, Anthropic) | — | ✅ | ✅ | ✅ |
| Analytics (Google Analytics, Datadog) | — | ✅ | ✅ | ✅ |
| Market Data (Yahoo Finance) | ✅ | ✅ | ✅ | ✅ |
| Weather & IoT (OpenWeatherMap) | ✅ | ✅ | ✅ | ✅ |
| **Industrial / OT** | | | | |
| SCADA / Modbus TCP | — | — | ✅ | ✅ |
| BACnet / OPC UA | — | — | ✅ | ✅ |
| Building Automation (BAS/BMS) | — | — | ✅ | ✅ |
| Energy Management (EMS) | — | — | ✅ | ✅ |
| Additive Manufacturing / 3D Print | — | — | ✅ | ✅ |
| MTConnect / PackML / ISA-95 | — | — | ✅ | ✅ |
| **Content & Media** | | | | |
| YouTube Data API | — | ✅ | ✅ | ✅ |
| Twitch / Live Streaming | — | ✅ | ✅ | ✅ |
| Social Media Scheduler | — | ✅ | ✅ | ✅ |
| Content Creator Platform Modulator | — | — | ✅ | ✅ |
| Digital Asset Generator | — | — | ✅ | ✅ |
| **AI & Governance** | | | | |
| Multi-LLM Routing (OpenAI/Anthropic/Groq/Local) | ✅ | ✅ | ✅ | ✅ |
| Murphy Foundation Model (on-prem) | — | — | ✅ | ✅ |
| Confidence-Gated Execution (G/D/H scoring) | ✅ | ✅ | ✅ | ✅ |
| Human-in-the-Loop Gates | ✅ | ✅ | ✅ | ✅ |
| Wingman Protocol (executor/validator) | — | ✅ | ✅ | ✅ |
| Causality Sandbox (what-if simulation) | — | — | ✅ | ✅ |
| **Security & Compliance** | | | | |
| RBAC / Multi-tenant | — | ✅ | ✅ | ✅ |
| SOC 2 / GDPR / HIPAA / PCI DSS | — | ✅ | ✅ | ✅ |
| PII Redaction + Audit Log | ✅ | ✅ | ✅ | ✅ |
| SSO / SAML | — | — | ✅ | ✅ |
| **Support** | | | | |
| Community Support | ✅ | — | — | — |
| Email Support | — | ✅ | ✅ | ✅ |
| Priority / SLA Support | — | — | ✅ | ✅ |
| Dedicated CSM + Architecture Review | — | — | — | ✅ |

---

## Revenue Streams

### 1. Platform Licensing (Primary)

Subscription SaaS with annual discount. Industrial/OT and full content
creator capabilities gated to Professional and above — commanding a premium
over general-purpose automation tools.
| Tier | Monthly | Annual/mo | Users | Automations | Includes |
|------|---------|-----------|-------|-------------|----------|
| **Solo** | $29 | $24 | 1 | 3 | Core runtime, community support |
| **Business** | $299 | $249 | 10 | Unlimited | Multi-user, API access, email support |
| **Professional** | Custom | Custom | Unlimited | Unlimited | SSO, RBAC, priority support |
| **Enterprise** | Custom | Custom | Unlimited | Unlimited | SLA, dedicated support, white-label, multi-tenant |

> **Self-hosted is always free for development** (BSL 1.1). Production licensing starts at Solo $29/mo.

### 2. Managed Cloud Hosting

- Fully managed Murphy instances (Murphy Cloud)
- 99.9% SLA, automatic updates, managed backups
- Available from Business tier upward

### 3. Vertical Add-Ons (à la carte)

| Add-On | Price | Description |
|--------|-------|-------------|
| **Industrial OT Bundle** | +$99/mo | SCADA, BACnet, Modbus, OPC UA, EMS, BAS |
| **Content Creator Bundle** | +$49/mo | YouTube API, TikTok, Twitch, Content Modulator |
| **AI Credits Top-up** | Usage-based | Extra OpenAI/Anthropic/Groq tokens |
| **Compliance Pack** | +$149/mo | Enhanced SOC 2 + HIPAA + PCI DSS reporting |
| **White-Label License** | Custom | Agency/reseller rights |

### 4. Professional Services

- Onboarding and integration development
- Training and certification programs
- Architecture review and consulting

---

## Pricing Philosophy

- **Development use is always free** (BSL 1.1 allows non-production use)
- **No per-API-call pricing** — flat subscription, predictable costs
- **Premium for breadth** — no competitor covers factory-floor to social media to AI in one system
- **Open conversion** — each version becomes Apache 2.0 after four years

---

## Competitive Positioning

Murphy System commands a premium because it is the **only platform that covers**:

| Domain | Capability | Nearest Competitor |
|---|---|---|
| Business Automation | NL → governed DAG execution | Zapier (no NL), n8n (no governance) |
| Industrial / OT | SCADA, BACnet, Modbus, OPC UA, EMS, BAS | None (market gap) |
| Additive Manufacturing | 3D print job management via OPC UA AM spec | None (market gap) |
| Content Creation | YouTube, Twitch, TikTok, content pipeline | Buffer (no automation) |
| AI Orchestration | Multi-LLM routing + Murphy Foundation Model | LangChain (no governance) |
| Self-Improvement | Immune engine + shadow deployment + RLEF | None (market gap) |

Key differentiators:
1. **Describe → Execute** — natural language directly generates governed workflows
2. **Self-Integration Engine** — point at a GitHub repo → Murphy generates the adapter
3. **Self-Improvement** — system learns from corrections and auto-heals at runtime
4. **Full-Stack Vertical** — factory floor → enterprise → agent → content creator in one system
5. **Confidence-Gated** — Bayesian scoring + 5D uncertainty on every decision

---

## Go-to-Market Strategy

1. **Open-source community** — BSL 1.1 source availability builds trust
2. **Developer-first adoption** — CLI, API, and terminal interfaces
3. **Industrial/OT vertical** — underserved market, high willingness to pay, low competition
4. **Content creator vertical** — large addressable market, proven SaaS pricing
5. **Partner ecosystem** — agency automation tier enables resellers
6. **Revenue gates** — target $1K → $5K → $15K → $50K MRR through focused sprints
3. **Vertical templates** — pre-built automation for specific industries
4. **Partner ecosystem** — agency automation tier enables resellers

---

## Murphy's UX Paradigm: Describe → Execute → Refine

This is the generational leap that separates Murphy from drag-and-drop node builders.

### The Three-Step Flow

**1. Describe** — Primary input is natural language. The user describes what they want:
> *"Monitor my sales data and send a weekly summary to Slack."*

No forms. No connectors to drag. No trigger logic to wire. Just a plain English sentence.

**2. Execute** — Murphy generates the execution plan — `ai_workflow_generator.py` converts the description into a governed DAG workflow:
- Nodes represent steps (fetch data, process, send notification)
- Edges define the execution order
- Safety gates are automatically inserted at key decision points
- The full plan is shown to the user for approval before anything runs

**3. Refine (optional)** — The visual canvas (`workflow_canvas.html`) is the *review layer*, not the build layer. After Murphy generates the workflow, the user can open the canvas to:
- Rename or reorder steps
- Adjust timing or conditions
- Add custom logic nodes
- Re-run with modifications

### Why This Matters

Every other automation platform forces the user to be the architect. Murphy inverts this: **Murphy is the architect; the user is the approver.**

- Zapier: drag connector A to connector B. You are the engineer.
- Make: build a scenario with modules. You are the engineer.
- **Murphy: describe what you want. Murphy engineers it. You approve.**

The visual canvas exists not because drag-and-drop is the paradigm — it exists because sometimes you want to tweak what Murphy built. That's a fundamentally different role for a UI element.

### Modules That Power This Flow

| Module | Role |
|---|---|
| `nocode_workflow_terminal.py` | Librarian-powered interface — user describes intent, Librarian clarifies |
| `ai_workflow_generator.py` | Converts natural language description into a structured DAG workflow |
| `aionmind/runtime_kernel.py` | Executes the approved DAG with full orchestration and governance |
| `workflow_canvas.html` | Visual canvas for optional post-generation refinement |
| `murphy_terminal.py` | Terminal interface for power users and developers |
