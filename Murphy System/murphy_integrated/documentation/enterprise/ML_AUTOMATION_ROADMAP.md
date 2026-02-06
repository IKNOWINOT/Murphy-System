# Murphy ML Automation Roadmap (Auditable)

This plan defines how Murphy will develop, manage, and operate ML-driven automation across business domains. The focus is on **auditable, deterministic outcomes** with clear gating between what a customer provides, what Murphy may infer, and what must be explicitly requested.

## 1) Core Principles (Non‑negotiable)

- **Auditability first:** every inference, prediction, and generated artifact must have a ledger entry linking inputs → model → decision → output.
- **Deterministic outputs:** where compliance or operational risk exists, output must be bounded by templates and policies (no open‑ended generation).
- **Separation of sources:**
  - **Provided**: customer-supplied facts, documents, and explicit approvals.
  - **Inferred**: model predictions and derived metrics (tagged as inferred).
  - **Required**: missing data that must be requested before continuing.
- **Regulatory gating:** industry and jurisdiction rules enforce which steps can proceed without HITL approval.
- **Model containment:** ML outputs are proposals; production changes require policy validation and approval.

## 2) Universal Business Functions to Automate (Most Applicable)

The following functions are common to nearly all businesses and offer high automation ROI. Each includes **input sources**, **ML inference targets**, **deliverables**, and **gates**.

### A) Lead Intake & Qualification
- **Inputs:** web forms, CRM, email, call transcripts
- **ML Inference:** lead fit score, urgency, authority likelihood
- **Deliverables:** qualification report, next-step recommendation
- **Gates:** require explicit approval before outreach sequencing or disqualification

### B) Requirements Capture & Scoping
- **Inputs:** discovery notes, intake forms, system inventories
- **ML Inference:** scope estimate, missing constraints, risk flags
- **Deliverables:** requirements dossier, scope matrix
- **Gates:** customer approval on scope + compliance before proposal generation

### C) Proposal & Pricing
- **Inputs:** requirements dossier, pricing rules, historical deals
- **ML Inference:** optimal tier, discount boundaries, timeline risk
- **Deliverables:** proposal draft, pricing sheet
- **Gates:** pricing approval + legal review where required

### D) Contract & Compliance
- **Inputs:** proposal, legal templates, jurisdiction rules
- **ML Inference:** clause risk, required addenda
- **Deliverables:** contract draft, compliance checklist
- **Gates:** legal/HITL approval before issuance

### E) Delivery & Onboarding
- **Inputs:** implementation plan, integration checklist
- **ML Inference:** schedule risk, dependency gaps
- **Deliverables:** onboarding plan, rollout tracker
- **Gates:** customer confirmation before automation activation

### F) Operations Monitoring
- **Inputs:** telemetry, incident logs, SLA metrics
- **ML Inference:** drift detection, anomaly scoring
- **Deliverables:** incident report, remediation plan
- **Gates:** operational approval before system changes

### G) Finance & Forecasting
- **Inputs:** invoices, revenue data, pipeline values
- **ML Inference:** forecast accuracy, cash‑flow risk
- **Deliverables:** forecast report, alerts
- **Gates:** executive approval for budget actions

### H) Customer Success & Renewal
- **Inputs:** usage telemetry, support cases, NPS
- **ML Inference:** churn risk, expansion likelihood
- **Deliverables:** renewal playbook, upsell triggers
- **Gates:** human review before automated outreach

## 3) Domain Pack Strategy (Per Session)

- **Base layer:** universal policies (audit, safety, approvals, ledgers).
- **Session layer:** customer‑specific priors derived from onboarding + provided artifacts.
- **Domain pack growth:** convert repeated onboarding patterns into reusable domain packs.
- **Ledger tags:** every entity, metric, and requirement is tagged with source type (provided/inferred/required).

## 4) Gating Model (Provided vs. Inferred vs. Required)

| Data Type | Definition | Allowed Uses | Gate Requirement |
|----------|------------|--------------|------------------|
| Provided | Explicit customer data | Can drive deterministic outputs | None beyond audit logging |
| Inferred | ML-derived predictions | Only used for proposals/flags | HITL before execution |
| Required | Missing critical input | Must be requested | Block downstream flow |

**Rule:** If a required field is missing, the system **must halt** generation and ask for input.

## 5) Audit Ledger Events (Required Fields)

- `event_id`, `timestamp`, `session_id`
- `input_refs` (documents, fields, approvals)
- `model_id`, `model_version`
- `decision_type` (inference, generation, escalation)
- `confidence_score` + `thresholds`
- `output_ref` (artifact id)
- `approval_ref` (if HITL)

## 6) ML Development Phases

1. **Phase 1: Parsing + Tagging** (MVP)
   - Extract structured fields from random domain documents.
   - Validate against taxonomies.

2. **Phase 2: Confidence + Drift**
   - Introduce belief updates, drift detection, and automated gating.

3. **Phase 3: Predictive Deliverables**
   - Generate bounded deliverables (reports, checklists, plans).

4. **Phase 4: Optimized Operations**
   - Continuous learning, performance tuning, and domain pack growth.

## 7) Deliverables Catalog (Initial Set)

- Qualification Report
- Requirements Dossier
- Scope Matrix
- Proposal Draft
- Compliance Checklist
- Onboarding Plan
- Incident Report
- Forecast Report
- Renewal Playbook

Each deliverable is generated via deterministic templates with traceable inputs.

## 8) What to Build Next

- **Data ingestion adapters** for CRM, ticketing, analytics
- **Template library** for each deliverable type
- **Ledger service** for audit compliance
- **HITL interface** for gated approvals

---

**Outcome:** Murphy can safely automate high‑ROI business functions by enforcing deterministic generation, clear gating, and full auditability.
