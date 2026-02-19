# Murphy System — Request for Information (RFI) Ledger

This ledger tracks decisions required to unblock architecture wiring, governance enforcement, and section 1–14 implementation closure.

## Status model

- **OPEN**: decision needed before full implementation.
- **ANSWERED**: user provided decision; implementation work is queued or in progress.
- **IMPLEMENTED**: decision has been incorporated into runtime/docs/tests.

## Response format

- Reply with: `RFI-<ID>: <decision>` for each item.
- If undecided: `RFI-<ID>: defer`.

---

## Decision Ledger

| ID | Status | Priority | Blocking | Topic | Decision request | Options / Expected Input |
| --- | --- | --- | --- | --- | --- | --- |
| RFI-001 | OPEN | High | Yes | Domain-aligned swarms | Final authoritative domain list for DomainSwarms (Engineering, Security, Compliance/GRC, Finance, Legal, Product, etc.)? | Provide domain names + owner role per domain |
| RFI-002 | OPEN | High | Yes | Executive authority gates | Final authority scopes and delegation rules for approval gates (including separation-of-duties)? | Provide approver roles, delegation limits, SoD exceptions |
| RFI-003 | OPEN | High | Yes | Scope enforcement | Exact mandatory Request Envelope fields defining in-scope vs Change Order? | Confirm required scope keys + minimum acceptance criteria |
| RFI-004 | OPEN | High | Yes | Change orders | Which out-of-scope triggers are mandatory Change Orders (integration, budget, compliance expansion, environment change, etc.)? | Confirm trigger set + approval chain |
| RFI-005 | OPEN | High | Yes | Budget/T&M controls | Which negotiated role rate table + NTE defaults are authoritative for T&M mode? | Provide rate card source + default NTE thresholds |
| RFI-006 | OPEN | High | Yes | Compliance rulepacks | Which baseline rulepacks are mandatory (SOC2/PCI/HIPAA/regional privacy), and enforcement mode per rulepack (refuse/escalate/conditional)? | Provide rulepacks + enforcement mode by rulepack |
| RFI-007 | OPEN | High | Yes | Authoritative source registry | Confirm one-source-of-truth mapping by fact type (IAM, Git, CI/CD, ITSM, GRC, SIEM, CLM, ERP/Billing). | Provide authoritative system list + precedence rules |
| RFI-008 | OPEN | Medium | No | Legacy orchestrator wiring | For Rubixcube/Triage/Clockwork bridges, preferred wiring order? | Rank priority adapters 1..N |
| RFI-009 | OPEN | Medium | No | Deterministic compute plane | Replay policy decision: required retention window + re-evaluation SLA for historical gate decisions? | Provide retention period + replay SLA |
| RFI-010 | OPEN | Medium | No | Telemetry/public reporting | Which per-prompt micro-increment precision should be externally shown (`0.1`, `0.01`, `0.001`, etc.)? | Choose precision + publication cadence |
| RFI-011 | OPEN | Medium | No | Verification boundary | Facts/citations policy: when is “mark uncertain” acceptable vs hard refusal? | Provide domain/risk-based thresholds |
| RFI-012 | OPEN | Medium | No | UI operations | Required UI control set for shadow-agent account/user-base management (create/suspend/delegate/audit export)? | Confirm minimum UI operations + audit requirements |

---

## Answered

Move answered rows here (keep ID + decision + date + owner).

Example:
- `RFI-010 | Decision: Show micro-increments at 0.01 precision | Date: 2026-02-19 | Owner: @IKNOWINOT`

## Implemented

Move implemented rows here (keep ID + linked commit/section + date).

Example:
- `RFI-012 | Implemented via commit abc1234 + FULL_SYSTEM_ASSESSMENT §14 | Date: 2026-02-20`
