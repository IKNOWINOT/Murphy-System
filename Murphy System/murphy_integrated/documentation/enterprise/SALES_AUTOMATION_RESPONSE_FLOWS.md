# Murphy System Sales Automation – Response Flows

This document defines response flows for automating the business of selling Murphy System. These flows are designed to work with the integrated UI variants and the backend architecture blueprint.

## 1) Lead Intake → Qualification Flow

**Goal:** convert inbound lead data into a qualified opportunity with a structured next step.

**Trigger:** inbound web form, CRM webhook, referral intake, or UI onboarding form.

**Inputs:**
- `lead_profile` (name, company, role, email)
- `company_size`
- `industry`
- `use_case_summary`
- `decision_timeline`

**System Responses:**
1. **Acknowledge + capture intent**
   - “Thanks for reaching out. Let’s validate fit and scope.”
2. **Qualification questions (deterministic)**
   - Budget range, decision authority, current tooling, timeline.
3. **Fit score**
   - `fit_score = weighted(company_size, industry, timeline, urgency)`
4. **Next step routing**
   - `fit_score >= 0.75` → schedule discovery call
   - `0.4 <= fit_score < 0.75` → request clarifying answers
   - `< 0.4` → send resource pack + optional re-engagement

**Outputs:**
- `qualification_report`
- `next_action` (schedule/disqualify/clarify)

---

## 2) Discovery → Requirements Capture Flow

**Goal:** produce a clean requirements dossier and scoped plan for a sales opportunity.

**Trigger:** qualified lead, scheduled discovery, or onboarding workflow completion.

**Inputs:**
- `business_problem`
- `current_process_map`
- `constraints` (compliance, security, approvals)
- `success_metrics`

**System Responses:**
1. **Interview prompts** (structured, short-form)
   - “What’s the primary bottleneck?”
   - “Which systems must remain the system-of-record?”
2. **Artifact creation**
   - `Requirements Dossier` (structured sections + redlines)
3. **Scope boundaries**
   - “In scope / Out of scope” matrix
4. **Validation prompt**
   - confirm or request HITL review

**Outputs:**
- `requirements_dossier`
- `scope_matrix`
- `risk_flags`

---

## 3) Solution Blueprint → Proposal Flow

**Goal:** generate a proposal that aligns with requirements, pricing, and delivery timeline.

**Trigger:** approved requirements dossier.

**Inputs:**
- `requirements_dossier`
- `pricing_model` (fixed, usage-based, hybrid)
- `delivery_timeline`

**System Responses:**
1. **Solution blueprint**
   - architecture summary, modules, integrations, and phased rollout
2. **Pricing response**
   - tiers + assumptions; include compliance add-ons
3. **Approval request** (HITL)
   - “Confirm proposal draft before sending.”

**Outputs:**
- `proposal_pdf`
- `pricing_sheet`
- `timeline`

---

## 4) Procurement → Contract Flow

**Goal:** move from proposal acceptance to executed contract.

**Trigger:** proposal accepted.

**Inputs:**
- `accepted_proposal`
- `legal_constraints`
- `payment_terms`

**System Responses:**
1. **Contract draft**
   - standard MSA + SOW based on proposal scope
2. **Negotiation checklist**
   - exceptions, liability, data processing addendum
3. **Signature workflow**
   - automated e-sign request + reminders

**Outputs:**
- `msa_contract`
- `sow_contract`
- `signature_status`

---

## 5) Delivery → Renewal Flow

**Goal:** ensure onboarding success and prepare for renewal or expansion.

**Trigger:** contract signed, delivery started.

**Inputs:**
- `implementation_plan`
- `customer_success_metrics`
- `usage_telemetry`

**System Responses:**
1. **Onboarding sequence**
   - kickoff checklist, integration tasks, HITL approvals
2. **Success review**
   - “Did we meet baseline metrics?”
3. **Expansion cues**
   - detect upsell opportunities based on telemetry

**Outputs:**
- `onboarding_status`
- `success_score`
- `renewal_recommendation`

---

## Response Template Library (Reusable)

**1) Acknowledgement**
> “Thanks for reaching out. I’ll ask a few questions to confirm fit and priority.”

**2) Clarify Intent**
> “Which outcomes matter most: speed, cost, accuracy, or compliance?”

**3) Proposal Confirmation**
> “Here is the draft. Please confirm scope and pricing before I submit.”

**4) HITL Required**
> “This step requires human approval based on compliance policy.”

---

## Integration Touchpoints

- **UI:** use onboarding forms and terminal variants for intake and approval routing.
- **API:** use `/api/forms/*` for structured intake, `/api/integrations/*` for system hooks.
- **Ledger:** log each stage transition for audit and renewal forecasting.
