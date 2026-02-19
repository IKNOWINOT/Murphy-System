# Murphy System — Request for Information (RFI)

This file tracks **user decisions required** to unblock architecture wiring, governance enforcement, and section 1–14 implementation closure.

Response format (recommended):
- Reply with: `RFI-<ID>: <decision>` for each item.
- If undecided, reply with: `RFI-<ID>: defer`.

---

## Open RFIs

| ID | Priority | Blocking | Topic | Question needing your decision | Options / Expected Input |
| --- | --- | --- | --- | --- | --- |
| RFI-001 | High | Yes | Domain-aligned swarms | Final authoritative domain list for DomainSwarms (Engineering, Security, Compliance/GRC, Finance, Legal, Product, etc.)? | Provide domain names + owner role per domain |
| RFI-002 | High | Yes | Executive authority gates | What are the final authority scopes and delegation rules for approval gates (including separation-of-duties)? | Provide approver roles, delegation limits, SoD exceptions |
| RFI-003 | High | Yes | Scope enforcement | What exact fields are mandatory in Request Envelope to define in-scope vs Change Order? | Confirm required scope keys + minimum acceptance criteria |
| RFI-004 | High | Yes | Change orders | Which out-of-scope triggers are mandatory Change Orders (integration, budget, compliance expansion, environment change, etc.)? | Confirm trigger set + approval chain |
| RFI-005 | High | Yes | Budget/T&M controls | What negotiated role rate table + NTE defaults should be authoritative for T&M mode? | Provide rate card source and default NTE thresholds |
| RFI-006 | High | Yes | Compliance rulepacks | Which rulepacks are mandatory in baseline runtime (SOC2/PCI/HIPAA/regional privacy), and per-rulepack enforcement mode (refuse/escalate/conditional)? | Provide baseline rulepacks + enforcement mode by rulepack |
| RFI-007 | High | Yes | Authoritative sources registry | Confirm one-source-of-truth mapping per fact type (IAM, Git, CI/CD, ITSM, GRC, SIEM, CLM, ERP/Billing). | Provide authoritative system list + precedence rules |
| RFI-008 | Medium | No | Legacy orchestrator wiring | For Rubixcube/Triage/Clockwork bridges, what is preferred wiring order (pilot first)? | Rank priority adapters 1..N |
| RFI-009 | Medium | No | Deterministic compute plane | Replay policy decision: required retention window + re-evaluation SLA for historical gate decisions? | Provide retention period and replay SLA |
| RFI-010 | Medium | No | Telemetry/public reporting | What per-prompt micro-increment precision should be externally shown (`0.1`, `0.01`, `0.001`, etc.)? | Choose precision + publication cadence |
| RFI-011 | Medium | No | Verification boundary | Facts/citations policy: when is “mark uncertain” acceptable versus hard refusal? | Provide domain/risk-based thresholds |
| RFI-012 | Medium | No | UI operations | Required UI control set for shadow-agent account/user-base management (create/suspend/delegate/audit export)? | Confirm minimum UI operations and audit requirements |

---

## Closed RFIs

_None yet. Move resolved items here with decision date and summary._
