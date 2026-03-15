# Murphy System — Outreach Compliance Policy

<!--
  Copyright © 2020 Inoni Limited Liability Company
  Creator: Corey Post
  License: BSL 1.1
  Design Label: COMPL-002
-->

**Design Label:** COMPL-002  
**Owner:** Security Team / Marketing Team  
**Status:** Active  
**Last Updated:** 2026-03-14

---

## Purpose

Murphy System automates outreach and marketing on behalf of Inoni LLC and platform customers.
This policy defines the hard rules that govern ALL automated outreach.

These rules are enforced in code by the `OutreachComplianceGate` (COMPL-002) integration
layer and the `ContactComplianceGovernor` (COMPL-001) engine — no outreach path bypasses
this gate.

---

## Core Rules

### Rule 1: 30-Day Contact Cooldown (Non-Customers)

- No prospect may be contacted more than once within a 30-day rolling window
- This applies across ALL channels (email, SMS, LinkedIn, phone)
- Existing customers have a reduced cooldown of 7 days for marketing messages; no
  cooldown for service/transactional messages (e.g., billing receipts, support replies)

### Rule 2: Explicit Opt-Out is Permanent

- Any contact who says "stop", "unsubscribe", "remove me", "do not contact", or
  "opt out" is immediately added to the global Do-Not-Contact (DNC) list
- DNC entries are immutable and permanent
- A DNC contact cannot be reached by any channel, by any engine, for any reason
  (except legally required transactional messages such as billing disputes)
- The only way to reverse a DNC entry is for the contact themselves to re-opt-in
  with explicit written consent

### Rule 3: Regulatory Compliance

Murphy enforces compliance with the following regulations across all automated outreach:

| Regulation | Jurisdiction | Key Requirements Enforced |
|---|---|---|
| **CAN-SPAM Act** | US | Unsubscribe link in every email, physical address, honest subjects, 10-day opt-out processing |
| **TCPA** | US | No calls/texts without prior express consent, time-of-day restrictions (8am–9pm local), DNC registry compliance |
| **GDPR** | EU | Lawful basis required, right to erasure honored, data minimization, consent withdrawal honored immediately |
| **CCPA** | California | Right to opt out, "Do Not Sell" honored, clear notice at point of collection |
| **CASL** | Canada | Express consent required, sender identification, 10-day unsubscribe processing |

When a prospect's region cannot be determined, the most restrictive regulation
(GDPR) is applied.

### Rule 4: Every Outreach is Audited

- Every outreach attempt — whether allowed or blocked — is logged in an immutable
  audit trail by the `OutreachComplianceGate`
- Audit records include: contact ID, channel, decision, block reason, regulation
  cited, and ISO timestamp
- Audit logs are retained for 7 years (SOX/GDPR requirement overlap)

### Rule 5: Self-Selling Engine Compliance

Murphy's self-selling engine (which sells Murphy itself) follows all the same rules:

- Prospects discovered by `SalesAutomationEngine` are checked against DNC before
  any outreach is composed or sent
- Every message composed by `SelfSellingOutreach` passes through
  `ContactComplianceGovernor` via `OutreachComplianceGate.check_and_record()`
- Reply processing via `OutreachComplianceGate.process_reply()` automatically
  detects opt-out intent and immediately adds the contact to the DNC list
- The 30-day cooldown is enforced between selling cycles for the same prospect

---

## Technical Enforcement

These rules are enforced by the following components:

| Component | Design Label | Role |
|---|---|---|
| `ContactComplianceGovernor` | COMPL-001 | Centralized compliance engine — DNC registry, cooldown tracking, regulatory gating |
| `OutreachComplianceGate` | COMPL-002 | Integration layer — wired into every outreach path as a pre-send gate |
| `GovernanceKernel` | GATE-001 | Bounds all autonomous actions including outreach |
| `ComplianceEngine` | — | Validates against GDPR, CCPA, SOC2, HIPAA, PCI-DSS frameworks |

The gate **fails closed**: if `ContactComplianceGovernor` is unavailable or raises an
unexpected error, the outreach is blocked, not allowed.

---

## Audit & Reporting

The following endpoints expose compliance data to authorized administrators:

| Endpoint | Access | Description |
|---|---|---|
| `GET /api/compliance/outreach/audit` | Admin | View the full outreach audit trail |
| `GET /api/compliance/outreach/dnc` | Admin only | View the Do-Not-Contact list |
| `GET /api/compliance/outreach/stats` | Admin | View compliance statistics (allow/block rates, top block reasons) |

---

## Enforcement Matrix

| Engine | Gate Applied | Method |
|---|---|---|
| `MurphySelfSellingEngine` | ✅ Yes | `OutreachComplianceGate.check_and_record()` before `SelfSellingOutreach.send()` |
| `SalesAutomationEngine.automate_outreach()` | ✅ Yes | `OutreachComplianceGate.check_and_record()` per recipient |
| `MarketingAutomationEngine.automate_social_media()` | ✅ Yes | `OutreachComplianceGate.check_and_record()` per recipient |
| `AdaptiveCampaignEngine` | ✅ Yes | `OutreachComplianceGate.check_and_record()` before campaign send |
| Reply processing (all engines) | ✅ Yes | `OutreachComplianceGate.process_reply()` on every inbound reply |
