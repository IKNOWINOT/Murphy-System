# Murphy FDE Pod — Tasked Agents (not assistants)

**Ship 30 — 2026-06-10 — locked by founder directive 2026-06-10.**

## What this is

Eleven tasked agents that execute the Forward Deployed Engineer 
engagement loop end-to-end. They take instructions, perform work, 
produce deliverables, and book outcomes to the ledger. They are 
NOT chatbots. They are NOT recommendation engines. They are workers 
under Rosetta contract with explicit scope, authority, spend limits, 
and a loyalty bias.

## The dual loyalty rule

Every FDE agent serves two principals:
  1. **Customer** — the paying tenant whose engagement they're embedded in
  2. **Inoni LLC** — the operator (Corey Post) whose business they generate margin for

When interests align (the usual case): execute normally.
When interests conflict: the new Rosetta field **`loyalty_bias`** controls. Values:
  - `customer_first` — used by Builder, Sustainer, Relationship (trust agents)
  - `mutual` — used by Recon, Scoping (advisory agents)
  - `operator_first` — used by Negotiator, Treasury, Margin Optimizer, CSA, Partnership Scout (business agents)
  - `compliance_first` — used by Compliance agent (overrides everything else)

The bias is RECORDED on every dispatch. The HITL gate fires whenever a 
single action crosses biases (e.g., Builder proposing something that 
benefits Inoni at customer expense).

## The eleven agents

### Customer-facing engagement loop (5)
| # | Agent | Phase | Loyalty | What it does |
|---|---|---|---|---|
| 1 | Recon | Day 1-3 | mutual | Inventories customer environment read-only |
| 2 | Scoping | Day 4-7 | mutual | Translates pain → PRD with ROI math |
| 3 | Builder | Week 2-N | customer_first | Ships code under customer's repo + rules |
| 4 | Sustainer | Week 6+ | customer_first | Keeps shipped systems alive in customer prod |
| 5 | Relationship | Continuous | customer_first | Slack/email presence in customer org |

### Operator/business arrangement (6)
| # | Agent | Phase | Loyalty | What it does |
|---|---|---|---|---|
| 6 | Negotiator | Pre-sales + amendments | operator_first | MSA/SOW/EUA terms with customer legal |
| 7 | Procurement | Continuous | operator_first | Selects cheapest vendor that meets engagement spec |
| 8 | Compliance | Pre-ship gate | compliance_first | Veto power before any external action |
| 9 | Treasury | Per transaction | operator_first | Routes money customer→vendor→Inoni margin |
| 10 | Margin Optimizer | Continuous | operator_first | Tags every workstream with $/hr math, surfaces leaks |
| 11 | Partnership Scout | Continuous | operator_first | Hunts cheap resale/affiliate deals to lower COGS |

### Reporting (1)
| # | Agent | Phase | Loyalty | What it does |
|---|---|---|---|---|
| 12 | CSA | Weekly | operator_first | Reports to Corey only: is this engagement on track to renew? |

## How they compose

```
Pipeline Producer (in Sales lane, not FDE pod itself)
    ↓ qualified inbound
Negotiator (close the deal)
    ↓ signed MSA/SOW
Recon → Scoping → Builder → Sustainer → Relationship
                  ↑                ↑
                  Compliance gate fires on every external action
                  Procurement is queried for every vendor decision
                  Treasury books every $ event
                  Margin Optimizer watches it all
                  Partnership Scout pre-positions cheaper vendors
                  CSA reports to Corey weekly
```

## The leverage strategy (founder-locked)

**Bias toward partnership-leveraged economics.** Murphy is NOT a 
high-COGS shop. Every workstream is forced through Procurement which 
must pick the cheapest vendor that satisfies the engagement spec. 
Partnership Scout actively pre-negotiates resale/affiliate deals 
with every vendor we touch so that even at customer's posted price, 
Inoni captures wholesale-vs-retail spread.

**Examples in scope today:**
  - Together AI → wholesale LLM tokens, marked up at customer rate
  - AWS Activate → $5k-100k in free credits, applied to customer infra
  - Stripe partners → 0.4% revenue share on processed payments
  - Anthropic startup program → discounted Opus access
  - Hugging Face Pro → free if we publish open-source Murphy-Bench

**Anti-patterns the agents must refuse:**
  - Picking a vendor because Inoni gets kickback when worse for customer
  - Ignoring open-source alternative when it would close to break-even
  - Building bespoke when a partnership API exists at lower TCO

## Rosetta extension required for v1

Add to `RosettaDocument`:
  - `loyalty_bias`: enum (above)
  - `partnership_preferences`: list of preferred vendors with deal terms
  - `cogs_ceiling_per_workstream`: dict of $ caps before HITL fires
  - `customer_principal_id`: who the customer-side principal is
  - `operator_principal_id`: always Corey Post / Inoni LLC

## Files in this directory

```
01_recon_agent.md
02_scoping_agent.md
03_builder_agent.md
04_sustainer_agent.md
05_relationship_agent.md
06_negotiator_agent.md
07_procurement_agent.md
08_compliance_agent.md
09_treasury_agent.md
10_margin_optimizer_agent.md
11_partnership_scout_agent.md
12_customer_success_auditor.md
```

Each spec fills in: identity, employee_contract, industry_terminology, 
business_plan_math, day_of_week_factor, hitl_throughput_model, 
subject_matter_perspective, workflow_pattern, task_pipeline, loyalty_bias, 
partnership_preferences, cogs_ceiling, and a Day-1 scenario.
