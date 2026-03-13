# Murphy System — Public Roadmap

> **Revenue-first, $0-budget execution strategy.**
> Every sprint is gated by the revenue of the previous one.
> This roadmap is public so customers, contributors, and collaborators can hold us accountable.

---

## 🎯 North Star: Describe → Execute → Refine

Murphy's hero flow is already built. This roadmap is about getting it in front of paying customers, polishing the experience, and reinvesting revenue to grow the ecosystem.

```
1. DESCRIBE: "Monitor my sales data and send a weekly summary to Slack"
2. EXECUTE:  Murphy builds a governed DAG workflow with safety gates
3. REFINE:   Open the visual canvas to tweak any step (optional)
```

---

## Sprint 1 — Weeks 1–4: Make It Work Perfectly for 1 Paying Customer

**Goal:** Ship a flawless end-to-end experience for the very first paying customer.

### Tasks

- [ ] Fix critical bugs: LLM key config (ref: PR #56), security findings (ref: PR #27)
- [ ] Polish the **Describe → Execute** hero flow:
  - User types intent in plain English
  - Murphy shows the generated plan (DAG workflow)
  - User approves → it runs
- [ ] One-command install: `docker compose up` → onboarding wizard within 60 seconds
- [ ] Record 3 screen recordings (OBS, free) demonstrating end-to-end flows:
  1. Sales automation from description to execution
  2. IT ticket routing
  3. IoT sensor alert → Slack notification
- [ ] Identify and personally onboard the first paying customer

### Modules Powering This Sprint

- `ai_workflow_generator.py` — natural language → DAG generation
- `nocode_workflow_terminal.py` — Librarian-powered description interface
- `aionmind/runtime_kernel.py` — execution runtime
- `workflow_canvas.html` — visual plan review
- `murphy_terminal.py` — terminal interface

---

## Sprint 2 — Weeks 5–8: Visual Refinement Layer + First 50 Connectors

**Goal:** Publish pricing, grow to 10 paying customers.

### Tasks

- [ ] Visual canvas role clarified: "edit what Murphy built" — a reviewer, not a builder
- [ ] Ship 50 connectors using the self-integration engine:
  - Slack, Jira, Salesforce, HubSpot, GitHub, Google Workspace, Microsoft 365, Stripe, Shopify, Twilio, SendGrid, AWS, Azure, GCP, PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch, Notion, Airtable, Asana, Trello, Zendesk, Freshdesk, Intercom, Mailchimp, Typeform, Calendly, Zoom, Discord, Telegram, Dropbox, Box, Linear, PagerDuty, Datadog, Splunk, Kafka, RabbitMQ, Snowflake, BigQuery, Plaid, QuickBooks, Xero, and more
- [ ] Pricing page goes live (ref: PR #211)
- [ ] Publish **Solo tier at $29/mo**
- [ ] Target: **first 10 paying customers**

---

## Sprint 3 — Weeks 9–12: Community + Docs + 100 Connectors

**Goal:** Build the ecosystem foundation.

### Tasks

- [ ] GitHub Discussions enabled (free)
- [ ] Docs site on GitHub Pages (free)
- [ ] 100 connectors total (self-integration engine + community PRs)
  - Community connector PRs credited with "Built by [name]" in connector metadata
- [ ] `CONTRIBUTING.md` upgraded with "good first issue" labels
- [ ] Connector contribution guide published

---

## Sprint 4 — Weeks 13–20: Revenue Reinvestment

**Goal:** Use revenue to fund the next layer of the platform.

### Revenue-Gated Milestones

| MRR Milestone | Action Unlocked |
|---|---|
| **$1K MRR** | Begin basic SaaS hosting exploration |
| **$5K MRR** | Launch managed SaaS; introduce connector bounties ($50–$100/connector) |
| **$15K MRR** | Formal penetration test; begin SOC 2 readiness program |
| **$50K MRR** | Full SOC 2 Type II certification; first team hires |

---

## Pricing Model

| Tier | Monthly | Annual/mo | Users | Automations |
|---|---|---|---|---|
| **Solo** | $29 | $24 | 1 | 3 |
| **Business** | $99 | $79 | 10 | Unlimited |
| **Professional** | $299 | $249 | Unlimited | Unlimited |
| **Enterprise** | Custom | Custom | Unlimited | Unlimited |

> **Self-hosted is always free for development** (BSL 1.1). Production licensing starts at Solo $29/mo.

---

## What We Are NOT Doing (Yet)

- No paid bounties until $5K MRR
- No SaaS hosting until $1K MRR
- No formal pen test until $15K MRR
- No new paid tooling or services added to the stack

---

## Contributing to the Roadmap

Have a feature request? Open a [GitHub Discussion](https://github.com/IKNOWINOT/Murphy-System/discussions) or file an issue with the `roadmap` label.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute connectors, bug fixes, or docs.
