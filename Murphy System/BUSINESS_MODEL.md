# Murphy System — Business Model

> Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post
> License: BSL 1.1 (Business Source License)

---

## Overview

Murphy System is an **autonomous business automation platform** that converts
natural-language requests into governed, auditable execution plans. It is
licensed under the Business Source License 1.1 (BSL 1.1), which converts to
Apache 2.0 after four years per version release.

## Revenue Streams

### 1. Platform Licensing (Primary)

| Tier | Monthly | Annual/mo | Users | Automations | Includes |
|------|---------|-----------|-------|-------------|----------|
| **Solo** | $29 | $24 | 1 | 3 | Core runtime, community support |
| **Business** | $99 | $79 | 10 | Unlimited | Multi-user, API access, email support |
| **Professional** | $299 | $249 | Unlimited | Unlimited | SSO, RBAC, priority support |
| **Enterprise** | Custom | Custom | Unlimited | Unlimited | SLA, dedicated support, white-label, multi-tenant |

> **Self-hosted is always free for development** (BSL 1.1). Production licensing starts at Solo $29/mo.

### 2. Managed Services

- Hosted Murphy instances (SaaS)
- Migration and onboarding assistance
- Custom integration development

### 3. Support & Training

- Priority support contracts
- Training and certification programs
- Architecture review and consulting

## Pricing Philosophy

- **Development use is always free** (BSL 1.1 allows non-production use)
- **Production licensing** scales with organizational size
- **No per-API-call pricing** — predictable costs for customers
- **Open conversion** — each version becomes Apache 2.0 after four years

## Competitive Positioning

Murphy System differentiates through:

1. **Deterministic governance** — every action passes through auditable gates
2. **Domain-agnostic control plane** — same engine handles HVAC, finance, healthcare
3. **Human-in-the-loop by design** — not bolted on as an afterthought
4. **Resolution-aware processing** — RM0–RM6 concept clarity scoring
5. **Regulatory alignment** — built-in controls for GDPR, SOC 2, HIPAA, PCI DSS

## Go-to-Market Strategy

1. **Open-source community** — BSL 1.1 source availability builds trust
2. **Developer-first adoption** — CLI, API, and terminal interfaces
3. **Vertical templates** — pre-built automation for specific industries
4. **Partner ecosystem** — agency automation tier enables resellers

---

## Murphy's UX Paradigm: Describe → Execute → Refine

This is the generational leap that separates Murphy from drag-and-drop node builders.

### The Three-Step Flow

**1. Describe** — Primary input is natural language. The user describes what they want:
> *"Monitor my sales data and send a weekly summary to Slack."*

No forms. No connectors to drag. No trigger logic to wire. Just a plain English sentence.

**2. Execute** — Murphy generates the execution plan. Internally, `ai_workflow_generator.py` converts the description into a governed DAG workflow:
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
